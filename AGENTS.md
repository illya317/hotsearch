# Anya - 热搜 & 资讯 Bot

Bot + API 服务，定时推送热榜/资讯，支持飞书交互式查询。覆盖知乎、微博、小红书、B站、IT之家、豆瓣、东方财富热榜，AI 新闻 RSS，GitHub Trending，B站视频，开源发布，法律法规监控。

---

# 一、项目结构

```
hotsearch/
├── config/                          # 静态配置（JSON/YAML）
│   ├── bot.json                     # 飞书机器人命令映射
│   ├── cron.json                    # 定时任务调度
│   ├── hotsearch.json               # 热榜平台定义（7大平台）
│   ├── trends.json                  # 趋势任务显示名
│   ├── preference.json              # 评分参数
│   ├── search_sources.json          # 搜索域名白/黑名单
│   ├── model_config.yaml            # LLM 提供商 + 模型参数 + 降级链
│   ├── logging_config.yaml          # Python logging 配置
│   └── prompts/                     # Jinja2 模板 + Markdown prompt
│       ├── summary.j2               # SummaryAgent 输出模板
│       ├── summary.md               # 角色描述
│       ├── preference.md            # 用户内容偏好
│       ├── tag.j2                   # 标签规则更新模板
│       └── tag_classify.j2          # LLM 分类模板
│
├── src/hotsearch/                   # 主包
│   ├── __init__.py                  # 项目根解析、环境变量、路径常量
│   ├── schemas.py                   # 数据模型（dataclass + format_text）
│   │
│   ├── tools/                       # 适配器层：对接外部数据源
│   │   ├── base.py                  # ToolAdapter 抽象基类 + StandardItem/StandardResult
│   │   ├── tag.py                   # TAG_RULES 10 类关键词 + classify()
│   │   ├── logger.py                # 日志初始化器
│   │   ├── trends/                  # 趋势类适配器（pkgutil 自发现）
│   │   │   ├── base.py             # TrendAdapter 基类
│   │   │   ├── hotsearch.py        # api.rebang.today → 7 大平台
│   │   │   ├── ainews.py           # RSS → AI 新闻（3 源）
│   │   │   └── github_trending.py  # GitHub Search API → 30 天热门仓库
│   │   ├── feeds/                   # 订阅类适配器（pkgutil 自发现）
│   │   │   ├── base.py             # FeedAdapter 基类
│   │   │   ├── video_feeds.py      # RSSHub → B 站 6 频道
│   │   │   ├── release_feeds.py    # Atom → GitHub Release
│   │   │   ├── newlaw.py           # NPC API → 国家法律法规
│   │   │   └── newlaw_shanghai.py  # REST API → 上海地方法规
│   │   └── system/                  # 系统工具
│   │       ├── feishu_send.py       # 飞书消息发送（token 重试）
│   │       ├── feishu_voice.py      # TTS 语音发送
│   │       ├── tavily_search.py     # Tavily 搜索
│   │       ├── exa_search.py        # Exa 搜索
│   │       ├── server-status.py     # 服务器资源报告
│   │       └── prune.py            # 缓存清理
│   │
│   ├── services/                    # 业务逻辑层：编排适配器
│   │   ├── trends.py               # TrendsService：并行采集 → 标准化 → 聚合 + load_latest()
│   │   ├── feeds.py                # FeedsService：采集 + 增量检测 + load_latest()
│   │   ├── scoring.py              # ScoringService：标签 → 偏好权重分
│   │   ├── search.py               # SearchService：Tavily + Exa 统一搜索
│   │   └── bot.py                  # 飞书 WebSocket 交互机器人
│   │
│   ├── agents/                      # 智能体层：AI 增强处理
│   │   ├── content.py              # ContentAgent：分类 + 打分（TagEngine + ScoringService）
│   │   └── summary.py              # SummaryAgent：搜索增强 + 模板渲染 + 飞书推送
│   │
│   ├── llms/                        # LLM 客户端抽象层
│   │   ├── base.py                 # LLMClient 抽象基类
│   │   ├── minimax.py              # MinimaxClient
│   │   ├── kimi.py                 # KimiClient
│   │   ├── deepseek.py             # DeepseekClient
│   │   ├── fallback.py             # FallbackClient 降级链
│   │   └── config.py              # 模型参数解析
│   │
│   ├── routers/
│   │   └── api.py                  # HTTP API（port 3000）双层缓存 L1 内存 + L2 文件
│   │
│   └── config/
│       └── __init__.py             # 配置加载器
│
├── scripts/                         # Shell 入口
│   ├── run.sh                       # PYTHONPATH 启动器
│   ├── cron-task.sh                 # Cron 三步管道分发器
│   └── generate-crontab.py          # 从 cron.json 动态生成 crontab
│
├── data/                            # 运行时数据（gitignore）
│   ├── cache/                       # 缓存
│   │   ├── api/                     # HTTP API 文件缓存（24h TTL）
│   │   ├── trends/                  # 趋势原始数据快照
│   │   ├── feeds/                   # 订阅状态 + 快照
│   │   ├── cron/                    # 打分中间数据
│   │   └── search/                  # 搜索结果 MD
│   └── outputs/                     # 最终格式化输出（飞书推送内容）
│
└── logs/                            # 日志
    ├── cron.log                     # cron-task.sh 管道日志
    └── hotsearch.log                # Python logging 日志
```

