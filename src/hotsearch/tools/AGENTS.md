# Tools

独立可运行的脚本，`python3` 直接跑。大部分纯 stdout 输出，推送由 Service 层负责。

## StandardItem 必备字段

所有 adapter 的 `normalize()` 输出必须包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | `str` | 标题 |
| `summary` | `str \| None` | 摘要或热度描述 |
| `timestamp` | `float` | 抓取时间（unix 时间戳） |
| `tags` | `list[str]` | 分类标签 |
| `source_name` | `str \| None` | 来源名称 |

可选字段：`id`、`url`、`time`、`raw`

## trends/ — 热榜与趋势（整点汇报）

| 文件 | 用途 |
|---|---|
| `hotsearch.py` | 多平台热搜（知乎/微博/东方财富/IT之家/小红书/豆瓣/Bilibili） |
| `ainews.py` | AI 新闻聚合（THE DECODER / HN / TechCrunch） |
| `github_trending.py` | GitHub 30天热门仓库 |

## feeds/ — 信息流追踪（有更新才推送）

| 文件 | 用途 |
|---|---|
| `video_feeds.py` | Bilibili RSS 视频追踪（6个UP主） |
| `release_feeds.py` | GitHub Release 追踪（OpenClaw/lark-cli） |
| `newlaw.py` | 国家新法速递（flk.npc.gov.cn） |
| `newlaw_shanghai.py` | 上海地方法规（law.sfj.sh.gov.cn） |

## system/ — 系统基础设施

| 文件 | 用途 |
|---|---|
| `feishu_send.py` | 飞书 token + 发送（被其他 tool 和 service import） |
| `feishu_voice.py` | Text → Minimax TTS → OPUS → 飞书语音消息 |
| `tavily_search.py` | Tavily 搜索 API |
| `exa_search.py` | Exa AI 搜索 API |
| `server-status.py` | 服务器状态检查（磁盘/内存/负载） |
| `prune.py` | 清理过期缓存数据（feeds/trends/search） |
