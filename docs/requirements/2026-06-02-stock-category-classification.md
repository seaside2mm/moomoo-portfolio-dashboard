# 持仓板块分类落地文档

版本：v0.1
日期：2026-06-02

## 1. 目标

为 moomoo 持仓增加板块分类能力，让看板可以按板块、行业、主题展示持仓分布。

本方案采用“板块字典 + 股票人工覆盖 + 简单 API”的方式落地。前端只负责展示分类结果，不提供复杂编辑页；人工修改通过 API、SQL 或后续脚本完成。

## 2. 核心原则

| 项目 | 规则 |
|---|---|
| 前端职责 | 只展示持仓和分类结果，不做复杂分类编辑 |
| 板块名称 | 由数据库字典统一维护，不散落在代码中 |
| 股票归属 | 通过股票覆盖表指定 symbol 对应分类 |
| 分类优先级 | 人工覆盖 > 自动分类 > 未分类 |
| 历史快照 | 默认不回写历史，只影响当前展示和未来同步 |
| 现有表 | 不直接修改 `position_snapshots` 的原始持仓字段 |

## 3. 范围

包含：

- 新增板块字典表 `category_definitions`
- 新增股票分类覆盖表 `symbol_category_overrides`
- 新增分类查询和覆盖写入 API
- Dashboard 持仓结果增加分类展示字段
- Dashboard 板块聚合按最终分类结果计算

不包含：

- 前端分类编辑页
- 批量导入页面
- 自动从外部数据源识别行业
- 历史快照批量重算
- 删除或替换现有 `theme_mappings`

## 4. 分类层级

系统先支持三类分类：

| 类型 | 字段 | 示例 | 用途 |
|---|---|---|---|
| 大板块 | sector | 半导体 / 科技 / 金融 | 看整体资产配置 |
| 细行业 | industry | AI芯片 / 云服务 / 银行 | 看行业集中度 |
| 投资主题 | theme | AI / 高股息 / 新能源车 | 看投资叙事和主题暴露 |

同一只股票可以同时拥有 `sector`、`industry`、`theme`。缺失的层级显示为 `未分类`。

## 5. 板块名指定方式

板块名不直接写入股票表，而是先写入字典表。

`category_code` 是程序使用的稳定编码，建议使用英文小写和下划线，例如 `semiconductor`、`ai_chip`、`high_dividend`。

`category_name` 是页面展示名，可以使用中文，例如 `半导体`、`AI芯片`、`高股息`。

这样后期如果想把 `半导体` 改成 `芯片与半导体`，只需要修改字典表的展示名，不需要改所有股票记录。

## 6. 数据表设计

### 6.1 category_definitions

维护系统允许使用的板块、行业和主题。

```sql
CREATE TABLE IF NOT EXISTS category_definitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_type TEXT NOT NULL CHECK (category_type IN ('sector', 'industry', 'theme')),
  category_code TEXT NOT NULL UNIQUE,
  category_name TEXT NOT NULL,
  parent_code TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_category_definitions_type
ON category_definitions(category_type, enabled, sort_order);
```

字段说明：

| 字段 | 说明 |
|---|---|
| category_type | 分类类型，限定为 `sector` / `industry` / `theme` |
| category_code | 稳定编码，供 API、统计和关联使用 |
| category_name | 展示名称 |
| parent_code | 可选父级编码，例如行业挂到大板块 |
| sort_order | 展示排序 |
| enabled | 1 启用 / 0 停用 |
| updated_at | 更新时间 |

### 6.2 symbol_category_overrides

维护股票到分类的人工指定关系。

```sql
CREATE TABLE IF NOT EXISTS symbol_category_overrides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  market TEXT NOT NULL DEFAULT 'US',
  sector_code TEXT,
  industry_code TEXT,
  theme_code TEXT,
  reason TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL,
  UNIQUE(symbol, market)
);

CREATE INDEX IF NOT EXISTS idx_symbol_category_overrides_symbol
ON symbol_category_overrides(symbol, market, enabled);
```

字段说明：

| 字段 | 说明 |
|---|---|
| symbol | 标准股票代码，例如 `NVDA` |
| market | 市场，例如 `US` / `HK` / `OTHER` |
| sector_code | 对应 `category_definitions.category_code` |
| industry_code | 对应 `category_definitions.category_code` |
| theme_code | 对应 `category_definitions.category_code` |
| reason | 人工指定原因，可为空 |
| enabled | 1 启用 / 0 停用 |
| updated_at | 更新时间 |

