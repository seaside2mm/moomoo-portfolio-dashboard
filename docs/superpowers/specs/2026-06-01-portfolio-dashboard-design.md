# Portfolio Dashboard Design

## Overview

This design defines the MVP architecture for a local portfolio dashboard that syncs real moomoo OpenD account data into SQLite snapshots and renders a single-page dashboard for current and historical portfolio review.

The MVP will:

- Connect directly to a real moomoo OpenD instance from day one.
- Store every successful or partially successful sync as an immutable SQLite snapshot batch.
- Expose JSON APIs for snapshot lists, dashboard payloads, manual sync, and editable theme mappings.
- Serve a static frontend from the same FastAPI process.
- Add daily `07:00` JST scheduled sync only after the manual sync path is stable.

The MVP will not:

- Place trades or unlock trading.
- Call external FX providers.
- Add cloud sync, auth, multi-user support, or AI analytics.
- Add automatic theme detection.
- Split frontend and backend into separate applications.

## Goals

- Build the backend data foundation first: SQLite schema, models, repository, and migration script.
- Build the smallest real moomoo sync loop: connect OpenD, fetch accounts, fetch account balances, fetch positions, and persist a snapshot batch.
- Build dashboard APIs for batch selection, dashboard rendering, and manual sync.
- Build a single-page frontend dashboard with overview cards, treemap, theme section, performance curves, and options table.
- Add editable theme mappings in the UI.
- Add daily scheduled sync after the manual sync flow is proven stable.

## Architecture

The application will be a single FastAPI service with static files served from the same process. The codebase will be organized into narrow layers so real OpenD behavior, SQLite persistence, and dashboard aggregation stay isolated from each other.

### Layers

- `app/api`
  HTTP routes only. Responsible for request parsing, response shaping, and status codes.
- `app/services`
  Business orchestration only. `sync_service` drives OpenD syncs, `dashboard_service` builds read models for the UI, and `scheduler_service` wires scheduled jobs.
- `app/adapters`
  Normalizes raw moomoo responses into internal snapshot models. Includes FX conversion and option parsing.
- `app/repositories`
  Owns SQLite schema initialization, transactions, inserts, and read queries.
- `app/models`
  Holds Pydantic models shared between adapters, services, repositories, and APIs.
- `app/static`
  Static HTML, CSS, and browser JavaScript for the dashboard UI.
- `app/migrations`
  SQL migration scripts, beginning with the initial schema bootstrap.

### Runtime Shape

- One FastAPI process serves both APIs and static assets.
- One SQLite database file stores all snapshots and theme mappings locally.
- One in-process sync lock prevents concurrent manual and scheduled sync execution.
- One APScheduler instance will be added after manual sync is stable.

## Data Model Boundaries

The SQLite schema follows the requirements documents and keeps snapshot data append-only. Theme mappings remain editable configuration data outside snapshot versioning.

### Core Tables

- `snapshot_batches`
  One row per sync execution. This is the time anchor for all dashboard reads.
- `account_snapshots`
  One row per account within a batch. Stores account-level balances, cash, PnL, and margin fields.
- `position_snapshots`
  Stores stock, ETF, option, cash, and other positions in a common shape for portfolio aggregation and treemap rendering.
- `option_snapshots`
  Stores parsed option contracts for the risk section, including side, strike, expiry, risk tag, and notional exposure.
- `exchange_rates`
  Stores the FX rates used during a batch so historical JPY conversions remain traceable.
- `theme_mappings`
  Stores editable symbol-to-theme mappings with display name, color, and enabled flag.
- `sync_errors`
  Stores partial failures and field-level sync issues for later inspection and batch status summarization.

### Persistence Rules

- Snapshot data is append-only. Existing historical batches are never mutated in MVP.
- Each sync writes one logical batch and all child rows under the same `batch_id`.
- SQLite writes happen inside a single transaction. If persistence fails, the full batch rolls back.
- `theme_mappings` is updated independently from sync batches and remains editable at any time.

### Status Rules

- `success`
  All intended accounts and data categories were synced and persisted.
- `partial_success`
  At least one account succeeded, but one or more accounts or fields failed.
- `failed`
  No usable account data was produced, or SQLite persistence failed before commit.

## Standard Internal Models

The app will standardize raw moomoo data before it reaches repositories or APIs.

### Batch Model

`SnapshotBatch` stores:

- `id`
- `snapshot_time`
- `trigger_type`
- `status`
- `base_currency`
- `total_assets_jpy`
- `total_pnl_jpy`
- `daily_pnl_jpy`
- `error_summary`
- `created_at`

### Account Model

`AccountSnapshot` stores:

- `batch_id`
- `account_id`
- `account_name`
- `market`
- `account_type`
- `currency`
- `total_assets_original`
- `total_assets_jpy`
- `cash_original`
- `cash_jpy`
- `total_pnl_original`
- `total_pnl_jpy`
- `daily_pnl_original`
- `daily_pnl_jpy`
- `margin_used_jpy`
- `financing_amount_jpy`
- `buying_power_jpy`

