# Anya - 热搜 & 资讯 Bot

飞书 bot + API 服务，定时推送知乎/微博/东方财富/IT之家/AI 新闻/GitHub Trending，支持交互式查询。

---

## 目录

- **services/** — 三个独立服务，彼此无依赖，各自直接调 tools
  - [bot.py](services/bot.py) — 飞书 WebSocket 长连接，接收用户命令并返回热搜/AI新闻/搜索
  - [scheduler.py](services/scheduler.py) — Cron 入口，定时抓热搜推送到飞书
  - [api.py](services/api.py) — HTTP API 网关（端口 3000），对外提供热搜缓存接口
- **tools/** — 独立工具，详见 [tools/Agent.md](tools/Agent.md)
  - [search/](tools/search/) — 数据抓取：热搜、新闻、GitHub、Bilibili、法规
  - [system/](tools/system/) — 基础设施：飞书发送、搜索、TTS 语音、服务器监控
- **scripts/** — Shell 启动器
  - [run.sh](scripts/run.sh) — 加载 .env 后运行任意 Python 脚本
  - [cron-task.sh](scripts/cron-task.sh) — `crontab` 调用的任务分发器
  - [crontab.txt](scripts/crontab.txt) — crontab 配置参考
- **config/** — 配置文件
  - [voices.json](config/voices.json) — TTS 各 Agent 音色映射
- **data/** — 运行时产生，`.gitignore` 整体忽略
  - [cache/](data/cache/) — API 查询缓存、视频/Release 追踪状态、法规去重、Cron 日志

---

## 交互命令

`hot` `fi` `it` `ai` `gh` `xhs` `mv` `vd` `search` `push` `help`

## 定时推送

| 时间 | 内容 | 说明 |
|------|------|------|
| 每小时 :07 | B 站新视频 + OpenClaw/lark-cli release | 避开整点拥堵 |
| 8:07 | 知乎热搜 | 原 8:00，偏移 +7min |
| 8:17 | 微博热搜 | 原 8:15，偏移 +2min |
| 8:32 | 东方财富 | 原 8:30，偏移 +2min |
| 8:42 | IT之家 | 原 8:40，偏移 +2min |
| 8:47 | AI 新闻 | 原 8:45，偏移 +2min |
| 8:52 | GitHub Trending | 原 8:50，偏移 +2min |
| 8:57 | 服务器状态 | 原 9:00，偏移 -3min |
| 14:07 | 国家新法速递 | 原 14:00，偏移 +7min |
| 14:12 | 上海地方法规 | 原 14:05，偏移 +7min |
| 15:37 | 东方财富（下午）| 原 15:30，偏移 +7min |

## 部署

```bash
# 1. 配置环境变量
cp .env.example .env   # 编辑填入 API key 和飞书凭证

# 2. 单次测试（zhihu/weibo/eastmoney/ithome/ainews/github/push）
./scripts/run.sh services/scheduler.py zhihu

# 3. 安装定时任务
crontab scripts/crontab.txt

# 4. 启动常驻服务
cd services
python3 api.py &      # HTTP API，端口 3000
python3 bot.py &      # 飞书 WebSocket Bot
```
