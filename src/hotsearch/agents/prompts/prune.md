# 数据清理工具

## 什么时候用

主人说"删"、"清理"、"过期数据"时，用 `prune.py`。

## 命令

```bash
./scripts/run.sh src/hotsearch/tools/system/prune.py --dry-run
./scripts/run.sh src/hotsearch/tools/system/prune.py --days 3 --targets trends,search
```

| 参数 | 说明 |
|------|------|
| `--days` | 过期阈值（天），默认 7 |
| `--targets` | `feeds,trends,search`，逗号分隔 |
| `--dry-run` | 只打印不删除，先给主人确认 |

## 清理范围

- `feeds` — 从 video/release 状态文件里删除超过 N 天的条目
- `trends` — 删除 `cache/trends/` 下超过 N 天的文件
- `search` — 删除 `cache/search/` 下超过 N 天的文件

**注意**：必须先 `--dry-run` 给主人看，确认后再执行真删除。
