# SQLite 数据库表结构

版本：v0.1
日期：2026-06-01

## 1. snapshot_batches

每次手动同步或每天 07:00 JST 自动同步生成一条批次记录。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer pk | 快照批次 ID |
| snapshot_time | datetime | 快照时间，Asia/Tokyo |
| trigger_type | text | manual / scheduled |
| status | text | success / partial_success / failed |
| base_currency | text | 固定 JPY |
| total_assets_jpy | real | 全账户总资产 |
| total_pnl_jpy | real | 全账户总收益 |
| daily_pnl_jpy | real | 全账户日收益 |
| error_summary | text | 错误摘要 |
| created_at | datetime | 创建时间 |

## 2. account_snapshots

记录每个账户在某个批次下的资产、现金、收益和保证金状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer pk | 账户快照 ID |
| batch_id | integer | 关联 `snapshot_batches.id` |
| account_id | text | moomoo 账户 ID |
| account_name | text | 本地显示名 |
| market | text | US / HK / OTHER |
| account_type | text | securities / options / margin |
| currency | text | 原始币种 |
| total_assets_original | real | 原币种总资产 |
| total_assets_jpy | real | JPY 总资产 |
| cash_original | real | 原币种现金 |
| cash_jpy | real | JPY 现金 |
| total_pnl_original | real | moomoo 总收益 |
| total_pnl_jpy | real | JPY 总收益 |
| daily_pnl_original | real | moomoo 日收益 |
| daily_pnl_jpy | real | JPY 日收益 |
| margin_used_jpy | real | 保证金占用 |
| financing_amount_jpy | real | 融资金额 |
| buying_power_jpy | real | 可用购买力 |

## 3. position_snapshots

股票、ETF、现金类资产进入此表；期权同时保留 position 记录便于总仓位计算。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer pk | 持仓快照 ID |
| batch_id | integer | 批次 ID |
| account_id | text | 账户 ID |
| symbol | text | 标准标的代码 |
| raw_code | text | moomoo 原始代码，如 US.NVDA |
| name | text | 标的名称 |
| market | text | 市场 |
| asset_type | text | stock / etf / option / cash / other |
| currency | text | 原始币种 |
| quantity | real | 持仓数量 |
| average_cost | real | 成本价 |
| latest_price | real | 最新价 |
| market_value_original | real | 原币种市值 |
| market_value_jpy | real | JPY 市值 |
| pnl_original | real | 原币种收益 |
| pnl_jpy | real | JPY 收益 |
| pnl_ratio | real | 收益率 |
| position_ratio | real | 占总净资产比例 |

## 4. option_snapshots

服务期权风险区，重点识别卖出看跌、到期日、行权价和名义风险。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer pk | 期权快照 ID |
| batch_id | integer | 批次 ID |
| account_id | text | 账户 ID |
| contract_code | text | moomoo 期权合约代码 |
| underlying | text | 正股标的 |
| option_type | text | CALL / PUT |
| side | text | LONG / SHORT |
| strike | real | 行权价 |
| expiry | date | 到期日 |
| quantity | real | 合约数量 |
| premium | real | 当前权利金/价格 |
| contract_multiplier | real | 合约乘数，默认 100 |
| market_value_jpy | real | JPY 市值 |
| notional_exposure_jpy | real | 名义风险暴露 |
| risk_tag | text | short_put / short_call / long_call / long_put / unknown_option |
| parse_status | text | parsed / failed |
| raw_contract | text | 原始合约信息 JSON |

## 5. exchange_rates

保存每个批次使用的汇率，确保历史数据可追溯。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer pk | 汇率记录 ID |
| batch_id | integer | 批次 ID |
| from_currency | text | USD / HKD / CNY 等 |
| to_currency | text | 固定 JPY |
| rate | real | 汇率 |
| source | text | moomoo |
| rate_time | datetime | 汇率时间 |

## 6. theme_mappings

用户手动维护的配置表，不随快照变化。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer pk | 配置 ID |
| symbol | text unique | 标的代码 |
| theme | text | 太空 / AI基建 / 医疗等 |
| display_name | text | 自定义显示名 |
| color | text | HEX 颜色 |
| enabled | integer | 1 启用 / 0 停用 |
| updated_at | datetime | 更新时间 |

## 7. sync_errors

记录每次同步中某个账户、某类数据失败的原因。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer pk | 错误 ID |
| batch_id | integer | 批次 ID |
| account_id | text | 账户 ID |
| data_type | text | account / position / option / rate / margin |
| error_code | text | 错误码 |
| error_message | text | 错误信息 |
| raw_payload | text | 原始错误内容 JSON |
| created_at | datetime | 创建时间 |

## 8. 关系设计

```text
snapshot_batches
├─ account_snapshots
├─ position_snapshots
├─ option_snapshots
├─ exchange_rates
└─ sync_errors

theme_mappings 独立存在
position_snapshots.symbol -> theme_mappings.symbol
option_snapshots.underlying -> theme_mappings.symbol
```

## 9. 约束建议

- `snapshot_batches.trigger_type` 限定为 `manual` 或 `scheduled`。
- `snapshot_batches.status` 限定为 `success`、`partial_success` 或 `failed`。
- `theme_mappings.symbol` 唯一。
- 查询看板时优先按 `batch_id` 建索引。
- 查询历史曲线时优先按 `snapshot_time` 建索引。
