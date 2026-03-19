# ATLAST ECP — Phase 3 详细开发计划（任务细分版）

> **目标**：从 "完整 SDK + 参考实现" 进化为 "生产就绪的协议生态"
> **起始版本**：v0.6.1 | **目标版本**：v0.7.0
> **起始测试**：415 passed, 2 skipped（含 BUG-1 修复后新增 3 个）
> **起始 commit**：`7ed9b6b` (main = origin/main)
> **预计总工时**：~10.5h
> **预计完成后测试**：455+
> **分工确认**：全部任务在 `atlast-ecp/` repo 内，不触碰 `llachat-platform/`、`api.llachat.com`、Trust Score 算法

---

## 已修复的 P0-P2 遗留问题（commit 7ed9b6b）

| Bug | 严重度 | 状态 | 修复内容 |
|-----|--------|------|---------|
| BUG-1 Merkle 排序不一致 | 🔴 严重 | ✅ 已修复 | `server/merkle.py` 去掉 `sorted()`，与 SDK `batch.py` 统一为保留原序 |
| BUG-2 DID 示例格式 | 🟡 低 | ✅ 已修复 | `ECP-SERVER-SPEC.md` 5 处 `z6Mk...` → `a1b2c3d4...` hex 格式 |

---

## P3-1: Insights Layer B — 拆分子端点（~2h，≥12 新测试）

**背景**：Alex 要求 Dashboard 异步加载 3 个独立面板。当前 `analyze_records()` 返回 7 个 key 的单一大对象。
**影响范围**：`sdk/atlast_ecp/insights.py`、`sdk/atlast_ecp/cli.py`、`server/routes/`、`server/models.py`

### 子任务

| ID | 任务 | 改动文件 | 依赖 | 验收标准 |
|----|------|---------|------|---------|
| 3.1.1 | `analyze_performance(records)` 函数 | `insights.py` | 无 | 返回 `{avg_latency_ms, p95_latency_ms, success_rate, throughput_per_min, total_records, by_model: {model: {avg_ms, count}}}` |
| 3.1.2 | `analyze_trends(records, bucket="day")` 函数 | `insights.py` | 无 | 返回 `{buckets: [{period, record_count, avg_latency_ms, error_count}], bucket_size}` |
| 3.1.3 | `analyze_tools(records, top_n=10)` 函数 | `insights.py` | 无 | 返回 `{tools: [{name, count, avg_duration_ms, error_rate}], total_tool_calls}` |
| 3.1.4 | 重构 `analyze_records()` | `insights.py` | 3.1.1-3 | 内部调用 3 个子函数聚合，**返回值 key 不变**（`summary`, `latency_by_model`, `model_usage`, `flags`, `error_count`, `high_latency_count`, `recommendations`）→ 向后兼容 |
| 3.1.5 | CLI `--section` 参数 | `cli.py` | 3.1.1-3 | `atlast insights --section performance\|trends\|tools`；无参数 = 全部（现有行为） |
| 3.1.6 | `PerformanceResponse` model | `server/models.py` | 3.1.1 | Pydantic schema |
| 3.1.7 | `TrendsResponse` model | `server/models.py` | 3.1.2 | Pydantic schema |
| 3.1.8 | `ToolsResponse` model | `server/models.py` | 3.1.3 | Pydantic schema |
| 3.1.9 | `server/routes/insights.py` — 3 个端点 | 新文件 | 3.1.6-8 | `GET /v1/insights/performance?agent_did=&period=`、`/trends`、`/tools` |
| 3.1.10 | 挂载 insights 路由到 `main.py` | `server/main.py` | 3.1.9 | `app.include_router(insights.router)` |
| 3.1.11 | SDK 单元测试 | `sdk/tests/test_insights.py` | 3.1.1-4 | ≥6 个：3 个子函数各 1 正常 + 1 空输入 |
| 3.1.12 | Server 端点测试 | `server/tests/test_insights.py` | 3.1.9 | ≥6 个：3 个端点各 1 正常 + 1 无数据 |