## 分层架构

```
agent/  ──→  services/  ──→  tools/
智能体层      业务逻辑层      适配器层
```

严格上层调下层，禁止反向。同级频繁互调说明职责划分有问题，应拆分或合并。

## 核心数据流

### Cron 管道（三步）

```
cron 触发 → scripts/cron-task.sh zhihu

  Step 1: services/trends.py zhihu
          → adapter.fetch() → normalize() → StandardResult
          → 保存 data/cache/trends/zhihu_YYYYMMDD_HHMM.json

  Step 2: agents/content.py --source zhihu
          → TrendsService.load_latest("zhihu")
          → classify() 关键词匹配 → LLM 兜底
          → ScoringService.score() 权重打分
          → 保存 data/cache/cron/zhihu_scored_*.json

  Step 3: agents/summary.py --source zhihu --send
          → 加载 scored 数据
          → 高分项(≥70) → SearchService.enrich() → Tavily + Exa
          → Jinja2 summary.j2 渲染
          → 保存 data/outputs/zhihu_final_*.md
          → send_to_feishu()
```

### 飞书交互查询

```
用户 "hot 5" → bot.py WebSocket
  → bot.json 命令映射 → subprocess adapter --json
  → schemas 解析 + format_text() → 飞书回复
```

### HTTP API

```
GET /trends?sources=hotsearch,github&tag=AI
  → L1 内存缓存 → L2 文件缓存
  → Miss: TrendsService.collect() → ThreadPoolExecutor 并行
  → 24h TTL，?refresh=1 强制刷新
```

---

# 二、使用指南

## scripts/run.sh

运行任意 Python 脚本，自动设置 `PYTHONPATH`。

```bash
./scripts/run.sh src/hotsearch/services/trends.py zhihu
./scripts/run.sh src/hotsearch/agents/content.py --source zhihu
./scripts/run.sh src/hotsearch/agents/summary.py --source zhihu --send
```

> `run.sh` 用于本地测试（stdout），`cron-task.sh` 用于 cron 调度（日志写入 `logs/cron.log`）。

## scripts/cron-task.sh

Cron 任务分发器，读取 `config/cron.json`，执行三步管道。

| 参数 | 说明 |
|------|------|
| `feeds` | 运行 feeds 检查（视频 / Release / 法规） |
| `status` | 运行服务器状态检查 |
| `zhihu` `weibo` `eastmoney` `ithome` `ainews` `github` | 趋势任务名 |

```bash
./scripts/cron-task.sh zhihu
```

## routers/api.py

HTTP API 网关，端口 3000。

| 端点 | 说明 |
|------|------|
| `/hotsearch?platform=zhihu&limit=5` | 热榜查询 |
| `/ainews?source=all&limit=5` | AI 新闻 |
| `/github-trending?limit=10` | GitHub Trending |
| `/trends?sources=hotsearch,github&tag=AI` | 统一趋势接口 |
| `/feeds?sources=videos,releases` | 统一 feeds 接口 |
| `/daily?period=24h` | 24h 更新汇总 |
| `/health` | 健康检查 |

所有端点支持 `?refresh=1` 强制刷新缓存。

```bash
python3 -m hotsearch.routers.api
```

## 搜索工具

### Tavily 搜索

```bash
./scripts/run.sh src/hotsearch/tools/system/tavily_search.py --query "关键词" --save --format md
```

