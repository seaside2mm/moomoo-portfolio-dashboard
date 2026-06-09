const currencyFormatter = new Intl.NumberFormat("ja-JP", {
  style: "currency",
  currency: "JPY",
  maximumFractionDigits: 0
});

const summary = document.querySelector("#summary");
const treemap = document.querySelector("#treemap");
const sectorAllocation = document.querySelector("#sectorAllocation");
const themes = document.querySelector("#themes");
const options = document.querySelector("#options");
const performance = document.querySelector("#performance");
const statusBanner = document.querySelector("#statusBanner");
const snapshotSelect = document.querySelector("#snapshotSelect");
const snapshotMeta = document.querySelector("#snapshotMeta");
const heroScore = document.querySelector("#heroScore");
const formulaBar = document.querySelector("#formulaBar");
const syncButton = document.querySelector("#syncButton");
const themeModal = document.querySelector("#themeModal");
const themeModalButton = document.querySelector("#themeModalButton");
const saveThemeButton = document.querySelector("#saveThemeButton");
const themeSymbol = document.querySelector("#themeSymbol");
const themeName = document.querySelector("#themeName");
const themeDisplayName = document.querySelector("#themeDisplayName");
const themeColor = document.querySelector("#themeColor");
const themeTable = document.querySelector("#themeTable");
let activeDashboardData = null;

const runtimeConfig = window.PORTFOLIO_DASHBOARD_CONFIG || {};
const apiBaseUrl = String(runtimeConfig.apiBaseUrl || "").replace(/\/$/, "");
const isReadOnlyFrontend = Boolean(runtimeConfig.readOnly);

function apiUrl(path) {
  return `${apiBaseUrl}${path}`;
}

const sectorStyles = {
  "太空": { color: "#ff2c93", icon: "⌁" },
  "AI基建": { color: "#19c7e5", icon: "◎" },
  "AI应用": { color: "#2ee6ca", icon: "◉" },
  "光通讯": { color: "#b75cff", icon: "◐" },
  "物理AI": { color: "#35e081", icon: "✦" },
  "存储": { color: "#7dd3fc", icon: "▤" },
  "芯片": { color: "#4fc3ff", icon: "◫" },
  "ETF": { color: "#ffd34d", icon: "★" },
  "日股": { color: "#ff7a3d", icon: "円" },
  "能源": { color: "#7ed957", icon: "⚡" },
  "防御": { color: "#f28c38", icon: "⛨" },
  "医疗": { color: "#35e081", icon: "+" },
  "金融服务": { color: "#ff951b", icon: "₿" },
  "杠杆与方向仓位": { color: "#f0b54a", icon: "⇄" },
  "未分类": { color: "#858da8", icon: "?" }
};

const fallbackSectorColors = ["#ff2c93", "#19c7e5", "#2ee6ca", "#b75cff", "#35e081", "#ff951b", "#ffd34d"];

