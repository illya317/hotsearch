# Config

所有配置集中在此，改行为不改代码。

## 文件

| 文件 | 用途 | 谁读取 |
|------|------|--------|
| `hotsearch.json` | 热榜平台定义：API 参数、tab 覆盖、组合分组 | `tools/trends/hotsearch.py` |
| `bot.json` | 飞书 Bot 命令：别名、工具映射、help 文本 | `services/bot.py` |
| `trends.json` | 定时任务：命令行和显示名称 | `services/trends.py` |
| `feishu_voice.json` | TTS 音色映射（Agent → voice_id） | `tools/system/feishu_voice.py` |
| `cron.json` | Cron 任务分发：脚本路径、目录、日志 | `scripts/cron-task.sh` |

> **注意**：feeds（视频/Release/法规）没有独立配置文件，源列表硬编码在 `services/feeds.py` 中。
| `README.md` | MiniMax 完整音色列表参考 | 人看 |

## 修改原则

- **加平台**：改 `hotsearch.json` + `bot.json` + `trends.json`
- **改命令别名**：改 `bot.json` 里的 `aliases`
- **改定时任务**：改 `trends.json`
- **改 cron 分发**：改 `cron.json`（脚本路径、目录、日志）
- **不改代码**：无需重启 bot，配置读取在模块加载时完成