| 参数 | 说明 |
|------|------|
| `--query` (required) | 搜索关键词 |
| `--max-results` | 结果数，默认 5，最大 10 |
| `--search-depth` | `basic` / `advanced` |
| `--format` | `raw` / `brave` / `md` |
| `--save` | 保存到 `data/cache/search/` |

### Exa 搜索

```bash
./scripts/run.sh src/hotsearch/tools/system/exa_search.py --query "关键词" --save --format md
```

| 参数 | 说明 |
|------|------|
| `--query` (required) | 搜索关键词 |
| `--num-results` | 结果数，默认 5，最大 20 |
| `--type` | `auto` / `fast` / `deep` |
| `--format` | `raw` / `brave` / `md` |
| `--save` | 保存到 `data/cache/search/` |

## Tag 维护

```bash
# 手动分类标题
./scripts/run.sh src/hotsearch/agents/content.py --titles "标题1" "标题2"
```

## 缓存清理

```bash
./scripts/run.sh src/hotsearch/tools/system/prune.py --dry-run
./scripts/run.sh src/hotsearch/tools/system/prune.py --days 3 --targets trends,search
```

## 新增数据源

在 `tools/trends/` 或 `tools/feeds/` 下新建 adapter 文件，继承基类实现 `fetch()` + `normalize()`，自发现机制自动注册。

```python
# tools/trends/example.py
from .base import TrendAdapter

class ExampleAdapter(TrendAdapter):
    name = "example"
    tags = ["tech"]

    def fetch(self, query: str = "", **kwargs) -> dict:
        return {"items": [...]}

    def normalize(self, raw: dict) -> dict:
        return {"source_name": "example", "items": [...], "meta": None, "output": None}
```

然后在 `config/cron.json` 加调度项即可，不改任何 agent/service 代码。

## 部署

```bash
crontab <(python3 scripts/generate-crontab.py --print)  # 安装定时任务
python3 -m hotsearch.routers.api &                       # HTTP API 端口 3000
python3 -m hotsearch.services.bot &                      # WebSocket Bot
```

---

# 三、项目要求

## 1. 配置不硬编码，统一放在根目录 `config/`

- 所有可配置项（API 密钥、URL、参数、开关等）必须写入 `config/` 目录下的配置文件（JSON/YAML）
- 禁止在代码中硬编码任何配置值

## 2. 转发配置写在 `__init__`，不建子目录专用配置文件

- 模块的配置入口/转发映射写在对应包的 `__init__.py` 中
- 禁止在 `tools/`、`services/`、`agents/` 等子目录下自建 config 子目录
- 正确示范：`tools/trends/__init__.py` 的自发现注册（`_TOOLS` dict）
- 反例：在 `tools/trends/` 下放 `trends_config.json`

## 3. 输出文件统一在 `data/`

- 运行时缓存 → `data/cache/`（api/ trends/ feeds/ cron/ search/）
- 最终格式化输出 → `data/outputs/`
- 禁止在其他位置散落输出文件，`data/` 已在 `.gitignore`

## 4. 分层架构：agent → service → tools

- 严格分层，只允许上级调用下级
- `agent` 禁止直接调 `tools` 做数据采集（应通过 service）
- 同级频繁互调说明职责划分有问题，应拆分或合并

## 5. schemas 负责格式转换，routers 负责分发，统一数据出口

- `schemas.py`：所有数据格式定义和转换（dataclass、from_dict、to_dict、format_text）
- `routers/`：HTTP API 层，外部请求入口和分发，不含业务逻辑
- 数据出口统一：HTTP → `routers/api.py`，飞书交互 → `services/bot.py`，推送 → `tools/system/feishu_send.py`
- adapter/service 不允许自行直接向外部输出（stdout 供 cron 管道除外）

## 关键日志点

所有 service 和 agent 主入口统一调用 `tools/logger.py::get_logger(__name__)`：

| 节点 | 日志 |
|------|------|
| TrendsService.main() | `"{mode}: N items fetched"` |
| FeedsService.main() | `"feeds: N items collected"` |
| ContentAgent | `"{mode}: N tagged, M uncertain, scored [min-max]"` |
| SummaryAgent | `"{mode}: X deep, Y regular, Z discarded, sent OK/FAIL"` |
| SearchService.search() | `"search '{query}': N results from {engines}"` |
