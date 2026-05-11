# Anya - 热搜 & 资讯 Bot

Bot + API 服务，早 8 晚 8 自动推送热榜简报。覆盖知乎、微博、B站、IT之家、东方财富热榜，AI 新闻 RSS，GitHub Trending。

---

# 一、项目结构

```
hotsearch/
├── config/                          # 静态配置
│   ├── bot.json                     # 飞书机器人命令映射
│   ├── cron.json                    # 定时任务（period: 12h, all 8am/8pm）
│   ├── hotsearch.json               # 热榜平台定义
│   ├── trends.json                  # 趋势任务显示名
│   ├── scoring_rules.json           # 标签权重 + 向量比例 + top-N + 阈值
│   ├── embedding.json               # embedding 模型 + max_seq_length + fp16
│   ├── search_sources.json          # 搜索域名白/黑名单
│   ├── model_config.yaml            # LLM 提供商 + 降级链
│   ├── logging_config.yaml          # Python logging
│   └── prompts/                     # Jinja2 模板 + Markdown
│       ├── summary.j2               # 简报输出模板
│       ├── summary.md               # 角色描述
│       ├── preference.md            # 用户偏好（喜欢/不喜欢/深度搜索触发）
│       ├── search_summarize.j2       # 搜索摘要 prompt
│       ├── llm_refine.j2            # LLM 精排 prompt
│       ├── tag_classify.j2          # LLM 分类 prompt
│       └── tag.j2                   # 标签规则更新 prompt
│
├── src/hotsearch/
│   ├── __init__.py                  # 路径常量：PROJECT_ROOT, CONFIG_DIR, DATA_DIR,
│   │                                #   CACHE_*, OUTPUT_DIR, RANKING_DIR, EMBEDDINGS_DIR...
│   ├── schemas.py                   # 数据模型（dataclass + format_text）
│   │
│   ├── tools/                       # 适配器层
│   │   ├── base.py                  # ToolAdapter + StandardItem/StandardResult
│   │   ├── tag.py                   # TAG_RULES + classify() → 调用 tag_db
│   │   ├── tag_db.py                # SQLite 标签数据库 (data/tags.db)
│   │   ├── embedding.py             # BGE/ multilingual-MiniLM embedding
│   │   ├── logger.py                # 日志初始化
│   │   ├── trends/                  # 趋势适配器（pkgutil 自发现）
│   │   │   ├── hotsearch.py        # api.rebang.today
│   │   │   ├── ainews.py           # RSS AI 新闻
│   │   │   └── github_trending.py  # GitHub Search API
│   │   ├── feeds/                   # 订阅适配器（pkgutil 自发现）
│   │   │   ├── video_feeds.py      # RSSHub B站
│   │   │   └── release_feeds.py    # GitHub Release
│   │   └── system/
│   │       ├── feishu_send.py       # 飞书消息发送
│   │       ├── tavily_search.py     # Tavily 搜索
│   │       ├── exa_search.py        # Exa 搜索
│   │       └── prune.py            # 缓存清理
│   │
│   ├── services/                    # 业务逻辑层
│   │   ├── trends.py               # TrendsService + load_latest()
│   │   ├── feeds.py                # FeedsService + load_latest()
│   │   ├── scoring.py              # ScoringService: tag_weight×0.7 + sim×0.3 + LLM
│   │   ├── search.py               # SearchService: Tavily+Exa 统一搜索 + 缓存
│   │   └── bot.py                  # 飞书 WebSocket Bot
│   │
│   ├── agents/                      # 智能体层
│   │   ├── content.py              # ContentAgent: classify + tag+vector score + LLM refine
│   │   └── summary.py              # SummaryAgent: search enrich + render + send
│   │
│   ├── llms/                        # LLM 客户端
│   │   ├── minimax.py, kimi.py, deepseek.py
│   │   ├── fallback.py             # Minimax → Kimi → Deepseek
│   │   └── config.py
│   │
│   ├── routers/
│   │   └── api.py                  # HTTP API :3000
│   │
│   └── config/
│       └── __init__.py             # 配置加载
│
├── scripts/
│   ├── run.sh                       # PYTHONPATH 启动器
│   ├── cron-task.sh                 # 三步管道: all → 6 platforms
│   └── generate-crontab.py          # cron.json → crontab
│
├── data/                            # 运行时数据 (gitignored)
│   ├── tags.db                      # SQLite 标签库
│   ├── cache/                       # 缓存 (api/ trends/ feeds/ cron/ search/ summary/)
│   ├── outputs/                     # 最终格式化简报 .md
│   ├── ranking/                     # 三列排名 (raw/ weighted/ agent)
│   ├── embeddings/                  # 向量缓存
│   └── prompts/                     # 运行时生成的 prompts
│
└── logs/                            # 日志 (cron.log, hotsearch.log)
```