### 逻辑碰撞检查

| 检查项 | 结果 |
|--------|------|
| `analyze_records()` 返回值结构是否改变？ | ❌ 不变。内部重构，外部 key 完全保留 |
| 现有 `test_insights.py` 的 15 个测试会 break 吗？ | ❌ 不会。`analyze_records()` 行为不变 |
| CLI `atlast insights`（无参数）行为变吗？ | ❌ 不变。`--section` 是新增可选参数 |
| Server insights 端点需要 auth 吗？ | 不需要。Insights 是 agent 自己的数据分析，Reference Server 场景下用 `agent_did` 过滤即可 |
| `insights.py` 导入了 `storage.py` 吗？ | 是，`cmd_insights()` 调用 `load_records()`。子函数只接受 `records` 参数，不直接 import storage |
| Trends 的 timestamp 来自哪个字段？ | v1.0 用 `ts`（epoch ms），v0.1 用 `timestamp`（ISO8601）。需要在 `analyze_trends()` 内部处理两种格式 |

---

## P3-2: API 增强 — 分页 + Batch Records + Handoffs（~2h，≥10 新测试）

**背景**：Alex 对齐时提出 Dashboard 需要分页、batch 详情、handoffs 查询。
**影响范围**：`server/routes/`、`server/models.py`、`server/database.py`

### 子任务

| ID | 任务 | 改动文件 | 依赖 | 验收标准 |
|----|------|---------|------|---------|
| 3.2.1 | `PaginatedResponse` 通用 model | `server/models.py` | 无 | `{total: int, page: int, limit: int, items: list}` generic |
| 3.2.2 | DB: `get_batches_paginated(agent_id, page, limit)` | `server/database.py` | 无 | 返回 `(items, total)`；SQL `LIMIT ? OFFSET ?` |
| 3.2.3 | DB: `get_batch_with_records(batch_id)` | `server/database.py` | 无 | JOIN `record_hashes` 表，返回 batch 元数据 + records 数组 |
| 3.2.4 | DB: `get_handoffs_by_agent(agent_did)` | `server/database.py` | 无 | 查询 `record_hashes` 中 out_hash = 另一 agent 的 in_hash（跨 batch 匹配） |
| 3.2.5 | `GET /v1/agents/{did}/batches?page=&limit=` | `server/routes/agents.py` | 3.2.1-2 | 分页返回 agent 的 batches |
| 3.2.6 | `GET /v1/batches/{batch_id}` | `server/routes/batches.py` | 3.2.3 | 返回 batch 元数据 + `records: [{record_id, chain_hash, step_type}]` |
| 3.2.7 | `HandoffResponse` model | `server/models.py` | 无 | 字段与 SDK `a2a.py` `Handoff` dataclass 对齐：`source_agent, source_record_id, target_agent, target_record_id, hash_value, source_ts, target_ts, valid, source_batch_id, target_batch_id` |
| 3.2.8 | `GET /v1/agents/{did}/handoffs` | 新增到 `server/routes/agents.py` | 3.2.4, 3.2.7 | 返回该 agent 参与的 handoffs |
| 3.2.9 | Profile `recent_batches` 支持 `?limit=` | `server/routes/agents.py` | 无 | 默认 10，max 100 |
| 3.2.10 | 分页测试 | `server/tests/test_batches.py` | 3.2.5-6 | ≥4 个：第一页/第二页/超出范围/空结果 |
| 3.2.11 | Handoffs 测试 | `server/tests/test_agents.py` | 3.2.8 | ≥3 个：有 handoff/无 handoff/多 agent |
| 3.2.12 | Batch detail 测试 | `server/tests/test_batches.py` | 3.2.6 | ≥3 个：正常/不存在/records 数组完整 |

### 逻辑碰撞检查

