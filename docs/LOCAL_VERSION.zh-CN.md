# PaperDaily 本地 / Standalone 版

PaperDaily 可以完全脱离 GitHub Actions 和 GitHub Pages 运行。普通 Windows 用户推荐使用冻结后的 standalone 版本：不需要安装 Python、不需要 Git，也不需要修改程序源码。

## Windows standalone

从 GitHub 最新 Release 下载 `PaperDaily-Windows.zip`，解压后主要是：

```text
PaperDaily-Windows/
├── PaperDaily.exe
├── config.yaml
├── api_token.txt
├── topics/
│   ├── sleep-homeostasis.yaml
│   └── eeg-methods.yaml
├── README.md
└── README.zh-CN.md
```

普通用户只需要修改配置文件，不需要碰源码：

- `config.yaml`：整个安装共用的 API、抓取数量、更新时间、主题和页面设置；
- `topics/*.yaml`：每个研究项目一个简短配置，包括检索词、prefilter、可选的独立数量参数和 AI interest profile；
- `api_token.txt`：第一行填写 AI API token。

之后双击 `PaperDaily.exe`。程序会自动创建自己的 `data/` 和 `site/` 运行目录，并用默认浏览器打开页面。

## 多研究主题

PaperDaily 0.6 支持一个安装同时维护多个研究项目。在 `config.yaml` 中启用：

```yaml
topics:
  enabled: true
  directory: topics
  default: sleep-homeostasis
```

主页和每日页面都会提供 Topic selector。一次 refresh 会先用所有启用 topic 的检索词建立共享 source query，每个外部来源只抓取一套数据并统一去重；随后再针对每个 topic 分别做 shortlist 和 AI relevance ranking。每个 topic 都有自己的每日 archive、Monthly Top 5 和 25 + additional papers 页面。

增加项目时复制一个现有 `topics/*.yaml` 即可。Standalone 运行期间，保存 `config.yaml` 或任意 `topics/*.yaml` 都会被 watcher 检测，并在 scheduled 模式下立即重新抓取和分析。

## 后台 Scheduler

默认配置：

```yaml
local:
  refresh_mode: scheduled
  refresh_times:
    - "05:30"
    - "20:30"
  scheduler_enabled: true
  scheduler_check_seconds: 30
  refresh_on_config_change: true
```

时间使用顶层 `timezone`。当前示例为 `Asia/Shanghai`，即北京时间。

启动时 PaperDaily 会判断当前时间之前最近一个应该完成的 refresh slot。如果该 slot 已记录在 `local_state.json`，就直接打开已有网页，不访问文献源，也不调用 AI；如果还没有成功运行，就先补跑一次。

程序保持运行时，后台 scheduler 会在未来的更新时间自动刷新。只有抓取和 AI 分析成功后才会记录该 slot；失败的任务不会被假装标记完成，而会稍后重试。

三种模式：

```yaml
refresh_mode: scheduled  # 推荐
refresh_mode: always     # 每次启动都刷新
refresh_mode: never      # 永远只看已有本地数据
```

## 版本更新提醒

每次真正开始抓取文献之前，standalone 会读取本仓库中的 `standalone_version.json`，并将安装包内的 `VERSION` 与最新版本比较。

如果有新版本，首页会显示更新提醒和下载入口；如果版本检查失败，文献抓取仍然继续，版本检查不会阻断 pipeline。

## 配色主题

Khaki、Black、Navy、Forest、Burgundy 等主题可以直接在页面中选择。`config.yaml` 只负责设置初始默认主题，也可以定义 custom palette。

## 费用显示

首页可以选择显示：

```text
Last run ¥... · Total ¥... · ~¥.../year
```

`Last run` 是最近一次独立 AI run 的费用；`Total` 是累计实际 API 支出；年化估算使用具有代表性的单次运行成本乘以每天配置的 refresh 次数。积累正常 scheduled 数据后，开发和调试运行不会进入年化参考成本。

费用后台仍然会记录，但页面**默认不显示**：

```yaml
site:
  show_billing: false
```

## 安全

API token 始终保留在 Python / EXE 侧，不会写入 HTML 或 JavaScript。不要分享自己的 `api_token.txt`。

正式 Windows standalone Release 不包含作者自己的历史文献数据、API token、GitHub secret，也不会暴露可编辑的 Python 源代码目录。

## Python 本地开发版

项目仍会提供 Python-based local ZIP，方便开发者和高级用户调试。它需要 Python 3.11+ 并包含源码；普通 Windows 用户优先使用 `PaperDaily.exe` standalone Release。