## 7. 初始板块字典示例

第一版可以先录入少量常用分类，后续按持仓逐步补齐。

```sql
INSERT INTO category_definitions
(category_type, category_code, category_name, parent_code, sort_order, enabled, updated_at)
VALUES
('sector', 'technology', '科技', NULL, 10, 1, datetime('now')),
('sector', 'semiconductor', '半导体', NULL, 20, 1, datetime('now')),
('sector', 'finance', '金融', NULL, 30, 1, datetime('now')),
('sector', 'healthcare', '医疗健康', NULL, 40, 1, datetime('now')),
('sector', 'consumer', '消费', NULL, 50, 1, datetime('now')),
('sector', 'energy', '能源', NULL, 60, 1, datetime('now')),
('industry', 'ai_chip', 'AI芯片', 'semiconductor', 10, 1, datetime('now')),
('industry', 'cloud_service', '云服务', 'technology', 20, 1, datetime('now')),
('industry', 'bank', '银行', 'finance', 30, 1, datetime('now')),
('theme', 'ai', 'AI', NULL, 10, 1, datetime('now')),
('theme', 'cloud', '云计算', NULL, 20, 1, datetime('now')),
('theme', 'high_dividend', '高股息', NULL, 30, 1, datetime('now')),
('theme', 'ev', '新能源车', NULL, 40, 1, datetime('now'));
```

## 8. 股票写入示例

### 8.1 API 写入

请求：

```http
POST /api/category-overrides
```

请求体：

```json
{
  "symbol": "NVDA",
  "market": "US",
  "sector_code": "semiconductor",
  "industry_code": "ai_chip",
  "theme_code": "ai",
  "reason": "手工指定为 AI 芯片核心持仓",
  "enabled": true
}
```

预期效果：

| 字段 | 结果 |
|---|---|
| symbol | NVDA |
| market | US |
| 板块 | 半导体 |
| 行业 | AI芯片 |
| 主题 | AI |
| 来源 | manual |

### 8.2 SQL 写入

```sql
INSERT INTO symbol_category_overrides
(symbol, market, sector_code, industry_code, theme_code, reason, enabled, updated_at)
VALUES
('NVDA', 'US', 'semiconductor', 'ai_chip', 'ai', '手工指定为 AI 芯片核心持仓', 1, datetime('now'))
ON CONFLICT(symbol, market) DO UPDATE SET
  sector_code = excluded.sector_code,
  industry_code = excluded.industry_code,
  theme_code = excluded.theme_code,
  reason = excluded.reason,
  enabled = excluded.enabled,
  updated_at = excluded.updated_at;
```

## 9. API 设计

### 9.1 GET /api/categories

返回启用的板块字典。

响应示例：

```json
[
  {
    "category_type": "sector",
    "category_code": "semiconductor",
    "category_name": "半导体",
    "parent_code": null,
    "sort_order": 20,
    "enabled": true
  }
]
```

### 9.2 GET /api/category-overrides

返回当前人工覆盖列表。

响应示例：

```json
[
  {
    "symbol": "NVDA",
    "market": "US",
    "sector_code": "semiconductor",
    "sector_name": "半导体",
    "industry_code": "ai_chip",
    "industry_name": "AI芯片",
    "theme_code": "ai",
    "theme_name": "AI",
    "reason": "手工指定为 AI 芯片核心持仓",
    "enabled": true
  }
]
```

### 9.3 POST /api/category-overrides

新增或更新某只股票的人工分类。

请求体：

```json
{
  "symbol": "TSM",
  "market": "US",
  "sector_code": "semiconductor",
  "industry_code": "ai_chip",
  "theme_code": "ai",
  "reason": "调整为半导体板块",
  "enabled": true
}
```

校验规则：

| 项目 | 规则 |
|---|---|
| symbol | 转成大写后保存 |
| market | 转成大写后保存 |
| sector_code | 如果不为空，必须存在于 `category_definitions` 且类型为 `sector` |
| industry_code | 如果不为空，必须存在于 `category_definitions` 且类型为 `industry` |
| theme_code | 如果不为空，必须存在于 `category_definitions` 且类型为 `theme` |
| enabled | 默认 true |

## 10. Dashboard 数据口径