| 检查项 | 结果 |
|--------|------|
| 现有 `GET /v1/agents/{did}/profile` 会被影响吗？ | ❌ 不变。分页是新增参数，Profile 端点独立 |
| `HandoffResponse` 字段 ⊇ SDK `Handoff` 字段？ | ✅ 完全覆盖所有 12 个字段（含 `source_batch_id`/`target_batch_id`） |
| 分页默认值？ | `page=1, limit=20`。与 Alex 对齐的格式一致 |
| Handoff 的 DB 查询能否实现？| `record_hashes` 表有 `chain_hash` 和 `batch_id`。跨 batch 匹配 out_hash=in_hash 需要 self-join。需要在 `record_hashes` 表新增 `hash_type` 列区分 in/out hash，或者直接存 `in_hash` + `out_hash` 两列 |
| ⚠️ **发现**：`record_hashes` 表只有 `chain_hash` 一列 | 需要改 DB schema 增加 `in_hash` 和 `out_hash` 列，或改为在 batch upload 时从 record 中提取并存储。**P3-2 新增子任务 3.2.4a** |
| 3.2.4a: DB schema migration | `database.py` 新增 `in_hash TEXT, out_hash TEXT` 列到 `record_hashes`；`batches.py` upload 时提取并存储 |

---

## P3-3: Webhook Attestation Trigger（~1.5h，≥6 新测试）

**背景**：CERTIFICATE-SCHEMA.md Section 3 定义了 webhook payload。Alex 选方案B（push）。
**影响范围**：新文件 `sdk/atlast_ecp/webhook.py`、`sdk/atlast_ecp/config.py`、`sdk/atlast_ecp/cli.py`、`server/routes/batches.py`

### 子任务

| ID | 任务 | 改动文件 | 依赖 | 验收标准 |
|----|------|---------|------|---------|
| 3.3.1 | `webhook.py` — `fire_webhook(payload, url, token)` | 新文件 | 无 | async POST，timeout 5s，retry 1x on 5xx，fail-open（异常只 log 不 raise）。用 `urllib.request` 无外部依赖 |
| 3.3.2 | `build_webhook_payload(batch_data)` | `webhook.py` | 无 | 生成与 CERTIFICATE-SCHEMA.md Section 3 完全一致的 payload：`event, cert_id, agent_did, batch_merkle_root, record_count, attestation_uid, eas_tx_hash, schema_uid, chain_id, on_chain, created_at` |
| 3.3.3 | CLI `atlast config set webhook_url <url>` | `cli.py` | 无 | 写入 `~/.atlast/config.json`；`atlast config set webhook_token <token>` 同理 |
| 3.3.4 | CLI `atlast config get` | `cli.py` | 无 | 显示当前配置（隐藏 token 中间部分） |
| 3.3.5 | `config.py` 新增 `get_webhook_url()`, `get_webhook_token()` | `config.py` | 无 | 优先级：env `ECP_WEBHOOK_URL` > config file > None |
| 3.3.6 | Server 集成：batch 创建后触发 webhook | `server/routes/batches.py` | 3.3.1, 3.3.5 | `upload_batch()` 成功后调用 `fire_webhook()`；webhook 失败不影响 201 响应 |
| 3.3.7 | 测试：webhook 成功发送 | `sdk/tests/test_webhook.py` | 3.3.1-2 | mock HTTP server，验证 payload 字段完整 |
| 3.3.8 | 测试：webhook 失败 fail-open | `sdk/tests/test_webhook.py` | 3.3.1 | 目标不可达时不 raise，返回 False |
| 3.3.9 | 测试：webhook retry on 5xx | `sdk/tests/test_webhook.py` | 3.3.1 | 第一次 500，第二次 200 → 成功 |
| 3.3.10 | 测试：payload 与 CERTIFICATE-SCHEMA.md 一致 | `sdk/tests/test_webhook.py` | 3.3.2 | 逐字段验证 payload keys 完全匹配 Section 3 |
| 3.3.11 | Server webhook 测试 | `server/tests/test_batches.py` | 3.3.6 | batch upload + mock webhook endpoint → 验证调用 |
| 3.3.12 | Config CLI 测试 | `sdk/tests/test_cli.py` 或新文件 | 3.3.3-4 | set/get 往返验证 |

### 逻辑碰撞检查

