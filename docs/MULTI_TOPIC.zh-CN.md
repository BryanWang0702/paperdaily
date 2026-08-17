# 多研究主题

PaperDaily 0.6 可以在同一个安装中维护多个彼此独立的研究兴趣或项目。

## 配置结构

`config.yaml` 保存整个 PaperDaily 共用的设置，例如 API provider、更新时间、数据源数量限制、主题配色和默认 AI batch 参数。

每一个研究项目放在 `topics/`：

```text
config.yaml
topics/
  sleep-homeostasis.yaml
  eeg-methods.yaml
  your-next-project.yaml
```

在 `config.yaml` 中启用：

```yaml
topics:
  enabled: true
  directory: topics
  default: sleep-homeostasis
```

Topic 文件只需要写这个项目与全局配置不同的部分，例如：

```yaml
id: my-topic
label: My Topic
description: Short dashboard description.

discovery_terms:
  - important phrase
  - another phrase

prefilter:
  anchors: [important phrase]
  weights:
    important phrase: 15

ai:
  max_analyzed: 40
  interest_profile: |
    Explain the research questions and ranking preferences for this project.
```

每个 topic 也可以单独覆盖 `prefilter.max_candidates`、`ai.max_analyzed` 等数量参数。

## Pipeline 如何工作

PaperDaily 会先合并所有启用 topic 的 discovery terms 和 arXiv categories，每次 refresh 对每个外部 source 只进行一套共享抓取，并统一去重。之后再针对每个 topic 分别建立 matching pool、规则预筛和 AI relevance ranking。

因此同一篇文献可以同时出现在多个项目中，并在不同 topic 下获得不同的 relevance score。每个 topic 的 AI cache 相互隔离，一个项目的排序不会覆盖另一个项目。

共享抓取数量可以随 topic 数量扩大：

```yaml
topics:
  scale_source_limit: true
  max_shared_source_results: 500
```

这样可以降低某一个很宽泛的 topic 占满共享候选池的风险。

## 页面行为

主页和每日页面都提供 Topic selector。切换 topic 后，会同步切换：

- 每日 archive 卡片；
- Monthly Top 5；
- 每日 relevance 排序；
- highlighted / additional 文献；
- keyword 快捷筛选和搜索上下文；
- 当前 topic 匹配到的各来源数量。

浏览器会记住上一次选择的 topic。

## 增加第三个项目

复制 `topics/` 中已有的一个 YAML，设置新的唯一 `id`，然后修改 discovery terms、prefilter 和 AI interest profile 即可。GitHub 在线版提交 `topics/*.yaml` 后会立即触发 refresh；Standalone 运行期间保存 topic 文件，也会被配置 watcher 检测并触发重新抓取与分析。

## 向后兼容

多主题功能是显式启用的。旧配置如果没有 `topics.enabled: true`，仍然按照原来的单主题 PaperDaily 运行。