function getSectorStyle(theme, index = 0) {
  return sectorStyles[theme] || {
    color: fallbackSectorColors[index % fallbackSectorColors.length],
    icon: "◆"
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(apiUrl(url), options);
  if (!response.ok) {
    const text = await response.text();
    try {
      const payload = JSON.parse(text);
      throw new Error(payload.detail || text);
    } catch (error) {
      if (error instanceof SyntaxError) {
        throw new Error(text);
      }
      throw error;
    }
  }
  return response.json();
}

function showStatus(message, warning = false) {
  if (!message) {
    statusBanner.classList.add("hidden");
    statusBanner.textContent = "";
    return;
  }
  statusBanner.classList.remove("hidden");
  statusBanner.textContent = message;
  statusBanner.style.borderColor = warning ? "var(--amber)" : "var(--green)";
}

function numberOrZero(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function percent(value, total) {
  const base = numberOrZero(total);
  if (!base) {
    return 0;
  }
  return (numberOrZero(value) / base) * 100;
}

function formatPercent(value, signed = false) {
  const absolute = Math.abs(value);
  let normalized = Math.round(value);
  if (absolute > 0 && absolute < 0.1) {
    normalized = Math.round(value * 100) / 100;
  } else if (absolute < 10) {
    normalized = Math.round(value * 10) / 10;
  }
  const prefix = signed && normalized > 0 ? "+" : "";
  return `${prefix}${normalized}%`;
}

function compactCurrency(value) {
  const amount = numberOrZero(value);
  if (Math.abs(amount) >= 100000000) {
    return `${Math.round(amount / 10000000) / 10}亿 JPY`;
  }
  if (Math.abs(amount) >= 10000) {
    return `${Math.round(amount / 10000)}万 JPY`;
  }
  return currencyFormatter.format(amount);
}

function formatDateLabel(value) {
  if (!value) {
    return "--";
  }
  const datePart = String(value).split("T")[0];
  const [, month, day] = datePart.split("-");
  return month && day ? `${Number(month)}/${Number(day)}` : datePart;
}

function buildTreemapLayout(items, bounds) {
  if (!items.length || bounds.width <= 0 || bounds.height <= 0) {
    return [];
  }
  if (items.length === 1) {
    return [{ ...items[0], ...bounds }];
  }

  const total = items.reduce((sum, item) => sum + item.absoluteValue, 0);
  let splitIndex = 1;
  let running = 0;
  let bestDistance = Infinity;
  for (let index = 0; index < items.length - 1; index += 1) {
    running += items[index].absoluteValue;
    const distance = Math.abs(total / 2 - running);
    if (distance <= bestDistance) {
      bestDistance = distance;
      splitIndex = index + 1;
    }
  }

  const first = items.slice(0, splitIndex);
  const second = items.slice(splitIndex);
  const firstTotal = first.reduce((sum, item) => sum + item.absoluteValue, 0);
  const firstRatio = total ? firstTotal / total : 0;

  if (bounds.width >= bounds.height) {
    const firstWidth = Math.round(bounds.width * firstRatio);
    return [
      ...buildTreemapLayout(first, { x: bounds.x, y: bounds.y, width: firstWidth, height: bounds.height }),
      ...buildTreemapLayout(second, {
        x: bounds.x + firstWidth,
        y: bounds.y,
        width: bounds.width - firstWidth,
        height: bounds.height
      })
    ];
  }

  const firstHeight = Math.round(bounds.height * firstRatio);
  return [
    ...buildTreemapLayout(first, { x: bounds.x, y: bounds.y, width: bounds.width, height: firstHeight }),
    ...buildTreemapLayout(second, {
      x: bounds.x,
      y: bounds.y + firstHeight,
      width: bounds.width,
      height: bounds.height - firstHeight
    })
  ];
}

function buildDailyPerformance(data) {
  const principal = numberOrZero(data.summary?.principal_basis_jpy);
  const byDate = new Map();
  for (const row of data.performance || []) {
    const assets = numberOrZero(row.total_assets_jpy);
    if (!assets) {
      continue;
    }
    const dateKey = String(row.snapshot_time || "").split("T")[0];
    const current = byDate.get(dateKey);
    if (!current || String(row.snapshot_time) > String(current.snapshot_time)) {
      byDate.set(dateKey, row);
    }
  }
  return [...byDate.values()]
    .sort((a, b) => String(a.snapshot_time).localeCompare(String(b.snapshot_time)))
    .map((row) => {
      const assets = numberOrZero(row.total_assets_jpy);
      return {
        snapshotTime: row.snapshot_time,
        label: formatDateLabel(row.snapshot_time),
        assets,
        returnRate: principal > 0 ? ((assets - principal) / principal) * 100 : null
      };
    });
}

function scaleValue(value, min, max, start, end) {
  if (max === min) {
    return (start + end) / 2;
  }
  return start + ((value - min) / (max - min)) * (end - start);
}

function padDomain(values, ratio = 0.12) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) {
    const fallback = Math.max(Math.abs(min) * ratio, 1);
    return [min - fallback, max + fallback];
  }
  const padding = (max - min) * ratio;
  return [min - padding, max + padding];
}

function linePath(points) {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");
}

function formatOptionExpiry(value) {
  if (!value) {
    return "--";
  }
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("en-US", {
    month: "short",
    year: "numeric"
  }).toUpperCase();
}

function formatOptionStrike(value) {
  const strike = numberOrZero(value);
  if (!strike) {
    return "--";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: strike % 1 === 0 ? 0 : 2
  }).format(strike);
}

