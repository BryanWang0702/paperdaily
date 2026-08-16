# PaperDaily

**语言：** [English](README.md) | 中文

PaperDaily 是一个轻量级的个人科研文献雷达。它会自动抓取最新文献、去重、进行透明的本地规则预筛选、根据研究者自己的兴趣进行 AI 相关性排序和摘要，并通过 GitHub Pages 发布为可持续更新的每日文献档案。

默认配置针对睡眠神经科学，但检索关键词、本地筛选规则、AI 分析数量和研究兴趣描述都可以在 `config.yaml` 中修改，因此也适合 fork 后用于其他研究领域。

> 网站本身保持英文界面；本仓库 README 同时提供中英文版本。

## 工作流程

```text
PubMed + bioRxiv + medRxiv + arXiv
                ↓
          重叠时间窗抓取
                ↓
          DOI / 来源去重
                ↓
         本地规则预筛选
      prefilter.max_candidates
                ↓
       选择送入 AI 的文献
          ai.max_analyzed
                ↓
 AI 排序 + 摘要 + keywords + 类型识别
                ↓
 site.featured_count 默认展开
       其余文献折叠显示
                ↓
       每日归档 + Monthly Top 5
                ↓
           GitHub Pages
```

## 主要功能

- 每日从 PubMed、bioRxiv、medRxiv 和 arXiv 抓取文献。
- PubMed 使用 Create Date 重叠窗口，减少漏抓新收录文献的概率。
- 跨来源去重。
- 在付费 AI 调用之前先进行免费的本地规则预筛选。
- 本地筛选数量和 AI 分析数量可以独立配置。
- 默认使用 DeepSeek。
- 同时支持 OpenAI 和其他兼容 OpenAI Chat Completions 的接口。
- AI ranking 和 summary 分开执行，提高相关性评分稳定性。
- 已处理文献会缓存，避免重复消耗 API token。
- 保留来源中的作者信息，并为每篇 AI 分析文献生成 3–5 个关键词和标准化的科学文章类型。
- 来源提供期刊名称时会保留；PubMed 文献会在每日卡片直接显示期刊名称。
- 每篇文献显示来源、类型、相关性评分、标题、期刊、作者、关键词、短摘要和原文链接。
- 每日页面显示 PubMed / bioRxiv / medRxiv / arXiv 的抓取数量。
- 每日页面根据当天关键词自动生成快捷筛选按钮，同时保留全文搜索框。
- 首页每个日期卡片直接显示当天 Top 5 标题。
- 首页侧边栏提供 Monthly Top 5。
- API 费用只在首页右上角集中显示。
- 后台继续记录每次运行和累计 token / API 费用。
- 文献源临时失败时支持重试和 last-good cache。
- GitHub Actions 会在正式运行前检查 API secret 是否已经配置。
- 自动部署 GitHub Pages。
- 网站中的更新时间统一按北京时间（`Asia/Shanghai`）显示。
- 提供不依赖 GitHub Actions / GitHub Pages 的可下载本地版。

## 文献元数据增强

PaperDaily 使用“**来源元数据优先，AI 补充和标准化**”的方式，而不是完全依赖 AI 猜测：

- **Authors**：直接保留 PubMed、bioRxiv、medRxiv、arXiv 提供的作者信息。
- **Journal**：来源提供期刊名称时直接保留；PubMed 的期刊名称会显示在每日文献卡片中。
- **Keywords**：来源有官方关键词时保留；AI summary 阶段同时为每篇文献生成 3–5 个简洁、具体的英文科研关键词。
- **Paper type**：来源提供的 publication type 作为重要依据，再标准化为 `Research Article`、`Review`、`Systematic Review`、`Meta-analysis`、`Methods/Resource`、`Clinical Study`、`Clinical Trial`、`Case Report`、`Protocol`、`Commentary/Perspective`、`Editorial` 或 `Other` 等科学内容类型。

`Preprint` 现在被视为**发表状态**，而不是 paper type。例如一篇 bioRxiv 论文仍然会根据内容被识别为 `Research Article`、`Review` 或 `Methods/Resource`；它来自 bioRxiv 这一来源本身已经表明它是预印本。

这些信息在 summary 阶段生成，因此不会改变独立的 relevance ranking prompt，也不会为了增加类型和关键词而重新定义相关性评分逻辑。

## DeepSeek API 配置

默认配置使用 DeepSeek，需要在 GitHub 仓库中添加：

```text
DEEPSEEK_API_KEY
```

位置：

**Settings -> Secrets and variables -> Actions -> Repository secrets**

PubMed 还可以选配：

```text
NCBI_API_KEY
PUBMED_EMAIL
```

当前抓取规模下，这两个不是必须的。