### Position Model

`PositionSnapshot` stores:

- `batch_id`
- `account_id`
- `symbol`
- `raw_code`
- `name`
- `market`
- `asset_type`
- `currency`
- `quantity`
- `average_cost`
- `latest_price`
- `market_value_original`
- `market_value_jpy`
- `pnl_original`
- `pnl_jpy`
- `pnl_ratio`
- `position_ratio`

### Option Model

`OptionSnapshot` stores:

- `batch_id`
- `account_id`
- `contract_code`
- `underlying`
- `option_type`
- `side`
- `strike`
- `expiry`
- `quantity`
- `premium`
- `contract_multiplier`
- `market_value_jpy`
- `notional_exposure_jpy`
- `risk_tag`
- `parse_status`
- `raw_contract`

### Theme Mapping Model

`ThemeMapping` stores:

- `symbol`
- `theme`
- `display_name`
- `color`
- `enabled`
- `updated_at`

## Real OpenD Sync Design

The MVP sync path uses a real OpenD connection from the first implementation. There is no fake sync path standing in for production behavior.

### Sync Flow

1. Receive manual or scheduled sync request.
2. Acquire in-process sync lock.
3. Create a moomoo trade context and connect to OpenD.
4. Discover accounts with `get_acc_list`.
5. Filter accounts using local account configuration rules if present.
6. For each account:
   - Fetch account data with `accinfo_query`.
   - Fetch positions with `position_list_query`.
   - Split general positions and option positions.
   - Normalize all rows through adapters.
7. Aggregate batch totals and collect sync errors.
8. Write batch, accounts, positions, options, rates, and errors inside one SQLite transaction.
9. Release sync lock.
10. Return batch result to the API caller.

### Account Identity Rules

- `acc_id` is the durable account identifier.
- `acc_index` is never used as the long-term primary key.
- Local display names can be layered on top of raw account IDs.

### FX Rules

- JPY is the dashboard base currency.
- If moomoo provides a usable FX rate, the app stores both original and JPY values.
- If FX is missing, original currency values are still stored and JPY fields remain null.
- Missing FX is recorded in `sync_errors`.
- No external FX fallback is used in MVP.

### Option Parsing Rules

Options are preserved both as general positions and as specialized option rows.

- `quantity > 0` maps to `LONG`
- `quantity < 0` maps to `SHORT`
- `PUT + SHORT` maps to `short_put`
- `CALL + SHORT` maps to `short_call`
- `CALL + LONG` maps to `long_call`
- `PUT + LONG` maps to `long_put`
- Parsing failures keep the raw contract payload and use `parse_status = failed`

### Error Handling

- OpenD unavailable:
  sync request fails and no batch is written.
- Account list unavailable:
  sync request fails and no batch is written.
- One account fails:
  other accounts may still succeed, and the batch becomes `partial_success`.
- SQLite write fails:
  the transaction rolls back and the sync request returns failure.
- Missing fields:
  the app preserves whatever valid data exists and records field errors without inventing replacement values.

## API Design

The MVP API surface is intentionally small and centered on one dashboard page plus theme editing.

### `GET /api/snapshots`

Returns snapshot batch options for the history selector.

Each item includes:

- `batch_id`
- `snapshot_time`
- `trigger_type`
- `status`
- `total_assets_jpy`
- `total_pnl_jpy`
- `daily_pnl_jpy`
- `error_summary`

Behavior:

- Ordered by newest first.
- Includes `success` and `partial_success` batches.

### `GET /api/dashboard`

Query parameter:

- `batch_id` optional; defaults to the latest usable batch.

Returns one composite dashboard payload with these sections:

- `summary`
  Total assets, total PnL, daily PnL, stock/option/cash mix, batch time, and batch status.
- `treemap`
  Position nodes aggregated for the treemap.
- `themes`
  Theme-grouped exposure cards built from positions plus `theme_mappings`.
- `performance`
  Historical time series for total assets, cumulative PnL, and daily PnL.
- `options`
  Parsed option risk rows for the selected batch.

Behavior:

- Returns `404` if a requested `batch_id` does not exist.
- Returns the latest usable batch if `batch_id` is absent.

### `POST /api/sync/run`

Triggers one manual sync and waits for completion.

Returns:

- `batch_id`
- `status`
- `snapshot_time`
- `accounts_total`
- `accounts_succeeded`
- `accounts_failed`
- `message`

Behavior:

- Returns `409` if another sync is already running.
- Returns `502` if OpenD connection or account discovery fails.
- Returns `500` if SQLite persistence fails.
- Returns `200` for both `success` and `partial_success`, with status details in the body.

### `GET /api/themes`

Returns all current theme mappings for the editor UI.

### `POST /api/themes`

Creates or updates a single mapping keyed by `symbol`.

Editable fields:

- `symbol`
- `theme`
- `display_name`
- `color`
- `enabled`

Behavior:

- Upsert by `symbol`
- Allows soft disable with `enabled = 0`

## Frontend Design

