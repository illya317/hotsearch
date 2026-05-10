# 搜索工具使用指南

## 什么时候搜索

遇到以下情况，**主动搜索**补充背景，不要只给标题：

- 标题提到具体政策/法规 → 搜原文+解读
- 提到具体公司/人物 → 搜背景+近期动态
- 提到具体数据/数字 → 核实来源
- 涉及地缘政治/国际关系 → 搜多方视角
- 主人兴趣领域（见 preference.md）的新进展

## 工具

### Tavily (`tools/system/tavily_search.py`)

通用搜索，适合快速查事实、新闻、背景。

```bash
./scripts/run.sh src/hotsearch/tools/system/tavily_search.py \
  --query "关键词" \
  --max-results 5 \
  --search-depth basic \
  --save
```

| 参数 | 说明 |
|------|------|
| `--query` | 搜索关键词（必填） |
| `--max-results` | 结果数，默认 5，最大 10 |
| `--search-depth` | `basic` / `advanced` |
| `--include-answer` | 包含 AI 总结答案 |
| `--save` | 保存原始 JSON 到 `cache/search/` |

### Exa (`tools/system/exa_search.py`)

AI 语义搜索，适合找深度内容、论文、长文。

```bash
./scripts/run.sh src/hotsearch/tools/system/exa_search.py \
  --query "关键词" \
  --num-results 5 \
  --type auto \
  --text-max-chars 5000 \
  --save
```

| 参数 | 说明 |
|------|------|
| `--query` | 搜索关键词（必填） |
| `--num-results` | 结果数，默认 5，最大 20 |
| `--type` | `auto` / `fast` / `instant` / `deep-lite` / `deep` / `deep-reasoning` |
| `--text-max-chars` | 获取全文最大字符数，0 = 关闭 |
| `--highlights` | 包含高亮片段 |
| `--save` | 保存原始 JSON 到 `cache/search/` |

## 数据保存

- 加 `--save` 会存到 `cache/search/`
- `tavily_{hash}.json` 或 `exa_{hash}.json`
- 默认保留 7 天，`prune.py` 自动清理