| 检查项 | 结果 |
|--------|------|
| `webhook.py` 引入新依赖吗？ | ❌ 使用 `urllib.request`（stdlib）。不引入 `aiohttp`/`requests` |
| `config.py` 的 `load_config()` 改变吗？ | ❌ 不变。新增 2 个 getter 函数，`load_config()` 用 `.get()` 自动兼容新字段 |
| CLI `config set` 与现有 `atlast init` 冲突吗？ | ❌ `init` 写 `agent_did`/`endpoint`，`config set` 写任意 key。两者都调 `save_config()` |
| Webhook payload 的 `cert_id` = `batch_id`？ | ✅ 与 CERTIFICATE-SCHEMA.md Section 3 Note 一致 |
| Server 的 `fire_webhook` 是同步还是异步？ | Server 用 FastAPI（async），webhook 发送用 `asyncio` 或 background task，不阻塞响应 |
| Webhook token 与 X-Agent-Key 混淆？ | ❌ 不同 header：webhook 用 `X-ECP-Webhook-Token`，batch upload 用 `X-Agent-Key` |

---

## P3-4: `.well-known` Discovery Endpoint（~1h，≥4 新测试）

**背景**：Enterprise 自动发现 ECP Server 能力。遵循 RFC 8615。
**影响范围**：`ECP-SERVER-SPEC.md`、`server/main.py`、`sdk/atlast_ecp/cli.py`

### 子任务

| ID | 任务 | 改动文件 | 依赖 | 验收标准 |
|----|------|---------|------|---------|
| 3.4.1 | 定义 `.well-known/ecp.json` schema | 文档 | 无 | 字段：`ecp_version`, `server_version`, `endpoints[]`, `capabilities[]`, `chain` (optional) |
| 3.4.2 | Server `GET /.well-known/ecp.json` | `server/main.py` | 3.4.1 | 返回 discovery 文档；`capabilities` 动态反映已启用功能 |
| 3.4.3 | CLI `atlast discover <url>` | `cli.py` | 3.4.1 | 请求 `<url>/.well-known/ecp.json`，格式化展示 server 信息 |
| 3.4.4 | 测试：Server discovery 端点 | `server/tests/test_discovery.py` | 3.4.2 | 返回 200 + 正确 JSON schema |
| 3.4.5 | 测试：capabilities 列表正确 | `server/tests/test_discovery.py` | 3.4.2 | 含 `batch`, `profile`, `leaderboard`, `insights`, `handoffs` |
| 3.4.6 | 测试：CLI discover 解析 | `sdk/tests/test_cli.py` 或新文件 | 3.4.3 | mock response → 正确输出 |
| 3.4.7 | 测试：不可达 URL 优雅报错 | | 3.4.3 | 不 crash，输出错误信息 |

### Discovery 文档格式

```json
{
  "ecp_version": "1.0",
  "server_version": "0.7.0",
  "server_name": "ATLAST Reference ECP Server",
  "endpoints": [
    {"path": "/v1/agents/register", "method": "POST"},
    {"path": "/v1/batches", "method": "POST"},
    {"path": "/v1/agents/{did}/profile", "method": "GET"},
    {"path": "/v1/leaderboard", "method": "GET"},
    {"path": "/v1/insights/performance", "method": "GET"},
    {"path": "/v1/insights/trends", "method": "GET"},
    {"path": "/v1/insights/tools", "method": "GET"},
    {"path": "/v1/agents/{did}/handoffs", "method": "GET"},
    {"path": "/v1/agents/{did}/batches", "method": "GET"},
    {"path": "/v1/batches/{batch_id}", "method": "GET"}
  ],
  "capabilities": ["batch", "profile", "leaderboard", "insights", "handoffs", "discovery"],
  "auth_methods": ["X-Agent-Key"],
  "chain": null
}
```

### 逻辑碰撞检查