Dashboard 查询持仓时，需要把 `position_snapshots` 与人工覆盖表、板块字典表关联。

最终每条持仓增加以下字段：

| 字段 | 说明 |
|---|---|
| sector_code | 大板块编码 |
| sector_name | 大板块显示名 |
| industry_code | 行业编码 |
| industry_name | 行业显示名 |
| theme_code | 主题编码 |
| theme_name | 主题显示名 |
| category_source | `manual` / `auto` / `unclassified` |

当没有人工覆盖和自动分类时：

| 字段 | 值 |
|---|---|
| sector_name | 未分类 |
| industry_name | 未分类 |
| theme_name | 未分类 |
| category_source | unclassified |

## 11. 同步流程接入点

第一版不需要在 moomoo 同步时写分类快照，Dashboard 可以实时读取覆盖表并展示当前分类。

推荐第一版流程：

```text
同步 moomoo 持仓
  ↓
写入 position_snapshots
  ↓
Dashboard 查询最新 batch
  ↓
读取 symbol_category_overrides
  ↓
join category_definitions
  ↓
返回带分类的持仓结果
```

后续如果需要固定历史分类，再新增 `position_category_snapshots`：

```text
同步 moomoo 持仓
  ↓
解析当前生效分类
  ↓
写入 position_category_snapshots
  ↓
Dashboard 按 batch_id 读取历史分类结果
```

## 12. 后期修改规则

### 12.1 修改板块显示名

修改 `category_definitions.category_name`。

```sql
UPDATE category_definitions
SET category_name = '芯片与半导体',
    updated_at = datetime('now')
WHERE category_code = 'semiconductor';
```

影响：

| 范围 | 影响 |
|---|---|
| 当前展示 | 立即生效 |
| 未来同步 | 使用新名称展示 |
| 历史快照 | 第一版没有分类快照，因此历史页面也会显示新名称 |

### 12.2 修改股票归属

修改 `symbol_category_overrides`。

```sql
UPDATE symbol_category_overrides
SET sector_code = 'semiconductor',
    reason = '调整为半导体板块',
    updated_at = datetime('now')
WHERE symbol = 'TSM'
  AND market = 'US';
```

影响：

| 范围 | 影响 |
|---|---|
| 当前展示 | 立即生效 |
| 未来同步 | 使用新归属 |
| 历史快照 | 第一版没有分类快照，因此历史页面也会按当前归属展示 |

如需保证历史分类不变，后续增加 `position_category_snapshots` 后再启用历史固定逻辑。

## 13. 与现有 theme_mappings 的关系

当前数据库已有 `theme_mappings`，它可以继续保留，用于兼容现有 Dashboard 逻辑。

新分类体系上线后，推荐逐步迁移：

| 阶段 | 处理 |
|---|---|
| 第一阶段 | 新增分类表和 API，Dashboard 同时兼容 `theme_mappings` |
| 第二阶段 | Dashboard 优先使用 `symbol_category_overrides.theme_code` |
| 第三阶段 | 确认无依赖后，再决定是否停用 `theme_mappings` |

不建议立即删除 `theme_mappings`，避免影响现有页面展示。

## 14. 实施清单

后续实现时按以下顺序执行：

1. 在 migration 中新增 `category_definitions` 和 `symbol_category_overrides`
2. 在模型层新增分类字典和股票分类覆盖模型
3. 在 repository 中新增分类字典查询、覆盖列表查询、覆盖 upsert 方法
4. 在 API 中新增 `GET /api/categories`
5. 在 API 中新增 `GET /api/category-overrides`
6. 在 API 中新增 `POST /api/category-overrides`
7. 在 DashboardService 中给持仓结果补充分类字段
8. 将板块聚合从 `theme_mappings` 逐步切到新分类结果
9. 增加 repository 和 API 测试
10. 使用示例 SQL 或 API 写入几只实际持仓验证展示

## 15. MVP 验收标准

| 项目 | 标准 |
|---|---|
| 字典维护 | 可以通过数据库保存板块、行业、主题 |
| 股票指定 | 可以通过 API 给股票指定分类 |
| 分类展示 | Dashboard 持仓行可以返回分类字段 |
| 未分类处理 | 没有配置的股票显示 `未分类` |
| 前端复杂度 | 不新增分类编辑页面 |
| 可修改性 | 修改字典名或股票归属后，Dashboard 展示随之更新 |
