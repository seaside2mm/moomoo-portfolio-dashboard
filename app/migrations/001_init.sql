CREATE TABLE IF NOT EXISTS snapshot_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_time TEXT NOT NULL,
  trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual', 'scheduled')),
  status TEXT NOT NULL CHECK (status IN ('success', 'partial_success', 'failed')),
  base_currency TEXT NOT NULL DEFAULT 'JPY',
  net_inflow_jpy REAL,
  cumulative_return_rate REAL,
  total_assets_jpy REAL,
  total_pnl_jpy REAL,
  daily_pnl_jpy REAL,
  error_summary TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL,
  account_id TEXT NOT NULL,
  account_name TEXT NOT NULL,
  market TEXT NOT NULL,
  account_type TEXT NOT NULL,
  currency TEXT NOT NULL,
  total_assets_original REAL,
  total_assets_jpy REAL,
  cash_original REAL,
  cash_jpy REAL,
  total_pnl_original REAL,
  total_pnl_jpy REAL,
  daily_pnl_original REAL,
  daily_pnl_jpy REAL,
  margin_used_jpy REAL,
  financing_amount_jpy REAL,
  buying_power_jpy REAL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE TABLE IF NOT EXISTS position_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL,
  account_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  raw_code TEXT NOT NULL,
  name TEXT NOT NULL,
  market TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  currency TEXT NOT NULL,
  quantity REAL NOT NULL,
  average_cost REAL,
  latest_price REAL,
  market_value_original REAL,
  market_value_jpy REAL,
  pnl_original REAL,
  pnl_jpy REAL,
  pnl_ratio REAL,
  position_ratio REAL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE TABLE IF NOT EXISTS option_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL,
  account_id TEXT NOT NULL,
  contract_code TEXT NOT NULL,
  underlying TEXT,
  option_type TEXT,
  side TEXT NOT NULL,
  strike REAL,
  expiry TEXT,
  quantity REAL NOT NULL,
  premium REAL,
  contract_multiplier REAL NOT NULL DEFAULT 100,
  market_value_jpy REAL,
  notional_exposure_jpy REAL,
  risk_tag TEXT NOT NULL,
  parse_status TEXT NOT NULL,
  raw_contract TEXT NOT NULL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE TABLE IF NOT EXISTS exchange_rates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL,
  from_currency TEXT NOT NULL,
  to_currency TEXT NOT NULL DEFAULT 'JPY',
  rate REAL NOT NULL,
  source TEXT NOT NULL DEFAULT 'moomoo',
  rate_time TEXT NOT NULL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE TABLE IF NOT EXISTS theme_mappings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL UNIQUE,
  theme TEXT NOT NULL,
  display_name TEXT,
  color TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS sync_errors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER,
  account_id TEXT,
  data_type TEXT NOT NULL,
  error_code TEXT NOT NULL,
  error_message TEXT NOT NULL,
  raw_payload TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (batch_id) REFERENCES snapshot_batches(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_batches_time ON snapshot_batches(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_account_snapshots_batch ON account_snapshots(batch_id);
CREATE INDEX IF NOT EXISTS idx_position_snapshots_batch ON position_snapshots(batch_id);
CREATE INDEX IF NOT EXISTS idx_option_snapshots_batch ON option_snapshots(batch_id);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_batch ON exchange_rates(batch_id);
CREATE INDEX IF NOT EXISTS idx_category_definitions_type ON category_definitions(category_type, enabled, sort_order);
CREATE INDEX IF NOT EXISTS idx_symbol_category_overrides_symbol ON symbol_category_overrides(symbol, market, enabled);
CREATE INDEX IF NOT EXISTS idx_sync_errors_batch ON sync_errors(batch_id);

INSERT OR IGNORE INTO category_definitions
(category_type, category_code, category_name, parent_code, sort_order, enabled, updated_at)
VALUES
('sector', 'technology', '科技', NULL, 10, 1, datetime('now')),
('sector', 'semiconductor', '半导体', NULL, 20, 1, datetime('now')),
('sector', 'finance', '金融', NULL, 30, 1, datetime('now')),
('sector', 'healthcare', '医疗健康', NULL, 40, 1, datetime('now')),
('sector', 'consumer', '消费', NULL, 50, 1, datetime('now')),
('sector', 'energy', '能源', NULL, 60, 1, datetime('now')),
('sector', 'defense', '防御', NULL, 65, 1, datetime('now')),
('sector', 'space', '太空', NULL, 70, 1, datetime('now')),
('sector', 'ai_infrastructure', 'AI基建', NULL, 80, 1, datetime('now')),
('sector', 'optical_communication', '光通讯', NULL, 100, 1, datetime('now')),
('sector', 'physical_ai', '物理AI', NULL, 110, 1, datetime('now')),
('sector', 'storage', '存储', NULL, 120, 1, datetime('now')),
('sector', 'chip', '芯片', NULL, 125, 1, datetime('now')),
('sector', 'etf', 'ETF', NULL, 130, 1, datetime('now')),
('sector', 'japan_stock', '日股', NULL, 140, 1, datetime('now')),
('sector', 'ai_app', 'AI应用', NULL, 150, 1, datetime('now')),
('sector', 'healthcare_trade', '医疗', NULL, 160, 1, datetime('now')),
('sector', 'financial_service', '金融服务', NULL, 170, 1, datetime('now')),
('industry', 'ai_chip', 'AI芯片', 'semiconductor', 10, 1, datetime('now')),
('industry', 'cloud_service', '云服务', 'technology', 20, 1, datetime('now')),
('industry', 'bank', '银行', 'finance', 30, 1, datetime('now')),
('theme', 'ai', 'AI', NULL, 10, 1, datetime('now')),
('theme', 'cloud', '云计算', NULL, 20, 1, datetime('now')),
('theme', 'high_dividend', '高股息', NULL, 30, 1, datetime('now')),
('theme', 'ev', '新能源车', NULL, 40, 1, datetime('now'));