function translateRiskTag(tag) {
  const labels = {
    short_put: "卖出看跌",
    short_call: "卖出看涨",
    long_call: "买入看涨",
    long_put: "买入看跌"
  };
  return labels[tag] || tag || "--";
}

function renderSummary(data) {
  const total = numberOrZero(data.summary.total_assets_jpy);
  const stock = numberOrZero(data.asset_allocation.stock);
  const option = numberOrZero(data.asset_allocation.option);
  const cash = numberOrZero(data.asset_allocation.cash);
  const residual = total - stock - option - cash;
  const liquidity = cash + residual;
  const stockPct = percent(stock, total);
  const optionPct = percent(option, total);
  const liquidityPct = percent(liquidity, total);
  const cumulativeReturnRate = Number(data.summary.cumulative_return_rate);
  const cards = [
    { label: "净值", value: "100%", caption: compactCurrency(total), accent: "var(--green)" },
    { label: "股票", value: formatPercent(stockPct), caption: compactCurrency(stock), accent: "var(--cyan)" },
    { label: "期权", value: formatPercent(optionPct), caption: compactCurrency(option), accent: optionPct < 0 ? "var(--amber)" : "var(--danger)" },
    { label: "现金/其他", value: formatPercent(liquidityPct), caption: compactCurrency(liquidity), accent: "#d9dcff" }
  ];
  summary.innerHTML = cards.map((card) => `
    <article class="card" style="--accent:${card.accent}">
      <span class="muted">${card.label}</span>
      <strong>${card.value}</strong>
      <small>${card.caption}</small>
    </article>
  `).join("");

  heroScore.textContent = Number.isFinite(cumulativeReturnRate)
    ? formatPercent(cumulativeReturnRate * 100, true)
    : "--";
  formulaBar.innerHTML = `
    <strong>${formatPercent(stockPct)}</strong>
    <span>股票</span>
    <span>+</span>
    <strong class="${optionPct < 0 ? "warn" : "pos"}">${formatPercent(optionPct, true)}</strong>
    <span>期权</span>
    <span>+</span>
    <strong>${formatPercent(liquidityPct)}</strong>
    <span>现金/其他</span>
    <span>=</span>
    <strong class="eq">100% 净值</strong>
  `;
}

function renderTreemap(data) {
  const palette = ["#ff1f86", "#f03eb3", "#15abc2", "#32c7b9", "#36d7e8", "#a556f6", "#bb6cf0", "#21bc5b", "#ff9718", "#f7c948"];
  const rows = data.treemap
    .filter((row) => row.asset_type !== "option" && row.asset_type !== "cash")
    .map((row) => ({
      ...row,
      absoluteValue: numberOrZero(row.market_value_jpy)
    }))
    .filter((row) => row.absoluteValue > 0)
    .sort((a, b) => b.absoluteValue - a.absoluteValue);
  const total = rows.reduce((sum, row) => sum + row.absoluteValue, 0);
  const totalAssets = numberOrZero(data.summary?.total_assets_jpy);
  const width = Math.max(treemap.clientWidth, 320);
  const height = Math.max(treemap.clientHeight, width < 720 ? 430 : 560);
  const layout = buildTreemapLayout(rows, { x: 0, y: 0, width, height });

  treemap.innerHTML = layout
    .map((row, index) => {
      const totalAssetShare = percent(row.market_value_jpy, totalAssets);
      const compactClass = row.width < 130 || row.height < 96 ? " tile-compact" : "";
      const tinyClass = row.width < 86 || row.height < 68 ? " tile-tiny" : "";
      return `
        <div class="tile${compactClass}${tinyClass}" title="${row.symbol} · ${row.sector_name || "未分类"} · 总资产占比 ${formatPercent(totalAssetShare)} · ${compactCurrency(row.market_value_jpy)}" style="left:${row.x}px; top:${row.y}px; width:${row.width}px; height:${row.height}px; background:${palette[index % palette.length]}">
          <div class="tile-symbol">${row.symbol}</div>
          <div class="tile-share">${formatPercent(totalAssetShare)}</div>
        </div>
      `;
    }).join("") || `<p class="muted">当前快照无股票持仓</p>`;
}