## 本地开发运行

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline --days 3
```

启动本地网页：

```bash
python -m http.server 8000 -d site
```

然后打开：

```text
http://localhost:8000
```

## 可下载本地版

PaperDaily 每次发布网页时都会同步生成一个本地版 ZIP：

```text
https://bryanwang.cn/paperdaily/downloads/PaperDaily-local.zip
```

这个版本适合不熟悉 GitHub 的用户。正常情况下，只需要修改两个文件：

```text
config.yaml
api_token.txt
```

### Windows

解压后双击：

```text
START_PAPERDAILY_WINDOWS.bat
```

第一次运行会自动创建 Python 虚拟环境、安装依赖，并在缺少 token 时创建 `api_token.txt`。把 DeepSeek 或其他兼容 API token 粘贴到第一行并保存，再双击一次即可。

### macOS / Linux

在解压目录中运行：

```bash
bash START_PAPERDAILY_MAC_LINUX.sh
```

启动器会先根据 `config.yaml` 抓取和分析最新文献，然后启动本地网页服务器，并自动在浏览器打开同一套 HTML 界面。API token 只保留在 Python 侧，不会被写进 HTML 或 JavaScript。

完整说明见：**[PaperDaily 本地版](docs/LOCAL_VERSION.zh-CN.md)**。

## 最重要的三个数量配置

现在可以在 `config.yaml` 中分别控制三个阶段：

```yaml
prefilter:
  # 免费的本地规则预筛选最终保留多少篇
  max_candidates: 40

ai:
  # 最多把多少篇预筛选结果送给 AI
  # 送入 AI 的文献都会进行相关性评分、摘要、关键词和类型识别
  max_analyzed: 40

site:
  # 每日页面默认展开多少篇
  # 其余已经 AI 分析的文献会放在折叠区域
  featured_count: 25
```

默认配置是：

```text
40 -> 40 -> 25
```

含义是：

1. 本地规则从当天抓到的全部文献中最多保留 40 篇；
2. 最多把这 40 篇全部送入 AI 进行排序和元数据增强；
3. 页面默认展开相关性最高的 25 篇；
4. 剩余 15 篇放在折叠区域。

也可以改成，例如：

```yaml
prefilter:
  max_candidates: 80

ai:
  max_analyzed: 50

site:
  featured_count: 20
```

这样流程就是：

```text
80 篇本地 shortlist
        ↓
50 篇 AI ranking + summary
        ↓
Top 20 默认展开
        ↓
剩余 30 篇折叠
```

如果 `ai.max_analyzed` 大于 `prefilter.max_candidates`，实际 AI 分析数量会自然受本地 shortlist 数量限制。

## 其他可配置内容

`config.yaml` 还可以修改：

- 时区；
- broad discovery terms；
- arXiv categories；
- 本地 prefilter 的 anchors、weights、penalties 和 boosts；
- AI provider 和 model；
- 研究者自己的 `interest_profile`；
- API token 价格参数；
- 本地版使用的端口和是否启动时自动刷新。

如果想从一个完全通用的配置开始，可以参考：

```text
config.template.yaml
```

## 首页

每个日期卡片会显示：

- 当天抓取并去重后的文献总数，但作为次要信息显示；
- featured / additional 文献数量；
- 按北京时间显示的最近一次更新时间；
- 当天相关性最高的 Top 5 标题。

API 费用只在首页右上角显示；单个日期卡片和每日子页不再重复显示费用。

侧边栏只保留 **Monthly Top 5**，根据过去 30 天的 AI relevance score 排序。

## 每日页面

每日页面会显示：

- 当天 unique paper 总数；
- PubMed、bioRxiv、medRxiv 和 arXiv 各自抓取数量；
- 按北京时间显示的更新时间；
- 根据当天常见 keywords 自动生成的快捷筛选按钮；
- 一个可以搜索标题、期刊、作者、关键词、摘要、来源和类型的搜索框；
- 按 relevance score 从高到低排序的文献；
- `site.featured_count` 指定数量的默认展开文献；
- 其余 AI 分析文献默认折叠；
- 每篇文献的来源、paper type、relevance score、标题、期刊（若有）、作者、3–5 个关键词、AI 短摘要和原文链接。

完整 abstract 只保存在后台 `data/`，不会发送到公开网页，因此页面加载更快。

## 自动运行

`.github/workflows/daily.yml` 当前每天在**北京时间 05:30 和 20:30**运行，也支持手动触发。主配置时区为 `Asia/Shanghai`。

`.github/workflows/deploy-pages.yml` 会在文献刷新成功或者网页代码变化后自动部署 GitHub Pages，同时构建同步的本地版 ZIP。

`.github/workflows/ci.yml` 会编译 Python、检查前端 JavaScript 语法、运行单元测试，并验证本地版 ZIP 可以成功生成。

## Fork 到自己的研究领域

完整英文教程：

**[Fork and Customize PaperDaily](docs/FORK_AND_CUSTOMIZE.md)**

通用配置模板：

```text
config.template.yaml
```

通常只需要修改 retrieval terms、prefilter 规则、AI interest profile 和几个数量参数，就可以把 PaperDaily 改造成其他领域的个人文献雷达。

## 设计原则

PaperDaily 不试图给所有论文建立一个“绝对科学质量排名”。它更像一个可复现的个人相关性系统：尽量不漏掉重要工作、长期运行成本足够低，并且当推荐结果不理想时，可以清楚地知道应该修改哪一层规则。
