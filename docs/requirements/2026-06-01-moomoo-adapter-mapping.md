# moomoo Adapter 字段映射表

版本：v0.1
日期：2026-06-01

## 1. Adapter 设计目标

`moomoo_adapter` 负责把 moomoo API 原始返回转换成看板标准模型。UI、SQLite、收益曲线都只依赖标准字段，不直接依赖 moomoo 原始字段。

`moomoo_adapter` 做四件事：

| 职责 | 说明 |
|---|---|
| 字段映射 | moomoo 原始字段 -> 看板标准字段 |
| 类型标准化 | 数字、日期、枚举、币种统一格式 |
| 资产分类 | stock / etf / option / cash / other |
| 错误隔离 | 单字段缺失不让整个同步失败 |

输出对象：

```text
AccountSnapshot
PositionSnapshot
OptionSnapshot
ExchangeRateSnapshot
SyncError
```

## 2. 账户资金映射

来源：`accinfo_query`

目标表：`account_snapshots`

| 标准字段 | moomoo 来源字段 | 转换规则 | 缺失处理 |
|---|---|---|---|
| `account_id` | 调用参数 `acc_id` | 转为 text | 必填，缺失则账户失败 |
| `account_name` | 本地配置 | 按 `acc_id` 查配置 | 无配置则用 `acc_id` |
| `market` | 本地账户配置 / context | 标准化为 `US/HK/OTHER` | 标记 `OTHER` |
| `account_type` | 本地配置 | `securities/options/margin` | 默认 `securities` |
| `currency` | 请求币种或返回币种 | 标准化为 `USD/HKD/JPY` | 标记 unknown |
| `total_assets_original` | `total_assets` | 转 float | 置空并记录错误 |
| `cash_original` | 分币种 cash 字段 / `cash` | 优先分币种现金；`cash` 废弃时谨慎兜底 | 置空 |
| `total_pnl_original` | 可用收益字段 | 以 moomoo 返回收益为准 | 置空，不自行计算覆盖 |
| `daily_pnl_original` | 可用日收益字段 | 以 moomoo 返回收益为准 | 置空 |
| `margin_used_jpy` | 保证金相关字段 | 原币种先转 JPY | 置空 |
| `financing_amount_jpy` | 融资相关字段 | 原币种先转 JPY | 置空 |
| `buying_power_jpy` | 购买力相关字段 | 原币种先转 JPY | 置空 |
| `total_assets_jpy` | adapter 计算 | `original * fx_rate` | 汇率缺失则置空 |
| `cash_jpy` | adapter 计算 | `original * fx_rate` | 汇率缺失则置空 |
| `total_pnl_jpy` | adapter 计算 | `original * fx_rate` | 汇率缺失则置空 |
| `daily_pnl_jpy` | adapter 计算 | `original * fx_rate` | 汇率缺失则置空 |

说明：账户级收益字段要以实际 moomoo 返回字段为准；如果当前 API 不返回完整总收益/日收益，adapter 只保存空值并记录缺失，不用资产变化反推覆盖。

## 3. 持仓映射

来源：`position_list_query`

目标表：`position_snapshots`

| 标准字段 | moomoo 来源字段 | 转换规则 | 缺失处理 |
|---|---|---|---|
| `account_id` | 调用参数 `acc_id` | 转 text | 必填 |
| `symbol` | `code` | 标准化代码，如 `NVDA` | 必填 |
| `raw_code` | `code` | 原样保存，如 `US.NVDA` | 空字符串 |
| `name` | `stock_name` | 原样保存 | 空字符串 |
| `market` | `position_market` / `code` 前缀 | 标准化 `US/HK/OTHER` | `OTHER` |
| `asset_type` | `asset_category` + code 特征 | 映射为 `stock/etf/option/cash/other` | `other` |
| `currency` | `currency` | 标准化币种 | unknown |
| `quantity` | `qty` | 转 float，支持负数 | 缺失则该持仓失败 |
| `average_cost` | `average_cost` / `cost_price` | 优先 `average_cost` | 置空 |
| `latest_price` | `nominal_price` | 转 float | 置空 |
| `market_value_original` | `market_val` | 转 float | 置空 |
| `pnl_original` | `pl_val` | 转 float | 置空 |
| `pnl_ratio` | `pl_ratio` | 统一用小数或百分比，实施前固定一种 | 置空 |
| `market_value_jpy` | adapter 计算 | `market_value_original * fx_rate` | 置空 |
| `pnl_jpy` | adapter 计算 | `pnl_original * fx_rate` | 置空 |
| `position_ratio` | adapter 计算 | `market_value_jpy / batch_total_assets_jpy` | 批次汇总后回填 |

建议：`symbol` 保存标准代码，`raw_code` 保存 moomoo 完整代码。这样港股、美股和其他市场可以追溯来源，也方便处理同名代码冲突。

## 4. 期权识别与映射

来源：优先从 `position_list_query` 中识别期权持仓；必要时用期权链或行情快照补充静态信息。

目标表：`option_snapshots`，同时保留一条 `position_snapshots`。