| 检查项 | 结果 |
|--------|------|
| `/.well-known/` 路径与 FastAPI 路由冲突？ | ❌ FastAPI 支持任意路径 |
| `ecp_version` 与 `ECP-SPEC.md` 版本一致？ | ✅ 都是 `"1.0"` |
| `endpoints` 列表与实际路由一致？ | ✅ 包含 P3-1/P3-2 新增的所有端点 |
| `chain` 字段为何 null？ | Reference Server 不含链上锚定功能（EAS 在 production server）。如果有，返回 `{chain_id, eas_contract}` |

---

## P3-5: AutoGen Adapter（~1.5h，≥8 新测试）

**背景**：第三个框架适配器。微软 AutoGen v0.4+ 使用 `AgentChat` 模式。
**影响范围**：新文件 `sdk/atlast_ecp/adapters/autogen.py`、`sdk/atlast_ecp/adapters/__init__.py`

### 子任务

| ID | 任务 | 改动文件 | 依赖 | 验收标准 |
|----|------|---------|------|---------|
| 3.5.1 | Runtime import pattern | `autogen.py` | 无 | `try: from autogen import ...; HAS_AUTOGEN = True` 与 LangChain/CrewAI adapter 模式一致 |
| 3.5.2 | `ATLASTAutoGenMiddleware` 类 | `autogen.py` | 3.5.1 | 拦截 `ConversableAgent` 的 `generate_reply` 调用，记录 input/output hash |
| 3.5.3 | `register_atlast(agent)` 便捷函数 | `autogen.py` | 3.5.2 | 一行注册：`register_atlast(my_agent)` |
| 3.5.4 | Multi-agent 消息检测 | `autogen.py` | 3.5.2 | 检测 `sender` ≠ `recipient` 时生成 A2A handoff 风格记录（`meta.handoff = true`） |
| 3.5.5 | Adapters `__init__.py` 注册 | `adapters/__init__.py` | 3.5.1 | 导出 `ATLASTAutoGenMiddleware`, `register_atlast` |
| 3.5.6 | 测试：基本记录 | `sdk/tests/test_adapters.py` | 3.5.2 | mock `ConversableAgent`，触发回复 → 验证 ECP record 生成 |
| 3.5.7 | 测试：multi-agent handoff | `sdk/tests/test_adapters.py` | 3.5.4 | 两个 mock agent 对话 → 验证 handoff record |
| 3.5.8 | 测试：AutoGen 未安装 | `sdk/tests/test_adapters.py` | 3.5.1 | `HAS_AUTOGEN=False` 时 import 不报错 |
| 3.5.9 | 测试：record 格式与 LangChain/CrewAI 一致 | `sdk/tests/test_adapters.py` | 3.5.2 | 验证 record 包含 `ecp, id, ts, agent, action, in_hash, out_hash` 7 个必需字段 |

### 逻辑碰撞检查

| 检查项 | 结果 |
|--------|------|
| AutoGen v0.2 vs v0.4 API 差异？ | v0.4 用 `AgentChat`（新 API），v0.2 用 `ConversableAgent`。优先支持 v0.2（市场存量大），v0.4 作为可选 |
| `register_atlast` 与现有 `atlast.init()` 冲突？ | ❌ 不同层级。`init()` 是全局初始化，`register_atlast()` 是单 agent 级注册 |
| Record 的 `action` 字段值？ | `"autogen_reply"` 或 `"autogen_handoff"`（与 langchain 的 `"langchain_llm_call"` 同层级） |
| A2A handoff record 与 `a2a.py` 兼容？ | ✅ 生成的 record 含 `in_hash`/`out_hash`，可被 `discover_handoffs()` 扫描匹配 |
| 硬依赖 AutoGen？ | ❌ runtime import only。`pip install atlast-ecp` 不安装 AutoGen |

---

## P3-6: ECP-SERVER-SPEC.md v1.1 更新（~30m）

### 子任务

