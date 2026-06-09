# moomoo 数据同步流程文档

版本：v0.1
日期：2026-06-01

## 1. 同步目标

从多个 moomoo 账户读取账户资金、股票/ETF 持仓、期权持仓、保证金信息和收益数据，统一转换为看板标准字段，并写入 SQLite 历史快照。

MVP 支持两种触发方式：

| 触发方式 | 说明 |
|---|---|
| 手动同步 | 用户点击同步按钮后立即执行 |
| 每日自动同步 | 每天 07:00 JST 自动执行 |

## 2. 同步前置条件

| 条件 | 要求 |
|---|---|
| moomoo OpenD | 已启动并可连接 |
| OpenAPI 权限 | 当前 moomoo 账户可读取交易账户、资金、持仓 |
| 账户配置 | 本地配置需要包含要同步的市场/账户范围 |
| SQLite | 数据库文件可读写 |
| 时区 | 快照时间统一使用 Asia/Tokyo |

MVP 只做只读同步，不设计交易解锁流程；如果后续加入下单，再单独设计 `unlock_trade` 相关流程。

## 3. 账户发现流程

同步开始后，系统先创建 moomoo 交易上下文，再获取账户列表。

```text
开始同步
  ↓
连接 OpenD
  ↓
按市场创建 TradeContext
  ↓
调用 get_acc_list
  ↓
获取 acc_id / acc_index / trd_env 等账户信息
  ↓
过滤启用账户
  ↓
生成本次同步账户清单
```

账户识别规则：

| 项目 | 规则 |
|---|---|
| 主键 | 使用 `acc_id` 作为账户唯一标识 |
| 不推荐 | 不用 `acc_index` 做长期标识，因为顺序可能变化 |
| 多市场 | US / HK / OTHER 按配置创建对应 context |
| 本地名称 | `account_name` 由本地配置维护 |

## 4. 单账户同步流程

每个账户按固定顺序拉取数据。

```text
同步账户 acc_id
  ↓
读取账户资金 accinfo_query
  ↓
读取持仓 position_list_query
  ↓
拆分普通持仓与期权持仓
  ↓
读取/计算保证金字段
  ↓
标准化字段
  ↓
转换 JPY 金额
  ↓
放入本批次待写入数据
```

MVP 必取数据：

| 数据类别 | 来源 | 写入表 |
|---|---|---|
| 账户资金 | `accinfo_query` | `account_snapshots` |
| 股票/ETF 持仓 | `position_list_query` | `position_snapshots` |
| 期权持仓 | `position_list_query` 后解析 | `position_snapshots` + `option_snapshots` |
| 汇率 | moomoo 可获取数据优先 | `exchange_rates` |
| 同步错误 | 异常捕获 | `sync_errors` |

## 5. JPY 折算规则

所有看板展示金额统一为 JPY。

| 场景 | 处理 |
|---|---|
| moomoo 可直接返回 JPY 口径 | 直接保存 JPY 字段 |
| 只返回原币种 | 保存原币种金额，再用 moomoo 汇率折算 |
| 汇率缺失 | 原币种金额照常保存，JPY 字段置空 |
| 汇率异常 | 记录 `sync_errors`，本账户可标记为部分成功 |

每条金额数据都保留两份：

```text
xxx_original
xxx_jpy
currency
```

## 6. 字段标准化流程

moomoo 原始字段不直接进入页面，必须经过 adapter 转换。

```text
moomoo raw response
  ↓
moomoo_adapter
  ↓
标准 AccountSnapshot / PositionSnapshot / OptionSnapshot
  ↓
校验
  ↓
SQLite 写入
```

标准化要求：

| 字段 | 规则 |
|---|---|
| `symbol` | 统一大写，保留 `raw_code` 或独立 market 字段 |
| `asset_type` | 标准化为 `stock / etf / option / cash / other` |
| `quantity` | 支持正负数量 |
| `market_value_jpy` | 可为负，尤其期权空头 |
| `pnl_jpy` | 以 moomoo 返回收益为准 |
| `position_ratio` | 使用 JPY 市值 / 全账户总净资产计算 |
| `snapshot_time` | 同一批次全局一致 |

## 7. 期权解析流程

期权从持仓列表中识别后，进入专门解析流程。

```text
发现 asset_type = option
  ↓
解析 contract_code
  ↓
识别 underlying / CALL PUT / strike / expiry
  ↓
识别 side = LONG 或 SHORT
  ↓
计算 notional_exposure_jpy
  ↓
生成 risk_tag
```

风险标签规则：

| 条件 | risk_tag |
|---|---|
| PUT + SHORT | `short_put` |
| CALL + SHORT | `short_call` |
| CALL + LONG | `long_call` |
| PUT + LONG | `long_put` |
| 解析失败 | `unknown_option` |

期权解析失败时，不丢弃原始数据；写入 `raw_contract`，`parse_status = failed`，并进入异常合约列表。

## 8. SQLite 写入事务

每次同步生成一个 `snapshot_batch`。

推荐流程：

```text
创建 batch，状态 pending
  ↓
拉取所有账户数据
  ↓
开启 SQLite transaction
  ↓
写 snapshot_batches
  ↓
写 account_snapshots
  ↓
写 position_snapshots
  ↓
写 option_snapshots
  ↓
写 exchange_rates
  ↓
写 sync_errors
  ↓
commit
```

批次状态：

| 状态 | 条件 |
|---|---|
| `success` | 全部账户和数据类型成功 |
| `partial_success` | 至少一个账户成功，部分账户或字段失败 |
| `failed` | 全部账户失败，或 SQLite 写入失败 |

SQLite 写入失败时必须 rollback，不能产生半批次脏数据。

## 9. 调度流程

每日自动同步规则：

| 项目 | 规则 |
|---|---|
| 时间 | 每天 07:00 JST |
| 触发类型 | `scheduled` |
| 重复执行 | 同一天如果已有 scheduled 成功快照，则不重复执行 |
| 手动同步 | 不受每日限制，可随时执行 |
| 冲突处理 | 如果同步中再次触发，后一个任务跳过 |

建议增加同步锁：

```text
sync_lock = active
```

避免手动同步和定时同步同时写库。

## 10. 异常处理

| 异常 | 处理 |
|---|---|
| OpenD 未启动 | 本次同步失败，不写账户快照 |
| 获取账户列表失败 | 本次同步失败，记录 batch 错误 |
| 单账户资金失败 | 跳过该账户，记录错误 |
| 单账户持仓失败 | 账户资金可写入，持仓记录错误 |
| 汇率缺失 | 写原币种，JPY 字段置空 |
| 期权解析失败 | 写原始合约，标记解析失败 |
| SQLite 写入失败 | rollback 本批次 |
| 定时任务冲突 | 跳过新任务，记录日志 |

## 11. MVP 不做

- 不做交易下单
- 不做交易解锁
- 不接外部汇率 API
- 不自动修正 moomoo 收益
- 不删除历史快照
- 不自动主题识别
- 不做云端同步
