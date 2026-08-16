# PaperDaily

**语言：** [English](README.md) | 中文

PaperDaily 是一个轻量级个人科研文献雷达：自动抓取最新文献、去重、本地预筛选、按照研究者自己的兴趣进行 AI relevance ranking，并生成短摘要、关键词和文章类型，再保存成每日归档。

默认配置针对睡眠神经科学，但 retrieval、prefilter、AI 分析数量、页面显示、主题和 interest profile 都可以在 `config.yaml` 中修改，因此可以很容易 fork 到其他研究领域。

> 网站界面保持英文；仓库 README 提供中英文版本。

## 工作流程

```text
PubMed + bioRxiv + medRxiv + arXiv
                ↓
          重叠时间窗抓取
                ↓
          DOI / 来源去重
                ↓
      prefilter.max_candidates
                ↓
          ai.max_analyzed
                ↓
AI ranking + summary + keywords + paper type
                ↓
      site.featured_count 展开
          其余文献折叠
                ↓
        Daily archive + Monthly Top 5
```

## 主要功能

- PubMed、bioRxiv、medRxiv、arXiv 自动抓取。
- PubMed 使用 Create Date 重叠窗口，降低漏抓风险。
- 跨来源去重。
- AI 之前先做免费的 deterministic prefilter。
- 本地 shortlist 数量、AI 分析数量和页面默认展开数量独立配置。
- 默认 DeepSeek，同时支持 OpenAI / OpenAI-compatible endpoint。
- relevance ranking 与 summary/enrichment 分开，减少评分漂移。
- AI cache 避免重复付费。
- 每篇文献显示 source、paper type、relevance score、title、journal（若有）、authors、3–5 keywords、AI summary 和原文链接。
- 每日页显示各来源数量、关键词快捷筛选和全文搜索。
- 首页日期卡片显示 Top 5 标题；侧栏只保留 Monthly Top 5。
- 首页费用改为 `Last run / Total / Estimated per year`，不再用“今天累计费用”做年化。
- `site.show_billing` 可以控制是否显示费用。
- 内置 khaki / black / navy / forest / burgundy 配色，并支持完全自定义 palette。
- Source retry + last-good cache。
- GitHub Pages 在线版。
- Python 本地开发版。
- **Windows standalone EXE**：普通用户不需要安装 Python 或 Git。
- 本地后台 scheduler：程序一直开着时，会在设定时间自动更新。
- 每次真正抓取前检查仓库中的 standalone version manifest，提醒用户是否需要升级。

## DeepSeek API

Hosted 版本默认需要仓库 secret：

```text
DEEPSEEK_API_KEY
```

位置：**Settings -> Secrets and variables -> Actions -> Repository secrets**。

PubMed 可选：

```text
NCBI_API_KEY
PUBMED_EMAIL
```

## Windows Standalone

普通 Windows 用户推荐直接下载 GitHub Release 中的 `PaperDaily-Windows.zip`。

解压后主要是：

```text
PaperDaily-Windows/
├── PaperDaily.exe
├── config.yaml
├── api_token.txt
├── README.md
└── README.zh-CN.md
```

正常使用只需要修改：

```text
config.yaml
api_token.txt
```

然后双击：

```text
PaperDaily.exe
```

EXE 内部已经包含 Python 代码和网页静态资源。第一次运行会在同目录创建自己的 `data/` 和 `site/` 运行目录。正式 standalone 包不会包含作者自己的历史文献、API token、GitHub secret，也不会暴露一个需要用户编辑的 Python 源码目录。

完整说明：**[PaperDaily 本地 / Standalone 版](docs/LOCAL_VERSION.zh-CN.md)**。

## 智能 Scheduler

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

时间使用顶层 `timezone`。睡眠神经科学示例为：

```yaml
timezone: Asia/Shanghai
```

启动时先检查最近一个应该完成的 slot：

- 已经成功跑过 → 直接打开已有网页，不访问文献源、不调用 AI；
- 尚未完成 → 自动补跑一次；
- 程序保持打开 → 到未来的 05:30 / 20:30 后台自动更新。

只有成功完成后才写入 `local_state.json`。失败任务不会被标记为完成，会稍后重试。浏览器每分钟检查 archive 时间戳，后台更新成功后会自动 reload。

## 版本提醒

每次真正开始抓取之前，standalone 会访问仓库维护的：

```text
standalone_version.json
```

并把安装包里的 `VERSION` 与最新版本比较。

有新版时首页会显示提示和下载入口；如果版本检查网络失败，PubMed / DeepSeek 刷新照常继续，不会被阻断。

## 数量配置

```yaml
prefilter:
  max_candidates: 40

ai:
  max_analyzed: 40

site:
  featured_count: 25
```

默认就是：

```text
40 local shortlist
→ 40 AI analyzed
→ Top 25 展开
→ 15 折叠
```

三层可以独立修改。

## 主题配置

```yaml
site:
  theme: khaki
  # theme: black
  # theme: navy
  # theme: forest
  # theme: burgundy
  # theme: custom
```

自定义配色：

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

首页现在显示：

```text
Last run ¥... · Total ¥... · ~¥.../year
```

- `Last run`：最近一次单独运行的实际 AI 费用；
- `Total`：从开始记录以来的真实累计支出；
- `~¥.../year`：代表性的单次费用 × 每天计划更新次数 × 365。

一旦已经有真实 `scheduled` 运行记录，开发和调试触发的运行不会再进入年化参考单价，因此不会因为一天调试很多次把年费估计放大；但这些调试产生的真实费用仍然计入 `Total`。

如果不想显示：

```yaml
site:
  show_billing: false
```

默认是 `true`。

## Python 本地开发版

开发者仍然可以使用同步生成的 Python local ZIP：

```text
https://bryanwang.cn/paperdaily/downloads/PaperDaily-local.zip
```

它需要 Python 3.11+，适合调试、二次开发以及当前的 macOS/Linux 使用场景。普通 Windows 用户优先使用 `PaperDaily.exe`。

## Hosted 本地测试

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.runtime_pipeline --days 3
python -m http.server 8000 -d site
```

## 自动化

- `.github/workflows/daily.yml`：北京时间 **05:30 / 20:30** 更新在线版。
- `.github/workflows/deploy-pages.yml`：部署 Pages，并同步生成 Python local ZIP。
- `.github/workflows/build-standalone.yml`：`VERSION` 更新时，在 Windows runner 构建并发布新的 `PaperDaily.exe` Release。
- `.github/workflows/ci.yml`：Python/JavaScript 测试，以及真实 PyInstaller Windows EXE smoke build。

## Fork 到其他研究领域

见：**[Fork and Customize PaperDaily](docs/FORK_AND_CUSTOMIZE.md)**。

通用起点：`config.template.yaml`。

PaperDaily 的目标不是建立“全领域绝对科学质量排名”，而是成为一个透明、可复现、便宜、可持续调参的个人相关性文献系统。