function buildSectorAllocation(data) {
  const grouped = new Map();
  const totalAssets = numberOrZero(data.summary?.total_assets_jpy);
  for (const row of data.treemap || []) {
    const sectorName = row.sector_name || "未分类";
    const marketValue = numberOrZero(row.market_value_jpy);
    if (marketValue <= 0) {
      continue;
    }
    const current = grouped.get(sectorName) || 0;
    grouped.set(sectorName, current + marketValue);
  }
  const sectorTotal = [...grouped.values()].reduce((sum, value) => sum + value, 0);
  return [...grouped.entries()]
    .map(([theme, marketValue]) => ({
      theme,
      marketValue,
      share: totalAssets ? (marketValue / totalAssets) * 100 : 0,
      barShare: sectorTotal ? (marketValue / sectorTotal) * 100 : 0
    }))
    .sort((a, b) => b.marketValue - a.marketValue);
}

function getSectorAllocationLookup(data) {
  return new Map(buildSectorAllocation(data).map((row) => [row.theme, row]));
}

function renderSectorAllocation(data) {
  const rows = buildSectorAllocation(data);
  if (!rows.length) {
    sectorAllocation.innerHTML = `<p class="muted">暂无多头板块配置</p>`;
    return;
  }

  sectorAllocation.innerHTML = `
    <div class="sector-stack" aria-label="多头板块配置">
      ${rows.map((row, index) => {
        const style = getSectorStyle(row.theme, index);
        const compactClass = row.barShare < 3 ? " sector-segment-compact" : "";
        const label = `${row.theme} ${formatPercent(row.share)}`;
        return `
          <div class="sector-segment${compactClass}" title="${label} · ${compactCurrency(row.marketValue)}" style="--sector:${style.color}; width:${Math.max(row.barShare, 1.6)}%">
            <span>${label}</span>
          </div>
        `;
      }).join("")}
    </div>
    <div class="sector-legend">
      ${rows.map((row, index) => {
        const style = getSectorStyle(row.theme, index);
        return `
          <span class="sector-legend-item" title="${row.theme} · ${compactCurrency(row.marketValue)}">
            <i style="--sector:${style.color}"></i>
            <b>${row.theme}</b>
            <strong>${formatPercent(row.share)}</strong>
          </span>
        `;
      }).join("")}
    </div>
  `;
}

function renderThemes(data) {
  const allocationLookup = getSectorAllocationLookup(data);
  const totalAssets = numberOrZero(data.summary?.total_assets_jpy);
  themes.innerHTML = data.themes.map((row, index) => {
    const style = getSectorStyle(row.theme, index);
    const allocation = allocationLookup.get(row.theme);
    const share = allocation?.share ?? 0;
    const positions = row.positions || [];
    const maxPositionValue = Math.max(...positions.map((position) => Math.abs(numberOrZero(position.market_value_jpy))), 1);
    const cardClass = row.layout === "special-strip" ? "sector-card sector-card-special" : "sector-card";
    return `
      <article class="${cardClass}" style="--sector:${style.color}">
        <div class="sector-head">
          <div class="sector-title">
            <span class="sector-icon">${style.icon}</span>
            <strong>${row.theme}</strong>
          </div>
          <strong class="sector-percent">${formatPercent(share)}</strong>
        </div>
        <div class="sector-meter"><span style="width:${Math.min(Math.abs(share), 100)}%"></span></div>
        <div class="sector-positions">
          ${positions.map((position) => {
            const positionValue = numberOrZero(position.market_value_jpy);
            const rowSize = Math.max((Math.abs(positionValue) / maxPositionValue) * 100, 8);
            return `
            <div class="sector-row" style="--row-size:${Math.min(rowSize, 100)}%">
              <span>
                <b>${position.symbol}</b>
                ${position.description ? `<small>${position.description}</small>` : ""}
              </span>
              <strong class="${positionValue < 0 ? "negative" : ""}">${formatPercent(percent(positionValue, totalAssets), true)}</strong>
            </div>
          `}).join("")}
        </div>
      </article>
    `;
  }).join("") || `<p class="muted">暂无板块配置</p>`;
}