| 标准字段 | moomoo 来源字段 | 转换规则 | 缺失处理 |
|---|---|---|---|
| `contract_code` | `code` | 原样保存完整合约代码 | 必填 |
| `underlying` | 合约解析 / `stock_owner` | 提取正股代码 | 解析失败置空 |
| `option_type` | 合约解析 / `option_type` | `CALL/PUT` | 解析失败置空 |
| `side` | `qty` 或 position side | `qty < 0` 视为 `SHORT`，否则 `LONG` | unknown |
| `strike` | 合约解析 / `strike_price` | 转 float | 解析失败置空 |
| `expiry` | 合约解析 / `strike_time` | 转 `YYYY-MM-DD` | 解析失败置空 |
| `quantity` | `qty` | 转 float | 必填 |
| `premium` | `nominal_price` | 当前价格 | 置空 |
| `contract_multiplier` | 市场规则 / 合约静态信息 | 默认 100 | 默认 100 并标记 |
| `market_value_jpy` | position 映射 | JPY 市值 | 置空 |
| `notional_exposure_jpy` | adapter 计算 | `abs(strike * quantity * contract_multiplier * fx_rate)` | 字段不足则置空 |
| `risk_tag` | adapter 计算 | `short_put/short_call/long_call/long_put` | `unknown_option` |
| `parse_status` | adapter 计算 | `parsed/failed` | failed |
| `raw_contract` | 原始 row JSON | 保存原始内容 | 必填 |

期权方向规则：

| 条件 | side |
|---|---|
| `quantity > 0` | `LONG` |
| `quantity < 0` | `SHORT` |
| `quantity = 0` | 不写入持仓，或标记异常 |

期权风险标签：

| 条件 | risk_tag |
|---|---|
| `PUT + SHORT` | `short_put` |
| `CALL + SHORT` | `short_call` |
| `CALL + LONG` | `long_call` |
| `PUT + LONG` | `long_put` |

## 5. 汇率映射

目标表：`exchange_rates`

| 标准字段 | 来源 | 转换规则 | 缺失处理 |
|---|---|---|---|
| `from_currency` | 持仓/账户币种 | `USD/HKD/JPY/...` | 必填 |
| `to_currency` | 固定配置 | `JPY` | 必填 |
| `rate` | moomoo 汇率来源 | 转 float | 缺失则记录错误 |
| `source` | 固定值 | `moomoo` | 必填 |
| `rate_time` | moomoo 返回时间或同步时间 | ISO datetime | 用快照时间兜底 |

MVP 只使用 moomoo 汇率。没有汇率时，不调用外部 API。

## 6. 批次汇总字段计算

目标表：`snapshot_batches`

批次汇总不直接依赖单个 API，而是由 adapter 汇总标准对象。

| 字段 | 计算规则 |
|---|---|
| `total_assets_jpy` | 所有成功账户 `total_assets_jpy` 求和 |
| `total_pnl_jpy` | 所有成功账户 `total_pnl_jpy` 求和，缺失账户跳过 |
| `daily_pnl_jpy` | 所有成功账户 `daily_pnl_jpy` 求和，缺失账户跳过 |
| `status` | 全成功为 `success`；部分失败为 `partial_success`；全失败为 `failed` |
| `error_summary` | 汇总 `sync_errors` 的简短描述 |

## 7. 校验规则

adapter 输出前必须校验：

| 校验项 | 规则 | 失败处理 |
|---|---|---|
| `account_id` | 不为空 | 账户失败 |
| `symbol` | 持仓不为空 | 单条持仓失败 |
| `quantity` | 可转 float | 单条持仓失败 |
| `market_value_original` | 可为空但不可为非数字 | 记录字段错误 |
| `currency` | 在已知币种列表或标记 unknown | 记录 warning |
| `expiry` | 期权必须是有效日期 | 期权解析失败 |
| `strike` | 期权必须大于 0 | 期权解析失败 |

## 8. 推荐代码结构

```text
app/
├─ adapters/
│  ├─ moomoo_client.py        # 连接 OpenD、调用 API
│  ├─ moomoo_adapter.py       # 原始字段 -> 标准模型
│  ├─ option_parser.py        # 期权合约解析
│  └─ fx_converter.py         # JPY 折算
├─ models/
│  ├─ snapshots.py            # AccountSnapshot 等 dataclass/Pydantic model
│  └─ errors.py
├─ services/
│  └─ sync_service.py         # 编排同步流程
└─ repositories/
   └─ sqlite_snapshot_repo.py # SQLite 写入/查询
```

## 9. MVP 实现优先级

第一阶段先做：

1. `get_acc_list` 获取账户。
2. `accinfo_query` 写入账户资产。
3. `position_list_query` 写入股票/ETF/期权原始持仓。
4. JPY 折算。
5. SQLite 事务写入。
6. 同步错误记录。

第二阶段再补：

1. 更强的期权合约解析。
2. 保证金字段细化。
3. 收益字段缺失提示。
4. 手动主题配置页面。