## 分层架构

```
agent/  ──→  services/  ──→  tools/
ContentAgent   ScoringService    tag.py/tag_db.py
SummaryAgent   SearchService     embedding.py
               TrendsService     trends/feeds adapters
```

## 核心数据流（Cron 管道）

```
cron 8:00/20:00 → cron-task.sh all

  Step 1 — 数据采集
  for each platform in trends:
    services/trends.py {mode}
      → adapter.fetch() → normalize() → StandardResult
      → 保存 data/cache/trends/{mode}_{ts}.json

  Step 2 — 分类+评分
  for each platform:
    agents/content.py --source {mode}
      → load raw → tag (keyword→LLM fallback)
      → ScoringService.score():
          tag_weight = max(tag_base[tag])            # 从 scoring_rules.json
          sim = cosine(title_vec, preference_vec)    # embedding
          similarity_score = (sim+1)/2*100           # [-1,1] → [0,100]
          combined = tag_weight*0.7 + sim_score*0.3  # 7:3 加权
          → LLM refine (-20~+20) → final score
      → 保存 data/cache/cron/{mode}_scored_{ts}.json

  Step 3 — 搜索增强+简报+推送
    agents/summary.py --source all --send
      → 加载所有 scored 数据（取最新 per mode）
      → 全局排序，取 top 5 + next 10
      → 高分项(≥detail_threshold) → SearchService.enrich()
          → Tavily + Exa 并行搜索
          → quality 过滤 + LLM 摘要
      → Jinja2 summary.j2 渲染
      → 保存 data/outputs/summary_{ts}.md
      → 保存 data/ranking/ranking_{ts}_{raw|weighted|agent}.json
      → send_to_feishu()
```

---

# 二、使用指南

## 本地测试

```bash
# 单步
./scripts/run.sh src/hotsearch/services/trends.py zhihu
./scripts/run.sh src/hotsearch/agents/content.py --source zhihu
./scripts/run.sh src/hotsearch/agents/summary.py --source zhihu --send

# 全管道（不发飞书）
./scripts/cron-task.sh all

# 查看排名
ls data/ranking/
```

## cron 部署

```bash
python3 scripts/generate-crontab.py --install
```

## 新增平台 / 新增 Feeds

**trends（pkgutil 自发现）**
1. 在 `tools/trends/` 新建 adapter（继承 `TrendAdapter`，实现 `fetch` + `normalize`）
2. `normalize()` 输出每个 item 必须包含 5 个字段：`title`、`summary`、`timestamp`、`tags`、`source_name`，缺失时报错
3. `config/cron.json` trends 加调度
4. 无需修改 `routers/api.py`、`services/trends.py` 等，自动注册

**feeds（pkgutil 自发现）**
1. 在 `tools/feeds/` 新建 adapter（继承 `FeedAdapter`，实现 `fetch` + `normalize`，可选 `check_new` / `get_status` / `get_daily_items`）
2. `normalize()` 输出每个 item 必须包含 5 个字段：`title`、`summary`、`timestamp`、`tags`、`source_name`，缺失时报错
3. `config/cron.json` feeds 加调度（可选 `ranking: false` 跳过 agent 直接推送）
4. 无需修改 `routers/api.py`、`services/bot.py`、`services/feeds.py` 等，自动注册

## 标签维护

```bash
# 手动分类
./scripts/run.sh src/hotsearch/agents/content.py --titles "标题1" "标题2"
```

---

# 三、项目要求

## 1. 配置不硬编码，统一放在根目录 `config/`

包括提示词。JSON/YAML/ Jinja2。

## 2. 转发配置写在 `__init__`，不建子目录专用配置文件

正确：`tools/trends/__init__.py` 自发现注册。反例：子目录下放 `xxx_config.json`。

## 3. 输出文件统一在 `data/`

缓存 → `data/cache/`，输出 → `data/outputs/`，排名 → `data/ranking/`。

## 4. 分层架构：agent → service → tools

agent 不直接调 tools 做数据采集（logger/tag/feishu_send 除外）。

## 5. schemas 格式转换，routers 分发，统一数据出口

HTTP → `routers/api.py`，飞书交互 → `services/bot.py`，推送 → `tools/system/feishu_send.py`。

## 6. 适配器自动注册（pkgutil 自发现）

`trends/` 和 `feeds/` 目录下的 adapter 通过 `pkgutil.iter_modules` + `importlib.import_module` 自动注册。新增或删除 adapter 文件后，**无需修改** `__init__.py`、`services/bot.py`、`services/feeds.py`、`routers/api.py` 等任何注册代码，运行时自动感知。
