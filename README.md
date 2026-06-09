# 持仓看板

本项目是一个本地运行的 moomoo 持仓看板。它会直连真实 moomoo OpenD，读取账户、资金和持仓数据，写入本地 SQLite，再通过 FastAPI 提供 Dashboard API 和前端页面。

当前页面地址：

```text
http://127.0.0.1:8000/
```

## 项目环境

推荐运行环境：

```text
OS: Windows
Python: 3.11+
推荐解释器: C:\Python313\python.exe
项目目录: E:\000-VibeCoding\股票\00.持仓看板
数据库: data/portfolio.db
时区: Asia/Tokyo
OpenD Host: 127.0.0.1
OpenD Port: 11111
```

项目依赖声明在 `pyproject.toml`：

```text
fastapi>=0.115
uvicorn>=0.30
pydantic>=2.8
apscheduler>=3.10
moomoo-api>=0
pytest>=8.2
httpx>=0.27
```

注意：如果机器上同时存在 Conda Python 和系统 Python，建议显式使用 `C:\Python313\python.exe`，避免启动时找不到依赖。

## 第一次安装

进入项目目录：

```powershell
cd "E:\000-VibeCoding\股票\00.持仓看板"
```

安装项目和开发依赖：

```powershell
C:\Python313\python.exe -m pip install -e ".[dev]"
```

验证依赖和测试：

```powershell
C:\Python313\python.exe -m pytest
```

正常结果应类似：

```text
25 passed
```

## 启动 moomoo OpenD

本项目从第一版开始直连真实 OpenD，不使用模拟数据。

启动前请确认：

```text
moomoo OpenD 已打开
API 端口是 11111
账户有读取资金和持仓的权限
OpenD 页面显示已登录
```

当前配置在 `app/config.py`：

```text
moomoo_host = 127.0.0.1
moomoo_port = 11111
base_currency = JPY
database_path = data/portfolio.db
sync_hour = 7
sync_minute = 0
```

本应用只读取账户、资金和持仓，不执行解锁交易、下单或改仓操作。

## moomooID 与 OpenD 配置

当前 MVP 不需要在项目代码里配置 moomooID、手机号、邮箱或交易密码。

登录关系如下：

```text
moomooID / 登录态：保存在本机 moomoo OpenD 客户端中
本项目：只连接本机 OpenD API 端口 11111
```

也就是说，项目连接的是：

```text
127.0.0.1:11111
```

不是直接登录 moomoo 账号。

启动前需要在 moomoo OpenD 中完成：

```text
登录 moomooID
确认 API 端口为 11111
确认账户权限可读取资金和持仓
确认 OpenD 处于运行状态
```

不要提交到 GitHub 的内容：

```text
moomooID
手机号 / 邮箱
登录密码
交易密码
OpenD 解锁密码
真实账户快照数据库 data/portfolio.db
导出的 CSV 持仓数据 exports/
运行日志 logs/
```

这些路径已在 `.gitignore` 中排除：

```text
data/
logs/
exports/
.env
.env.*
```

如果未来要支持远程展示，推荐模式是：

```text
本地电脑：OpenD + 同步程序
云端：只读展示最后上传的快照
```

不要把 OpenD 的 `11111` 端口直接暴露到公网。

## 启动 Web 服务

开发模式启动：

```powershell
C:\Python313\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

普通模式启动：

```powershell
C:\Python313\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如果需要在后台保持运行，可以使用：

```powershell
Start-Process -FilePath C:\Python313\python.exe `
  -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') `
  -WorkingDirectory 'E:\000-VibeCoding\股票\00.持仓看板' `
  -WindowStyle Hidden
```

启动成功后，终端应看到：

```text
Uvicorn running on http://127.0.0.1:8000
```

## 打开预览

浏览器访问：

```text
http://127.0.0.1:8000/
```