| ID | 任务 | 验收标准 |
|----|------|---------|
| 3.6.1 | Section 5: Insights 端点 | 3 个端点的 request/response 格式，含 `agent_did` 和 `period` 参数 |
| 3.6.2 | Section 6: Batch Detail 端点 | `GET /v1/batches/{batch_id}` response 含 `records` 数组 |
| 3.6.3 | Section 7: Paginated Batch Listing | `GET /v1/agents/{did}/batches?page=&limit=` |
| 3.6.4 | Section 8: Handoffs 端点 | `GET /v1/agents/{did}/handoffs` response 格式 |
| 3.6.5 | Section 9: Discovery | `/.well-known/ecp.json` 完整规范 |
| 3.6.6 | Section 10: Webhook | 引用 CERTIFICATE-SCHEMA.md Section 3，配置方式 |
| 3.6.7 | 版本号 v1.0 → v1.1 | header + changelog |

### 逻辑碰撞检查

| 检查项 | 结果 |
|--------|------|
| 原有 4 个端点文档改变？ | ❌ 不变，只新增 Section 5-10 |
| 新端点路径与现有冲突？ | ❌ 无冲突。所有路径唯一 |

---

## P3-7: PyPI v0.7.0 + GitHub Release（~30m）

### 子任务

| ID | 任务 | 验收标准 |
|----|------|---------|
| 3.7.1 | `pyproject.toml` version → `0.7.0` | 版本号更新 |
| 3.7.2 | `CHANGELOG.md` v0.7.0 条目 | 列出所有 P3 变更：Insights B、API 增强、Webhook、Discovery、AutoGen |
| 3.7.3 | `sdk/atlast_ecp/__init__.py` 版本号同步 | `__version__ = "0.7.0"` |
| 3.7.4 | Git commit + tag + push | `git tag v0.7.0 && git push --tags` |
| 3.7.5 | GitHub Release v0.7.0 | 创建 Release → 触发 GitHub Actions trusted publishing |
| 3.7.6 | 验证 PyPI | `pip install atlast-ecp==0.7.0` 成功 |

---

## P3-8: 全面质量审计（~1.5h）

### 子任务

| ID | 审计项 | 方法 | Pass 标准 |
|----|--------|------|----------|
| 3.8.1 | 全测试套件 | `python3 -m pytest sdk/tests/ server/tests/ -q` | 0 failures, 0 errors |
| 3.8.2 | 跨 SDK hash 一致性 | Python `sha256()` vs Go `Hash()` vs TS `computeHash()` 对相同输入 | 三个 SDK 输出完全相同 |
| 3.8.3 | Merkle cross-SDK 一致性 | Python `build_merkle_tree()` vs Server `build_merkle_root()` | 已有 3 个测试（BUG-1 fix），再加 1 个大数据量测试 |
| 3.8.4 | ECP-SPEC 合规 | 所有模块生成的 record 含 7 个必需字段 | `ecp, id, ts, agent, action, in_hash, out_hash` 全部存在 |
| 3.8.5 | Server-Spec 端点一致性 | 对比 ECP-SERVER-SPEC.md v1.1 与 `server/routes/` 实际路由 | 100% 匹配 |
| 3.8.6 | Adapter 输出一致性 | LangChain/CrewAI/AutoGen record 格式对比 | 所有 record 结构一致 |
| 3.8.7 | CERTIFICATE-SCHEMA webhook 对齐 | 对比 `build_webhook_payload()` 输出与 CERTIFICATE-SCHEMA.md Section 3 | 字段 100% 匹配 |
| 3.8.8 | A2A + Handoff 端点对齐 | `a2a.py` Handoff fields ⊆ API response fields | 全覆盖 |
| 3.8.9 | Config 完整性 | `~/.atlast/config.json` 支持全部字段 | endpoint, api_key, agent_did, webhook_url, webhook_token |
| 3.8.10 | CLI 完整性 | `atlast --help` 列出所有命令 | init, record, flush, push, verify, insights, a2a, proxy, run, register, config, discover |
| 3.8.11 | Import 安全 | `import atlast_ecp` 无副作用，不触发网络请求 | 纯 import 0 网络调用 |
| 3.8.12 | v0.1↔v1.0 兼容 | Insights/A2A/Server 接受两种 record 格式 | nested (v0.1) + flat (v1.0) 都能处理 |

