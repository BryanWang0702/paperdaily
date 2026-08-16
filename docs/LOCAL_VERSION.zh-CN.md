# PaperDaily 本地 / Standalone 版

PaperDaily 可以完全脱离 GitHub Actions 和 GitHub Pages 运行。对于普通 Windows 用户，推荐直接使用冻结后的 standalone 版本：不需要安装 Python、不需要 Git，也不需要修改源代码。

## Windows standalone：最简单的方式

从 GitHub 最新 Release 下载 `PaperDaily-Windows.zip`，解压后目录主要是：

```text
PaperDaily-Windows/
├── PaperDaily.exe
├── config.yaml
├── api_token.txt
├── README.md
└── README.zh-CN.md
```

普通用户通常只需要修改两个文件：

- `config.yaml`：研究领域、检索规则、筛选数量、AI 设置、更新时间、主题和页面显示选项；
- `api_token.txt`：第一行填 AI API token。

之后双击 `PaperDaily.exe`。程序会自动创建自己的 `data/` 和 `site/` 运行目录，并用默认浏览器打开页面。

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
```

时间使用 `config.yaml` 顶部的 `timezone`。当前睡眠神经科学示例为 `Asia/Shanghai`，即北京时间。

启动时，PaperDaily 会判断当前时间之前最近一个应该完成的 refresh slot。如果该 slot 已记录在 `local_state.json` 中，就直接打开已有网页，不访问 PubMed/bioRxiv，也不调用 AI。如果还没成功运行，就先补跑一次。

如果程序一直开着，后台 scheduler 会持续运行，并在未来的 05:30 / 20:30 自动触发更新。只有抓取和 AI 分析都成功后才会记录该 slot；失败的任务不会被假装标记完成，而会稍后重试。

浏览器每分钟检查一次 archive 时间戳。后台刷新成功后，页面会自动重新载入，不需要手动按 F5。

三种模式：

```yaml
refresh_mode: scheduled  # 推荐
refresh_mode: always     # 每次启动都刷新
refresh_mode: never      # 永远只看已有本地数据
```

## 版本更新提醒

每次真正开始抓取文献之前，standalone 会读取本仓库中的 `standalone_version.json`，并将安装包内的 `VERSION` 与最新版本比较。

如果有新版本，首页会显示更新提醒和下载入口。如果版本检查失败，例如暂时无法访问 GitHub，文献抓取仍然继续；版本检查永远不会阻断 PubMed / DeepSeek pipeline。

## 配色主题

内置主题包括：

```yaml
site:
  theme: khaki      # 当前默认，暖色纸张感
  # theme: black    # 黑色极简
  # theme: navy     # 经典学术深蓝
  # theme: forest   # 低饱和森林绿
  # theme: burgundy # 酒红
  # theme: custom
```

如果想自己配色：

```yaml
site:
  theme: custom
  custom_theme:
    background: "#f2efe5"
    surface: "#fffdf8"
    text: "#1f2723"
    muted: "#6b7068"
    border: "#d8d3c5"
    accent: "#75684d"
    accent_text: "#ffffff"
```

## 费用显示

首页可以显示：

```text
Last run ¥... · Total ¥... · ~¥.../year
```

其中：

- `Last run`：最近一次单独 AI 运行的费用，不再是“今天累计费用”；
- `Total`：PaperDaily 从开始记录以来的实际累计 API 支出；
- `~¥.../year`：用具有代表性的单次运行成本 × 每天配置的更新次数 × 365 估算。

一旦有真实 scheduled 运行记录，开发和调试触发的运行不会进入年化参考单价，因此不会因为一天调试几十次而把年费估计放大。

如果不想显示费用：

```yaml
site:
  show_billing: false
```

默认是 `true`。

## 研究领域配置

常用设置包括：

- `discovery_terms`
- `prefilter.max_candidates`
- `prefilter.anchors / weights / boosts`
- `ai.max_analyzed`
- `ai.interest_profile`
- `site.featured_count`
- `local.refresh_times`

当前 `config.yaml` 是睡眠神经科学示例；仓库里的 `config.template.yaml` 可以作为其他领域的通用起点。

## 安全

API token 始终保留在 Python / EXE 侧，不会写进 HTML 或 JavaScript。不要分享自己的 `api_token.txt`。

正式 Windows standalone Release 不包含作者自己的历史文献数据、API token、GitHub secret，也不会暴露可编辑的 Python 源代码目录。

## Python 本地开发版

项目仍然会提供 Python-based local ZIP，方便开发者和高级用户调试。它需要 Python 3.11+，并包含源码。普通 Windows 用户优先使用 `PaperDaily.exe` standalone Release。