健康检查：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/health -UseBasicParsing
```

正常返回：

```json
{"status":"ok"}
```

## 手动同步

页面点击“同步”，或者直接调用 API：

```powershell
Invoke-WebRequest -Method POST -Uri http://127.0.0.1:8000/api/sync/run -UseBasicParsing
```

同步流程：

```text
连接 OpenD
获取账户列表
跳过模拟账户
读取账户资金
读取账户持仓
解析期权合约
写入 SQLite 快照
刷新 Dashboard 数据
```

同步后的数据会写入：

```text
data/portfolio.db
```

## Dashboard API

获取快照列表：

```text
GET /api/snapshots
```

获取最新 Dashboard：

```text
GET /api/dashboard
```

按批次获取 Dashboard：

```text
GET /api/dashboard?batch_id=2
```

手动运行同步：

```text
POST /api/sync/run
```

主题配置：

```text
GET /api/themes
POST /api/themes
```

分类覆盖：

```text
GET /api/categories
GET /api/category-overrides
POST /api/category-overrides
```

## 股票与板块调整方法

Dashboard 的板块归类在后端完成，前端只展示 `/api/dashboard` 返回的结果。当前有两种调整方式。

### 方式一：修改自动分类规则

适合长期规则，例如某个股票以后都应固定归到某个板块。

规则文件：

```text
app/services/dashboard_service.py
```

修改 `AUTO_SECTOR_BY_SYMBOL`：

```python
AUTO_SECTOR_BY_SYMBOL = {
    "NVDA": ("chip", "芯片"),
    "AVGO": ("chip", "芯片"),
    "GLW": ("optical_communication", "光通讯"),
    "DELL": ("ai_infrastructure", "AI基建"),
}
```

格式说明：

```text
"股票代码": ("板块代码", "页面显示名称")
```

本次调整示例：

```text
AVGO -> 芯片
NVDA -> 芯片
GLW  -> 光通讯
DELL -> AI基建
```

改完后建议同步更新测试：

```text
tests/test_dashboard_service.py
```

验证规则函数：

```powershell
@'
from app.services.dashboard_service import resolve_auto_sector
for symbol in ["AVGO", "NVDA", "GLW", "DELL"]:
    print(symbol, resolve_auto_sector(symbol))
'@ | C:\Python313\python.exe -
```

运行测试：

```powershell
C:\Python313\python.exe -m pytest
```

如果 Web 服务已经启动，需要重启服务后新规则才会生效：

```powershell
C:\Python313\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 方式二：通过 API 做手动覆盖

适合临时调整、个别账户口径调整，或不想改代码的情况。

先查看可用分类：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/categories -UseBasicParsing
```

提交手动覆盖：

```powershell
$body = @{
  symbol = "NVDA"
  market = "US"
  sector_code = "semiconductor"
  industry_code = $null
  theme_code = $null
  reason = "manual override"
  enabled = $true
} | ConvertTo-Json

Invoke-WebRequest `
  -Method POST `
  -Uri http://127.0.0.1:8000/api/category-overrides `
  -ContentType "application/json" `
  -Body $body `
  -UseBasicParsing
```

查看已配置的手动覆盖：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/category-overrides -UseBasicParsing
```

优先级：

```text
手动覆盖 category-overrides
自动分类 AUTO_SECTOR_BY_SYMBOL
旧主题映射 theme_mappings
未分类
```

也就是说，如果同一个股票同时存在手动覆盖和自动规则，会优先使用手动覆盖。

### 验证页面分类

查看 Dashboard API 中某些股票的板块：

```powershell
@'
import json
from urllib.request import urlopen

with urlopen("http://127.0.0.1:8000/api/dashboard", timeout=10) as response:
    data = json.load(response)

for symbol in ["AVGO", "NVDA", "GLW", "DELL"]:
    rows = [row for row in data["positions"] if row["symbol"].upper() == symbol]
    for row in rows:
        print(symbol, row.get("sector_name"), row.get("category_source"))
'@ | C:\Python313\python.exe -
```

浏览器刷新：

```text
http://127.0.0.1:8000/
```

如果页面仍显示旧板块，通常是服务没重启，或浏览器缓存了旧页面。先重启 `uvicorn`，再强制刷新浏览器。

## 前端页面

当前前端是静态页面：

```text
app/static/index.html
app/static/styles.css
app/static/dashboard.js
```

页面包含：

```text
总览卡片
持仓树图
主题板块
收益曲线
期权表
手动同步按钮
主题配置弹窗
```

前端数据全部来自 `/api/dashboard`，不会写死持仓数据。

