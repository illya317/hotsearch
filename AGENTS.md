# Anya - 热搜 & 资讯 Bot

Bot + API 服务，定时推送热榜/资讯，支持交互式查询。

## 目录

```
.
├── services/           -- 服务层（独立运行，直接调 tools）
│   ├── bot.py          -- 交互 Bot
│   ├── trends.py       -- 定时热榜推送
│   ├── feeds.py        -- 内容更新追踪
│   └── api.py          -- HTTP API 网关（端口 3000）
├── tools/              -- 工具层
│   ├── trends/         -- 热榜抓取
│   ├── feeds/          -- 内容追踪
│   └── system/         -- 发送 / 搜索 / TTS / 监控
├── scripts/            -- 启动脚本
│   ├── run.sh          -- 运行 Python 脚本
│   ├── cron-task.sh    -- Cron 任务分发
│   └── crontab.txt     -- 定时任务配置
├── config/             -- 配置文件（改行为不改代码）
│   ├── hotsearch.json  -- 平台定义
│   ├── bot.json        -- Bot 命令
│   ├── trends.json     -- 定时任务
│   ├── feishu_voice.json -- TTS 音色
│   └── cron.json       -- Cron 分发配置
├── agents/             -- AI 上下文生成
│   ├── summary.py      -- 读取 API 输出格式化数据
│   └── prompts/        -- AI system prompt 模板
└── data/
    ├── cache/          -- 运行时数据
    │   ├── api/        -- API 缓存
    │   ├── trends/     -- 热榜缓存
    │   ├── feeds/      -- 追踪状态
    │   └── search/     -- 搜索缓存
    └── prompts/        -- 运行时生成的 prompts
```

## 用法

### scripts/run.sh

运行任意 Python 脚本，自动设置 `PYTHONPATH`。

| 参数 | 说明 |
|------|------|
| `<script>` | Python 脚本路径（相对项目根目录） |
| `[args...]` | 该脚本接受的参数 |

```bash
./scripts/run.sh src/hotsearch/services/trends.py zhihu
```

> `run.sh` 用于本地测试（stdout 直接输出），`cron-task.sh` 用于 cron 调度（日志统一写入文件）。

### scripts/cron-task.sh

Cron 任务分发器，读取 `config/cron.json` 调度，底层调用 `run.sh` 执行。

| 参数 | 说明 |
|------|------|
| `feeds` | 运行 feeds 检查（视频 / Release / 法规） |
| `status` | 运行服务器状态检查 |
| `<trend>` | Trends 任务名（由 `config/trends.json` 定义） |
| `--no-send` | 只写入 `data/cache/trends/`，不推送到飞书 |

```bash
./scripts/cron-task.sh zhihu
./scripts/cron-task.sh zhihu --no-send
```

日志统一输出到 `data/cache/cron/cron.log`。

### agents/main.py

Agent 入口。自动输出 `AGENTS.md` + 24h 数据上下文，供外部 AI 消费。

| 参数 | 说明 |
|------|------|
| `--no-prompts` | 不输出 prompt 文件，只输出数据 |
| `--api-base` | API 地址，默认 `http://localhost:3000` |

```bash
./scripts/run.sh src/hotsearch/agents/main.py
```

### services/api.py

HTTP API 网关，端口 3000，无命令行参数。

| 查询参数 | 说明 |
|----------|------|
| `?refresh=1` | 强制刷新缓存，重新抓取 |
| `/daily?period=24h` | feeds 更新汇总，支持任意 `Nh` 或 `Nd` |

缓存默认 24h 过期，过期后自动重新抓取。

```bash
python3 -m hotsearch.services.api
```

### tools/system/tavily_search.py

Tavily 搜索 API。

| 参数 | 说明 |
|------|------|
| `--query` (required) | 搜索关键词 |
| `--max-results` | 结果数量，默认 5，最大 10 |
| `--include-answer` | 包含 AI 总结答案 |
| `--search-depth` | `basic` / `advanced` |
| `--format` | `raw` / `brave` / `md` |
| `--save` | 保存原始 JSON 到 `data/cache/search/` |

```bash
./scripts/run.sh src/hotsearch/tools/system/tavily_search.py --query "xxx" --save
```

### tools/system/prune.py

清理过期缓存数据。

| 参数 | 说明 |
|------|------|
| `--days` | 过期阈值（天），默认 7 |
| `--targets` | `feeds,trends,search`，逗号分隔 |
| `--dry-run` | 只打印不删除 |

```bash
./scripts/run.sh src/hotsearch/tools/system/prune.py --dry-run
./scripts/run.sh src/hotsearch/tools/system/prune.py --days 3 --targets trends,search
```

### tools/system/exa_search.py

Exa AI 搜索 API。

| 参数 | 说明 |
|------|------|
| `--query` (required) | 搜索关键词 |
| `--num-results` | 结果数量，默认 5，最大 20 |
| `--type` | `auto` / `fast` / `instant` / `deep-lite` / `deep` / `deep-reasoning` |
| `--text-max-chars` | 获取全文最大字符数，0 = 关闭 |
| `--highlights` | 包含高亮片段 |
| `--format` | `raw` / `brave` / `md` |
| `--save` | 保存原始 JSON 到 `data/cache/search/` |

```bash
./scripts/run.sh src/hotsearch/tools/system/exa_search.py --query "xxx" --save
```

## 部署

```bash
crontab scripts/crontab.txt       # 安装定时任务
cd src/hotsearch/services
python3 api.py &                  # HTTP API，端口 3000
python3 bot.py &                  # WebSocket Bot
```
