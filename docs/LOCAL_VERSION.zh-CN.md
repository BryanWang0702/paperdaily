# PaperDaily 本地版

本地版适合不想配置 GitHub Actions 或 GitHub Pages 的用户。它使用和在线版相同的文献抓取、筛选、AI 排序、摘要和 HTML 页面。

## 需要准备什么

- Windows、macOS 或 Linux；
- Python 3.11 或更高版本；
- 可以访问 PubMed、bioRxiv、medRxiv、arXiv 和 AI API 的网络；
- 一个 API token，例如 DeepSeek API key。

## 通常只需要修改两个文件

### 1. `config.yaml`

这里可以设置研究领域、检索关键词、本地 prefilter、AI 分析数量、页面展示数量、AI provider/model、时区，以及本地版的更新时间点。

压缩包中的 `config.yaml` 是睡眠神经科学示例；`config.template.yaml` 是通用领域模板。

### 2. `api_token.txt`

把 `api_token.example.txt` 复制或改名为 `api_token.txt`，然后把自己的 API token 粘贴到第一行。

`api_token.txt` 已加入 `.gitignore`，不要分享这个文件。

## Windows 最简单的使用方式

双击：

```text
START_PAPERDAILY_WINDOWS.bat
```

第一次启动时会创建独立 Python 虚拟环境并安装依赖。只有真正需要刷新文献时，程序才会读取 API token。

## macOS / Linux

在解压目录中打开 Terminal，然后运行：

```bash
bash START_PAPERDAILY_MAC_LINUX.sh
```

## 智能刷新逻辑

本地版**不会每次打开都重新抓取和调用 AI**。

默认使用和在线版一样的两个北京时间更新点：

```text
05:30
20:30
```

程序启动时会先判断“当前时间之前最近一个应该完成的更新时间点”，然后检查本机的 `local_state.json`。

例如：

- 04:00 打开：最近应完成的是前一天 20:30；
- 06:00 打开：最近应完成的是当天 05:30；
- 19:00 打开：最近应完成的仍然是当天 05:30；
- 21:00 打开：最近应完成的是当天 20:30。

如果这个时间点已经在本机成功运行过，PaperDaily 会**直接打开已有网页，不重新访问文献源，也不调用 AI API**。

如果这个时间点还没有成功运行，程序会自动执行一次：

```text
抓取 → 去重 → 本地筛选 → AI ranking / summary → 写入本地网页数据
```

只有整次刷新成功之后，才会把该时间点写入 `local_state.json`。

如果刷新失败，这个时间点不会被标记为完成，因此下一次打开时仍然可以自动重试；如果之前已有页面数据，则旧页面仍然可以打开。

第一次运行时，如果本地还不存在 `site/data/latest.json`，无论当前几点都会强制执行一次刷新。

还有一个好处是：如果当前数据已经是最新的，程序连 API token 都不需要加载，直接打开本地页面即可。

## 本地刷新设置

在 `config.yaml` 中：

```yaml
local:
  port: 8765

  # scheduled | always | never
  refresh_mode: scheduled

  refresh_times:
    - "05:30"
    - "20:30"
```

`refresh_times` 使用 `config.yaml` 顶部的 `timezone`。当前睡眠版默认是 `Asia/Shanghai`，也就是北京时间。

三种模式：

- `scheduled`：推荐；只有最近一个更新时间点尚未在本机完成时才刷新；
- `always`：每次打开都刷新；
- `never`：启动时永远不抓取，只浏览已有数据。

`local_state.json` 只存在于用户自己的电脑，已加入 `.gitignore`，也不会被打进公开下载 ZIP。

## 默认本地地址

```text
http://127.0.0.1:8765/
```

使用期间不要关闭启动窗口。需要停止时按 `Ctrl+C`。

## 下载本地版 ZIP

在线 PaperDaily 每次部署时都会自动构建同步版本：

```text
https://bryanwang.cn/paperdaily/downloads/PaperDaily-local.zip
```

这个 ZIP 不包含 API token、本地刷新状态、GitHub secret、历史后台数据或 Python 虚拟环境。

## 自己生成 ZIP

```bash
python tools/build_local_bundle.py
```

默认生成 `dist/PaperDaily-local.zip`。

## 安全说明

不要把 API token 写入 HTML 或 JavaScript。本地版会让 token 保留在 Python 侧，浏览器页面不会读取 token。

分享本地文件夹时，不要包含 `api_token.txt`。