## v1.1.0 前端在线部署

v1.1.0 支持把前端静态页面部署到 GitHub Pages。

重要边界：

```text
在线前端只负责展示
OpenD 仍然在本地运行
云端前端不会直连 127.0.0.1:11111
```

部署后，前端需要访问一个云端只读 API：

```text
GET /api/snapshots
GET /api/dashboard
```

如果暂时还没有云端只读 API，GitHub Pages 页面可以打开，但无法加载真实快照数据。

### 本地构建静态前端

构建命令：

```powershell
C:\Python313\python.exe scripts\build_frontend.py `
  --api-base-url "https://your-api.example.com" `
  --read-only true
```

输出目录：

```text
dist/frontend
```

构建产物会包含：

```text
index.html
styles.css
dashboard.js
config.js
.nojekyll
```

`config.js` 中会写入在线 API 地址：

```javascript
window.PORTFOLIO_DASHBOARD_CONFIG = {
  apiBaseUrl: "https://your-api.example.com",
  readOnly: true
};
```

`readOnly = true` 时，前端会隐藏“同步”和“主题”按钮，避免在线页面误触本地同步能力。

### GitHub Pages 自动部署

仓库已包含 workflow：

```text
.github/workflows/deploy-frontend.yml
```

GitHub 仓库设置：

```text
Settings -> Pages -> Build and deployment -> Source -> GitHub Actions
```

仓库变量：

```text
Settings -> Secrets and variables -> Actions -> Variables
```

建议添加：

```text
FRONTEND_API_BASE_URL = https://your-api.example.com
FRONTEND_READ_ONLY = true
```

触发方式：

```text
推送 main 分支时自动部署
或在 Actions 页面手动运行 Deploy frontend
```

部署完成后，GitHub Actions 会给出 Pages URL。

### 与本地同步的关系

推荐架构：

```text
本地电脑：
OpenD -> 本地同步程序 -> SQLite -> 上传快照到云端只读 API

云端：
GitHub Pages 前端 -> 云端只读 API -> 展示快照
```

不要把 OpenD 的 `11111` 端口暴露到公网。

## 每日自动同步

应用启动时会尝试启用每日同步调度。

默认时间：

```text
07:00 JST
```

调度逻辑：

```text
每天检查是否已有成功的 scheduled 快照
如果没有，并且当前没有同步任务运行，则执行一次 scheduled 同步
```

如果 `apscheduler` 未安装，应用仍可启动，只是不会启用每日自动同步。安装依赖后即可恢复：

```powershell
C:\Python313\python.exe -m pip install apscheduler
```

## 常见问题

### 预览失败

先检查服务是否在监听 8000：

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

如果没有输出，说明 Web 服务没有启动。重新运行：

```powershell
C:\Python313\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

再检查健康接口：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/health -UseBasicParsing
```

### 端口被占用

查看占用端口的进程：

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object LocalAddress,LocalPort,State,OwningProcess
```

查看进程详情：

```powershell
Get-Process -Id <OwningProcess>
```

### 同步失败

确认 OpenD 已启动：

```text
OpenD 地址: 127.0.0.1
OpenD 端口: 11111
```

确认 moomoo 账户已登录，并且账户资金、持仓读取权限可用。

### 页面还是旧样式

浏览器可能缓存了静态资源。可以强制刷新页面，或检查 `index.html` 中的静态资源版本号：

```html
/static/styles.css?v=...
/static/dashboard.js?v=...
```

### 查看日志

如果使用后台启动并配置了重定向，日志通常在：

```text
logs/uvicorn.out.log
logs/uvicorn.err.log
```

## 当前开发计划

原始任务顺序：

```text
后端数据底座：SQLite 建表、模型、Repository、迁移脚本
moomoo 同步最小闭环：连接 OpenD、获取账户、拉资金、拉持仓、写入快照
Dashboard API：GET /snapshots、GET /dashboard、POST /sync/run
前端看板：总览卡片、持仓树图、主题板块、收益曲线、期权表
每日 07:00 JST 自动同步：手动同步稳定后再加调度
```

当前实现已经覆盖以上主线，后续改动应尽量沿着这条计划推进。