function renderOptions(data) {
  if (!data.options.length) {
    options.innerHTML = `<p class="muted">当前快照无期权持仓</p>`;
    return;
  }
  options.innerHTML = `
    <div class="option-board">
      <div class="option-board-head">
        <span>标的</span>
        <span>类型</span>
        <span>行权价</span>
        <span>到期</span>
      </div>
      ${data.options.map((row) => `
        <div class="option-board-row">
          <strong>${row.underlying || row.contract_code}</strong>
          <span><em class="option-badge">${translateRiskTag(row.risk_tag)}</em></span>
          <span>${formatOptionStrike(row.strike)}</span>
          <span>${formatOptionExpiry(row.expiry)}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function renderPerformance(data) {
  const rows = buildDailyPerformance(data);
  if (!rows.length) {
    performance.innerHTML = `<p class="muted">至少需要一个历史快照</p>`;
    return;
  }

  const width = 980;
  const height = 300;
  const padding = { top: 26, right: 74, bottom: 42, left: 74 };
  const assetValues = rows.map((row) => row.assets);
  const returnValues = rows
    .map((row) => row.returnRate)
    .filter((value) => value !== null && Number.isFinite(value));
  const [assetMin, assetMax] = padDomain(assetValues);
  const [returnMin, returnMax] = padDomain(returnValues.length ? returnValues : [0]);
  const latest = rows[rows.length - 1];
  const first = rows[0];
  const xForIndex = (index) => rows.length === 1
    ? (padding.left + width - padding.right) / 2
    : scaleValue(index, 0, rows.length - 1, padding.left, width - padding.right);
  const assetPoints = rows.map((row, index) => ({
    ...row,
    x: xForIndex(index),
    y: scaleValue(row.assets, assetMin, assetMax, height - padding.bottom, padding.top)
  }));
  const returnPoints = rows
    .filter((row) => row.returnRate !== null && Number.isFinite(row.returnRate))
    .map((row, index) => ({
      ...row,
      x: xForIndex(rows.indexOf(row)),
      y: scaleValue(row.returnRate, returnMin, returnMax, height - padding.bottom, padding.top)
    }));
  const assetDelta = latest.assets - first.assets;
  const chartGrid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = padding.top + (height - padding.top - padding.bottom) * ratio;
    const assetLabel = compactCurrency(scaleValue(ratio, 1, 0, assetMin, assetMax));
    const returnLabel = formatPercent(scaleValue(ratio, 1, 0, returnMin, returnMax));
    return { y, assetLabel, returnLabel };
  });

  performance.innerHTML = `
    <div class="performance-chart">
      <div class="performance-stats">
        <article>
          <span>最新资金</span>
          <strong>${compactCurrency(latest.assets)}</strong>
          <small class="${assetDelta >= 0 ? "positive" : "negative"}">${assetDelta >= 0 ? "+" : ""}${compactCurrency(assetDelta)} 较首日</small>
        </article>
        <article>
          <span>累计收益率</span>
          <strong class="${numberOrZero(latest.returnRate) >= 0 ? "positive" : "negative"}">${latest.returnRate === null ? "--" : formatPercent(latest.returnRate, true)}</strong>
          <small>本金基准 ${compactCurrency(data.summary?.principal_basis_jpy)}</small>
        </article>
      </div>
      <svg class="performance-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="资金和收益率曲线">
        <defs>
          <linearGradient id="assetFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stop-color="rgba(25, 199, 229, 0.28)" />
            <stop offset="100%" stop-color="rgba(25, 199, 229, 0)" />
          </linearGradient>
        </defs>
        ${chartGrid.map((line) => `
          <g class="chart-gridline">
            <line x1="${padding.left}" x2="${width - padding.right}" y1="${line.y.toFixed(1)}" y2="${line.y.toFixed(1)}" />
            <text x="${padding.left - 10}" y="${line.y + 4}" text-anchor="end">${line.assetLabel}</text>
            <text x="${width - padding.right + 10}" y="${line.y + 4}">${line.returnLabel}</text>
          </g>
        `).join("")}
        <path class="asset-area" d="${linePath(assetPoints)} L ${assetPoints.at(-1).x.toFixed(1)} ${height - padding.bottom} L ${assetPoints[0].x.toFixed(1)} ${height - padding.bottom} Z" />
        <path class="asset-line" d="${linePath(assetPoints)}" />
        ${returnPoints.length ? `<path class="return-line" d="${linePath(returnPoints)}" />` : ""}
        ${assetPoints.map((point) => `
          <circle class="asset-dot" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4">
            <title>${point.label} · 资金 ${compactCurrency(point.assets)}</title>
          </circle>
        `).join("")}
        ${returnPoints.map((point) => `
          <circle class="return-dot" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4">
            <title>${point.label} · 收益率 ${formatPercent(point.returnRate, true)}</title>
          </circle>
        `).join("")}
        ${assetPoints.map((point, index) => `
          <text class="chart-xlabel" x="${point.x.toFixed(1)}" y="${height - 12}" text-anchor="${index === 0 ? "start" : index === assetPoints.length - 1 ? "end" : "middle"}">${point.label}</text>
        `).join("")}
      </svg>
      <div class="chart-legend">
        <span><i class="asset"></i>资金</span>
        <span><i class="return"></i>收益率</span>
      </div>
    </div>
    <div class="performance-points">
      ${rows.map((row) => `
        <div class="performance-point">
          <strong>${row.label}</strong>
          <span>${compactCurrency(row.assets)}</span>
          <em class="${numberOrZero(row.returnRate) >= 0 ? "positive" : "negative"}">${row.returnRate === null ? "--" : formatPercent(row.returnRate, true)}</em>
        </div>
      `).join("")}
    </div>
  `;
}