---

## 全局逻辑碰撞矩阵（P0-P3）

### 数据流完整路径

```
Agent Code
  │
  ├─ Layer 0: atlast proxy ──► intercept HTTP ──► core.create_minimal_record()
  ├─ Layer 1: @track / record() ──────────────► core.create_record()
  └─ Layer 2: LangChain/CrewAI/AutoGen adapter ► core.create_record()
  │
  ▼
storage.save_record()  →  ~/.atlast/records/*.jsonl  (本地，P0)
  │
  ▼
atlast flush / push  →  batch.build_merkle_tree()  →  POST /v1/batches  (P1)
  │
  ▼
Server receives  →  merkle.verify_merkle_root()  →  database.save()  (P2-1)
  │
  ├─► fire_webhook()  →  POST to webhook_url  (P3-3, fail-open)
  ├─► GET /v1/insights/*  →  analyze_performance/trends/tools()  (P3-1)
  ├─► GET /v1/agents/{did}/handoffs  →  DB cross-batch match  (P3-2)
  └─► GET /.well-known/ecp.json  →  server capability discovery  (P3-4)
```

### 跨模块依赖图

```
core.py ◄─── wrap.py, record.py, proxy.py, adapters/*
  │
  ▼
storage.py ◄─── cli.py (flush/push), insights.py (load_records)
  │
  ▼
batch.py ◄─── cli.py (flush), server/merkle.py (must match algorithm!)
  │
  ▼
config.py ◄─── cli.py, batch.py, webhook.py (P3-3)
  │
  ▼
webhook.py (P3-3) ◄─── server/routes/batches.py
  │
  ▼
a2a.py ◄─── cli.py (--a2a), adapters/autogen.py (P3-5), server/routes/agents.py (P3-2)
  │
  ▼
verify.py ◄─── cli.py (verify), server/merkle.py
```

### 关键不变量（Invariants）

| # | 不变量 | 守护测试 |
|---|--------|---------|
| 1 | SDK `build_merkle_tree()` 与 Server `build_merkle_root()` 对相同输入产生相同 root | `test_merkle_cross_sdk_*` (3个) |
| 2 | 所有 record 包含 7 个必需字段 | 各模块 test + P3-8.4 审计 |
| 3 | `import atlast_ecp` 无副作用 | P3-8.11 |
| 4 | v0.1 和 v1.0 record 格式都被接受 | P3-8.12 |
| 5 | Adapter 无硬依赖（LangChain/CrewAI/AutoGen） | 各 adapter `HAS_*=False` 测试 |
| 6 | Webhook/网络失败不 crash agent | `test_webhook_fail_open` |
| 7 | Config 新字段不影响旧配置 | `load_config()` 用 `.get()` |

---

## 执行顺序与依赖关系

```
P3-1 (Insights B) ─────────────┐
P3-2 (API Enhancement) ────────┤
P3-3 (Webhook) ────────────────┤──► P3-6 (Spec v1.1) ──► P3-7 (Release) ──► P3-8 (Audit)
P3-4 (Discovery) ──────────────┤
P3-5 (AutoGen Adapter) ────────┘
```

P3-1 到 P3-5 互相独立，可任意顺序执行。P3-6 汇总所有新端点。P3-7 发布。P3-8 终检。

---

## 预算汇总

| 阶段 | 子任务数 | 估时 | 新测试 |
|------|---------|------|--------|
| P3-1 | 12 | 2h | ≥12 |
| P3-2 | 12 | 2h | ≥10 |
| P3-3 | 12 | 1.5h | ≥6 |
| P3-4 | 7 | 1h | ≥4 |
| P3-5 | 9 | 1.5h | ≥8 |
| P3-6 | 7 | 0.5h | — |
| P3-7 | 6 | 0.5h | — |
| P3-8 | 12 | 1.5h | ≥1 |
| **合计** | **77** | **~10.5h** | **≥41** |

完成后预计总测试：**456+**（当前 415 + 41 新增）
