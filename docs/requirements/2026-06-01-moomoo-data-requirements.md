# moomoo 数据获取需求文档

版本：v0.1
日期：2026-06-01

## 1. 目标

从多个 moomoo 账户中获取资产、持仓、期权、收益、现金、保证金等数据，统一折算为 JPY，写入本地 SQLite，供持仓全景看板展示当前状态与历史曲线。

## 2. 账户范围

MVP 支持以下账户类型：

| 类型 | 是否支持 | 说明 |
|---|---:|---|
| 美股证券账户 | 是 | 股票、ETF、现金、收益 |
| 美股期权账户 | 是 | 期权合约、方向、到期日、行权价 |
| 港股/其他市场账户 | 是 | 需要统一 symbol 与币种 |
| 融资/保证金账户 | 是 | 展示保证金占用、融资金额、可用购买力 |

## 3. 同步方式

| 同步方式 | 要求 |
|---|---|
| 手动同步 | 用户点击“同步”后立即拉取全部账户 |
| 自动同步 | 每天 07:00 JST 执行一次 |
| 启动补同步 | MVP 不做；后续可提示“今日尚未同步” |
| 快照策略 | 每次成功同步生成一组新快照 |
| 历史保存 | 永久保存，不自动删除 |

## 4. 数据口径

| 项目 | 规则 |
|---|---|
| 展示币种 | 全部统一折算为 JPY |
| 汇率来源 | 优先使用 moomoo API 返回或可获取的汇率 |
| 收益来源 | 以 moomoo API 返回的账户收益/持仓收益为准 |
| 历史曲线 | 优先使用 SQLite 中保存的 moomoo 收益快照生成 |
| 缺失收益 | 不覆盖 moomoo 收益字段；如页面需要连续曲线，可用资产变化估算并明确标记 |
| 主题归类 | 数据层只保存 symbol，主题由本地配置层处理 |

## 5. 必取数据

### 账户级数据

| 字段 | 说明 |
|---|---|
| account_id | moomoo 账户 ID |
| account_name | 本地显示名称 |
| market | US / HK / OTHER |
| currency | 原始账户币种 |
| total_assets_original | 原币种总资产 |
| total_assets_jpy | JPY 折算总资产 |
| cash_original | 原币种现金 |
| cash_jpy | JPY 折算现金 |
| total_pnl_original | moomoo 返回总收益 |
| total_pnl_jpy | JPY 折算总收益 |
| daily_pnl_original | moomoo 返回日收益 |
| daily_pnl_jpy | JPY 折算日收益 |

### 持仓级数据

| 字段 | 说明 |
|---|---|
| symbol | 标的代码 |
| name | 标的名称 |
| market | 市场 |
| asset_type | stock / etf / option / cash / other |
| quantity | 持仓数量 |
| average_cost | 成本价 |
| latest_price | 最新价 |
| market_value_original | 原币种市值 |
| market_value_jpy | JPY 折算市值 |
| position_ratio | 占净资产比例 |
| pnl_original | 持仓收益 |
| pnl_jpy | JPY 折算收益 |
| pnl_ratio | 收益率 |

### 期权数据

| 字段 | 说明 |
|---|---|
| contract_code | 期权合约代码 |
| underlying | 正股标的 |
| option_type | CALL / PUT |
| side | LONG / SHORT |
| strike | 行权价 |
| expiry | 到期日 |
| quantity | 合约数量 |
| premium | 权利金/当前价格 |
| market_value_jpy | JPY 折算市值 |
| notional_exposure_jpy | 名义风险暴露 |
| risk_tag | short_put / short_call / long_call / long_put / unknown_option |

### 保证金数据

| 字段 | 说明 |
|---|---|
| margin_used_jpy | 保证金占用 |
| financing_amount_jpy | 融资金额 |
| buying_power_jpy | 可用购买力 |
| cash_available_jpy | 可用现金 |

## 6. 快照规则

每次同步写入一个 `snapshot_batch`，同一批次下包含账户快照、持仓快照、期权快照、保证金快照、汇率快照和错误记录。

核心原则：

- 同步未完成时不覆盖旧数据。
- 单个账户失败时，允许本批次部分成功，但必须记录失败账户。
- 每条金额数据保留原币种金额和 JPY 折算金额。
- 历史数据只追加，不自动修改旧快照。
- SQLite 写入失败时回滚本批次，不能产生半批次数据。

## 7. 异常处理

| 场景 | 处理 |
|---|---|
| moomoo OpenD 未启动 | 同步失败，提示启动 OpenD |
| 某账户读取失败 | 跳过该账户，记录错误 |
| 汇率缺失 | 原币种金额保存，JPY 折算字段置空并记录错误 |
| 收益字段缺失 | 保存为空，页面显示“收益数据缺失”或估算标记 |
| 期权解析失败 | 保存原始合约代码，进入异常合约列表 |
| SQLite 写入失败 | 回滚本批次数据 |

## 8. MVP 不做

- 不从外部汇率 API 获取汇率
- 不自动修正 moomoo 收益
- 不做交易下单
- 不做云端同步
- 不做多用户权限
- 不做自动主题识别