The frontend is a static single-page dashboard served by FastAPI. It uses browser JavaScript to call backend APIs and re-render view sections.

### Page Layout

- Top control bar
  Manual sync button, snapshot selector, last sync time, and status banner.
- Overview cards
  Total assets, total PnL, daily PnL, stock ratio, option ratio, and cash ratio.
- Portfolio treemap
  Position-size visualization using `market_value_jpy`.
- Theme section
  Theme exposure cards and symbol lists based on editable mappings.
- Performance section
  Curves for total assets, cumulative PnL, and daily PnL.
- Options table
  Contract-level option risk rows with emphasis on short puts and other high-risk tags.

### Empty and Error States

- No snapshots:
  show a call to sync from OpenD first.
- Partial success:
  show a warning banner while still rendering usable data.
- Missing performance history:
  show a data-insufficient state when fewer than two usable batches exist.
- Dashboard read error:
  keep the page shell and display a retry prompt.

### Theme Editing UX

Theme editing is included in MVP and will be handled in a lightweight modal instead of a separate page.

The modal supports:

- Listing all mappings
- Creating a new mapping row
- Editing existing rows
- Saving `symbol`, `theme`, `display_name`, `color`, and `enabled`
- Refreshing dashboard data after save

The goal is to keep theme curation inside the same working flow as portfolio review.

## Scheduling Design

Daily scheduling is intentionally deferred until the manual sync path is stable. Once added, it should reuse the same sync service rather than introduce a second data path.

### Scheduler Rules

- Run daily at `07:00` in `Asia/Tokyo`
- Use `trigger_type = scheduled`
- Skip if a sync is already in progress
- Skip if the same calendar day already has a successful scheduled batch
- Reuse the same service path as manual sync

### Why Scheduling Comes Later

- Real OpenD reliability must be proven first.
- Sync status, rollback behavior, and partial-success handling should be validated manually before automation.
- Scheduling should remain a thin wrapper around a trusted sync core.

## Testing Strategy

The MVP uses automated tests for deterministic internal logic and manual validation for the live OpenD integration.

### Automated Tests

- Repository tests
  Schema initialization, inserts, queries, and transaction rollback behavior.
- Adapter tests
  Field mapping, asset classification, FX conversion, and option parsing.
- Service tests
  Batch aggregation, status derivation, partial-success handling, and error summaries.
- API tests
  Snapshot list, dashboard response shaping, manual sync endpoint behavior, and theme upsert behavior.

### Manual Validation

With OpenD running locally:

1. Trigger a manual sync.
2. Confirm a batch row is written.
3. Confirm account snapshots are written.
4. Confirm positions and options are written.
5. Confirm the dashboard API returns a usable payload.
6. Confirm the frontend renders the new batch.

## Implementation Sequence

The implementation will follow this order:

1. Backend data foundation
   SQLite schema, models, repository, and migration script.
2. Smallest real moomoo sync loop
   Connect OpenD, get accounts, fetch account balances, fetch positions, and persist snapshots.
3. Dashboard APIs
   `GET /api/snapshots`, `GET /api/dashboard`, `POST /api/sync/run`, and theme APIs.
4. Frontend dashboard
   Overview cards, treemap, themes, performance curves, and options table.
5. Daily scheduling
   Add `07:00` JST sync only after manual sync is proven stable.

## Risks and Mitigations

### OpenD Availability

Risk:
OpenD may not be running, logged in, or permissioned correctly.

Mitigation:
Fail fast with clear sync errors and do not write partial empty batches when account discovery cannot complete.

### Field Variability in moomoo Responses

Risk:
Different accounts or markets may omit fields or shape rows differently.

Mitigation:
Isolate raw-field handling in adapters, allow nullable standardized fields where appropriate, and record missing-field issues in `sync_errors`.

### Batch Integrity

Risk:
A persistence failure could create incomplete snapshots.

Mitigation:
Use one SQLite transaction per batch and roll back on any write failure.

### Concurrency

Risk:
Manual and scheduled syncs could overlap and corrupt data flow.

Mitigation:
Use one process-local sync lock and return `409` for overlapping manual requests.

### Frontend Complexity

Risk:
A no-framework frontend can sprawl if responsibilities are unclear.

Mitigation:
Keep the frontend single-page, API-driven, and organized by dashboard sections rather than generic utilities.

## Acceptance Criteria

The MVP is considered ready for the next iteration when all of the following are true:

- A real OpenD connection can be used to run a manual sync.
- A sync batch writes accounts, positions, options, FX rows, and errors into SQLite under one `batch_id`.
- `GET /api/snapshots` lists usable historical batches.
- `GET /api/dashboard` returns a complete dashboard payload for the latest or selected batch.
- `POST /api/sync/run` triggers a manual sync and returns success or partial-success details.
- Theme mappings can be created or edited from the UI and are reflected in the dashboard.
- The dashboard page renders overview cards, treemap, theme exposure, performance history, and option risk.
- Scheduled `07:00` JST sync is added only after the manual sync path has been verified stable.
