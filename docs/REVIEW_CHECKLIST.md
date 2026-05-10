# Code Review Checklist

基于 `AGENTS.md` 项目要求，每次 commit 后自动检查。

## 五条硬性检查

### 1. 配置外置
- [ ] 无硬编码 URL / API Key / 魔法数字
- [ ] 新增配置项在 `config/` 目录下（JSON 或 YAML）

### 2. 转发配置在 `__init__`
- [ ] 无新增子目录下的 `config/` 或 `*_config.json`
- [ ] 模块注册/路由映射在 `__init__.py` 中

### 3. 输出统一在 `data/cache/`
- [ ] 无散落在 `/tmp`、项目根目录、模块目录的输出文件
- [ ] 使用 `CACHE_*_DIR` 常量（定义在 `src/hotsearch/__init__.py`）

### 4. 分层不越界
- [ ] `agent/` 未直接调用 `tools/` 做数据采集
- [ ] `tools/` 未调用 `services/` 或 `agents/`
- [ ] 同级模块无新增频繁互调

### 5. schemas + routers 统一出口
- [ ] 新增数据格式在 `schemas.py` 中定义
- [ ] HTTP 端点只在 `routers/api.py` 中新增
- [ ] adapter/service 未直接向外部输出（除 stdout 供 cron 管道）

## 代码质量

- [ ] 无 `print()` 调试残留（关键日志用 `get_logger(__name__)`）
- [ ] import 路径使用 `hotsearch.xxx` 绝对导入
- [ ] 新增 adapter 实现 `fetch()` + `normalize()` 两个方法
- [ ] 外部依赖无新增（如需新增，更新 `pyproject.toml`）

## 检查命令

```bash
# 硬编码检查（排除已知API域名）
grep -rnE 'https?://' src/hotsearch/ --include='*.py' | grep -vE 'open.feishu|api.rebang|api.tavily|api.exa|#|__init__'

# 分层违规：agent 调 tools 做数据采集（logger/feishu_send/tag.classify 是合法工具调用）
grep -rnE 'from hotsearch.tools.(trends|feeds)' src/hotsearch/agents/ --include='*.py'

# 分层违规：tools 调 services（禁止反向）
grep -rnE 'from hotsearch.services' src/hotsearch/tools/ --include='*.py'

# 输出路径检查
grep -rn "Path(" src/hotsearch/ --include="*.py" | grep -vE "CACHE_|CONFIG_|PROJECT_ROOT|__file__"
```

> agent 合法调用 tools: `tools/logger.py`（日志）、`tools/tag.py`（关键词分类）、`tools/system/feishu_send.py`（推送出口）。这三者不算数据采集。