async function loadSnapshots() {
  const snapshots = await fetchJson("/api/snapshots");
  snapshotSelect.innerHTML = snapshots.map((row) => `
    <option value="${row.id}">${row.snapshot_time} · ${row.status}</option>
  `).join("");
  if (snapshots.length > 0) {
    snapshotSelect.value = snapshots[0].id;
    await loadDashboard(snapshots[0].id);
  }
}

async function loadDashboard(batchId) {
  const data = await fetchJson(`/api/dashboard?batch_id=${batchId}`);
  activeDashboardData = data;
  const stockCount = data.treemap.length;
  snapshotMeta.textContent = `按板块分类的多头仓位 · ${stockCount} 个标的 · ${data.themes.length || 0} 大板块`;
  renderSummary(data);
  renderTreemap(data);
  renderSectorAllocation(data);
  renderThemes(data);
  renderOptions(data);
  renderPerformance(data);
  showStatus(data.summary.status === "partial_success" ? data.summary.error_summary : "", data.summary.status === "partial_success");
}

window.addEventListener("resize", () => {
  if (activeDashboardData) {
    renderTreemap(activeDashboardData);
  }
});

async function loadThemes() {
  const mappings = await fetchJson("/api/themes");
  themeTable.innerHTML = mappings.map((row) => `
    <div class="row">
      <strong>${row.symbol}</strong>
      <span>${row.theme}</span>
    </div>
  `).join("") || `<p class="muted">暂无主题配置</p>`;
}

syncButton.addEventListener("click", async () => {
  syncButton.disabled = true;
  showStatus("正在同步账户数据", true);
  try {
    const result = await fetchJson("/api/sync/run", { method: "POST" });
    await loadSnapshots();
    snapshotSelect.value = String(result.batch_id);
    await loadDashboard(result.batch_id);
    showStatus("同步完成，已生成新快照", false);
  } catch (error) {
    const message = error.message === "sync already running"
      ? "已有同步任务正在运行，请稍等一会儿再试"
      : `同步失败：${error.message || "请检查 moomoo OpenD 状态"}`;
    showStatus(message, true);
  } finally {
    syncButton.disabled = false;
  }
});

snapshotSelect.addEventListener("change", async () => {
  if (snapshotSelect.value) {
    await loadDashboard(snapshotSelect.value);
  }
});

themeModalButton.addEventListener("click", async () => {
  await loadThemes();
  themeModal.showModal();
});

saveThemeButton.addEventListener("click", async () => {
  const payload = {
    symbol: themeSymbol.value.trim().toUpperCase(),
    theme: themeName.value.trim(),
    display_name: themeDisplayName.value.trim() || null,
    color: themeColor.value.trim() || null,
    enabled: true
  };
  if (!payload.symbol || !payload.theme) {
    return;
  }
  await fetchJson("/api/themes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  await loadThemes();
  if (snapshotSelect.value) {
    await loadDashboard(snapshotSelect.value);
  }
});

loadSnapshots().catch(() => showStatus("暂无快照，请先同步 moomoo 账户数据", true));

if (isReadOnlyFrontend) {
  syncButton.hidden = true;
  themeModalButton.hidden = true;
}
