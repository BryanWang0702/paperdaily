# PaperDaily 本地版

本地版适合不想配置 GitHub Actions 或 GitHub Pages 的用户。它使用和在线版完全相同的文献抓取、筛选、AI 排序、摘要和 HTML 页面。

## 需要准备什么

- Windows、macOS 或 Linux；
- Python 3.11 或更高版本；
- 可以访问 PubMed、bioRxiv、medRxiv、arXiv 和 AI API 的网络；
- 一个 API token，例如 DeepSeek API key。

## 通常只需要修改两个文件

### 1. `config.yaml`

这里可以设置：

- 自己的研究领域和检索关键词；
- 本地 prefilter 规则；
- `prefilter.max_candidates`；
- `ai.max_analyzed`；
- `site.featured_count`；
- AI provider / model；
- 时区；
- 本地网页端口等。

压缩包中的 `config.yaml` 是睡眠神经科学示例；`config.template.yaml` 是通用领域模板。

### 2. `api_token.txt`

把：

```text
api_token.example.txt
```

复制或改名为：

```text
api_token.txt
```

然后把自己的 API token 粘贴到第一行。

`api_token.txt` 已加入 `.gitignore`，不要分享这个文件。

## Windows 最简单的使用方式

双击：

```text
START_PAPERDAILY_WINDOWS.bat
```

第一次启动时它会自动：

1. 创建独立 Python 虚拟环境；
2. 安装所需依赖；
3. 如果没有 `api_token.txt`，自动创建一个；
4. 提示你填入 API token。

保存 token 后再双击一次。PaperDaily 会抓取最新文献、启动本地网页服务器，并自动用默认浏览器打开 HTML 页面。

## macOS / Linux

在解压目录中打开 Terminal，然后运行：

```bash
bash START_PAPERDAILY_MAC_LINUX.sh
```

脚本会创建虚拟环境、安装依赖并启动 PaperDaily。

## 启动后发生什么

默认情况下，本地启动器会：

1. 读取 `config.yaml`；
2. 把 `api_token.txt` 中的 token 写入当前 Python 进程对应的 API 环境变量；
3. 运行文献 pipeline；
4. 把完整数据写入 `data/`，网页轻量数据写入 `site/data/`；
5. 启动本地 HTML server；
6. 自动打开浏览器。

默认地址：

```text
http://127.0.0.1:8765/
```

使用期间不要关闭启动窗口。需要停止时按 `Ctrl+C`。

## 可选的本地设置

`config.yaml` 中可以使用：

```yaml
local:
  port: 8765
  refresh_on_start: true
```

如果只想查看之前已经生成的数据，不希望每次启动都重新抓取，可以设置：

```yaml
refresh_on_start: false
```

## 下载本地版 ZIP

在线 PaperDaily 每次部署时都会自动构建同步版本：

```text
https://bryanwang.cn/paperdaily/downloads/PaperDaily-local.zip
```

这个 ZIP 不包含任何 API token、GitHub secret、历史后台数据或 Python 虚拟环境。

## 自己生成 ZIP

在项目根目录运行：

```bash
python tools/build_local_bundle.py
```

默认生成：

```text
dist/PaperDaily-local.zip
```

## 安全说明

不要把 API token 写入 HTML 或 JavaScript。本地版会让 token 保留在 Python 侧，浏览器页面不会读取 token。

分享本地文件夹时，不要包含 `api_token.txt`。
