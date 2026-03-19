# ATLAST ECP — Phase 3 详细开发计划

> **目标**：从 "完整 SDK + 参考实现" 进化为 "生产就绪的协议生态"
> **起始版本**：v0.6.1（PyPI + npm 已发布）
> **起始测试**：412 passed, 2 skipped
> **起始 commit**：`935d60a` (main = origin/main)
> **预计总工时**：14-18 小时
> **执行顺序**：P3-1 → P3-2 → P3-3 → P3-4 → P3-5 → P3-6 → P3-7 → P3-8

---

## 当前已完成基线（P0 — P2 Summary）

| 阶段 | 状态 | 核心产出 |
|------|------|---------|
| P0 | ✅ | Bug fixes, core.py 重构, record ID 统一 |
| P1-Infra | ✅ | PyPI v0.6.1, npm v0.1.0, GitHub CI, OpenClaw Plugin |
| P1-Strategy | ✅ | ECP v1.0 Spec, Proxy, CLI 扩展, 5-Level Record, README 全面重写 |
| P1-Adapters | ✅ | LangChain + CrewAI adapters, Insights v0.1 |
| P1-Docs | ✅ | ECP-SPEC.md, ECP-SERVER-SPEC.md, CHANGELOG.md, CERTIFICATE-SCHEMA.md |
| P2-1 | ✅ | Reference ECP Server (FastAPI + SQLite, 4 endpoints, 23 tests, Docker) |
| P2-2 | ✅ | GitHub 社区模板 (Issue/PR templates, CONTRIBUTING, CoC, SECURITY) |
| P2-3 | ✅ | 全球 AI 合规指南 (5 capabilities × 5 regulations) |
| P2-4 | ✅ | A2A 多方验证 (handoff/orphan/blame/DAG, 18 tests) |
| P2-5 | ✅ | Go SDK 骨架 (types/hash/record/storage/verify/CLI) |

**SDK 模块**：20 Python + 3 adapters + 8 server + Go SDK + TS SDK
**测试**：412 passed, 2 skipped (Python + Server)
**发布**：PyPI v0.6.1, npm v0.1.0

---

## 🔴 P0-P2 遗留问题（P3 优先修复）

### BUG-1: Merkle Tree 排序不一致（严重）

**问题**：SDK `batch.py:build_merkle_tree()` **不排序** hashes，按原始顺序配对。Server `merkle.py:build_merkle_root()` **先 sorted()** 再配对。当 record hashes 不是字典序排列时，SDK 生成的 merkle_root 与 Server 验证用的 root 不同 → **batch upload 的 merkle 验证会误报失败**。

**影响**：生产环境中 `POST /v1/batches` 带 `merkle_root` 时，如果 records 不是字典序，server 会拒绝合法 batch。

**修复方案**：统一为 **不排序**（SDK 行为优先，因为已有生产数据）。修改 `server/merkle.py` 删除 `sorted()` 调用。

**验证**：写跨 SDK-Server 一致性测试。

### BUG-2: ECP-SERVER-SPEC.md DID 示例格式不一致（低）

**问题**：Spec 中 DID 示例用 `did:ecp:z6Mk...`（multibase 风格），实际 SDK 用 `did:ecp:{32 hex chars}`。不影响功能，但会误导开发者。

**修复**：P3-6 中统一所有示例为 `did:ecp:a1b2c3d4...` hex 格式。

---

## P3 任务清单

### P3-1: Insights Layer B — 拆分子端点 (~2h) ⭐ 高优先级

**背景**：Alex 提出 Insights 拆分为 3 个子端点，方便 Dashboard 异步加载各面板。当前 `analyze_records()` 返回单一大对象，需要拆为可独立调用的模块。

**目标**：
- SDK 内部：`insights.py` 拆为 `performance()`, `trends()`, `tools()` 三个独立函数
- Reference Server：新增 3 个 API 端点
- CLI：`atlast insights --section performance|trends|tools`

| ID | 任务 | 依赖 | 验收标准 | 估时 |
|----|------|------|---------|------|
| 3.1.1 | 拆分 `insights.py` 内部函数 | 无 | `analyze_performance()`, `analyze_trends()`, `analyze_tools()` 三个函数，各自独立可调用；原 `analyze_records()` 保留为聚合调用 | 30m |
| 3.1.2 | CLI `--section` 参数 | 3.1.1 | `atlast insights --section performance` 只输出性能分析；无参数 = 全部 | 15m |
| 3.1.3 | Server `/v1/insights/performance` | 3.1.1 | GET 端点，接受 `agent_did` + `period` 参数，返回延迟/吞吐/成功率 | 20m |
| 3.1.4 | Server `/v1/insights/trends` | 3.1.1 | GET 端点，返回时序趋势数据（按日/周聚合） | 20m |
| 3.1.5 | Server `/v1/insights/tools` | 3.1.1 | GET 端点，返回 tool 使用分布 + 耗时排名 | 15m |
| 3.1.6 | 测试 | 3.1.2-3.1.5 | ≥12 个新测试；覆盖各子函数 + API 端点 + CLI section 参数 | 20m |

**与 P0-P2 逻辑闭环**：
- ✅ `analyze_records()` 向后兼容（聚合三个子函数）
- ✅ 子端点响应格式与 Alex 对齐的拆分方案一致（performance/trends/tools）
- ✅ Server 端点遵循 ECP-SERVER-SPEC.md 的 `/v1/` prefix 约定
- ✅ 不改变现有 CLI `atlast insights` 的默认行为

---

### P3-2: API 增强 — 分页 + Batch Records + Handoffs (~2h)

**背景**：Alex 对齐时提出 Dashboard 需要分页、batch 详情返回 records 数组、以及 handoffs 查询端点。

| ID | 任务 | 依赖 | 验收标准 | 估时 |
|----|------|------|---------|------|
| 3.2.1 | Batch listing 分页 | 无 | `GET /v1/agents/{did}/batches?page=1&limit=20`，返回 `total`, `page`, `limit`, `items` | 20m |
| 3.2.2 | Batch detail 返回 records | 无 | `GET /v1/batches/{batch_id}` 返回 batch 元数据 + `records: [hash1, hash2, ...]` | 20m |
| 3.2.3 | Profile 分页 | 无 | `GET /v1/agents/{did}/profile` 的 `recent_batches` 支持 `?limit=` | 10m |
| 3.2.4 | Handoffs 端点 | 无 | `GET /v1/agents/{did}/handoffs` 返回该 agent 参与的所有 A2A handoff 记录 | 25m |
| 3.2.5 | Server 实现上述端点 | 3.2.1-3.2.4 | Reference Server 同步添加所有新端点 | 20m |
| 3.2.6 | 测试 | 3.2.5 | ≥10 个新测试 | 15m |

**与 P0-P2 逻辑闭环**：
- ✅ 分页格式与 ECP-SERVER-SPEC.md 保持一致风格
- ✅ Handoffs 端点返回的数据结构与 A2A (`a2a.py`) 的 `Handoff` dataclass 字段对齐
- ✅ `batch_id` 与 A2A 的 `source_batch_id`/`target_batch_id` 字段呼应（P2-4 commit 4a009fc）
- ✅ 分页 response 遵循 `{total, page, limit, items}` 通用模式

---

### P3-3: Webhook Attestation Trigger (~1.5h)

**背景**：CERTIFICATE-SCHEMA.md Section 3 定义了 webhook payload 格式。Alex 选了方案B（webhook push）。需要在 SDK/Server 侧实现 webhook 发送逻辑。

| ID | 任务 | 依赖 | 验收标准 | 估时 |
|----|------|------|---------|------|
| 3.3.1 | `sdk/atlast_ecp/webhook.py` | 无 | `fire_webhook(payload, url, token)` — async POST, fail-open, retry 1x, timeout 5s | 20m |
| 3.3.2 | CLI `atlast config set webhook_url <url>` | 3.3.1 | 写入 `~/.atlast/config.json`；`webhook_token` 同理 | 15m |
| 3.3.3 | Server webhook 集成 | 3.3.1 | Reference Server 在 batch 创建成功后调用 `fire_webhook()` | 15m |
| 3.3.4 | Webhook payload 与 CERTIFICATE-SCHEMA.md 对齐 | 3.3.1 | payload 字段 100% 匹配 Section 3 定义 | 10m |
| 3.3.5 | 测试 | 3.3.1-3.3.4 | ≥6 个测试（成功/失败/超时/重试/fail-open/payload 验证） | 15m |

**与 P0-P2 逻辑闭环**：
- ✅ Payload 格式与 `CERTIFICATE-SCHEMA.md` Section 3 完全一致
- ✅ `X-ECP-Webhook-Token` header 与 CERTIFICATE-SCHEMA.md 定义一致
- ✅ `cert_id` = `batch_id` 映射关系与 CERTIFICATE-SCHEMA.md Section 3 Note 一致
- ✅ Fail-open 设计符合 ECP 核心原则（webhook 失败不阻塞 batch 创建）
- ✅ Config 存储复用 P1 的 `config.py` (`~/.atlast/config.json`)

---

### P3-4: `.well-known` Discovery Endpoint (~1h)

**背景**：Enterprise 需要发现 ECP Server 的能力。Boss 决定 P3 做 spec，P4 做 enterprise 对接。

| ID | 任务 | 依赖 | 验收标准 | 估时 |
|----|------|------|---------|------|
| 3.4.1 | `.well-known/ecp.json` 规范 | 无 | 定义标准 discovery 文档：版本、支持的端点列表、capabilities（batch/anchor/a2a/insights）、EAS chain info | 15m |
| 3.4.2 | 写入 ECP-SERVER-SPEC.md | 3.4.1 | 在现有 spec 末尾添加 Section 5: Discovery | 10m |
| 3.4.3 | Reference Server 实现 | 3.4.1 | `GET /.well-known/ecp.json` 返回 discovery 文档 | 15m |
| 3.4.4 | CLI `atlast discover <url>` | 3.4.3 | 读取远端 `.well-known/ecp.json`，展示 server 能力 | 15m |
| 3.4.5 | 测试 | 3.4.3-3.4.4 | ≥4 个测试 | 10m |

**与 P0-P2 逻辑闭环**：
- ✅ Discovery 返回的端点列表与 ECP-SERVER-SPEC.md 的 4+3 个端点一致
- ✅ `capabilities` 字段反映实际已实现的功能（batch ✅, a2a ✅, insights ✅, anchor ❌可选）
- ✅ 遵循 RFC 8615 (`.well-known` URI) 标准
- ✅ `ecp_version` 字段与 ECP-SPEC.md 的版本号一致

---

### P3-5: AutoGen Adapter (~1.5h)

**背景**：继 LangChain + CrewAI 后的第三个框架适配器。AutoGen 是微软的多 agent 框架，市场份额增长快。

| ID | 任务 | 依赖 | 验收标准 | 估时 |
|----|------|------|---------|------|
| 3.5.1 | `sdk/atlast_ecp/adapters/autogen.py` | 无 | `ATLASTAutoGenMiddleware` — 拦截 AutoGen v0.4+ 的 `AgentChat` 消息流 | 30m |
| 3.5.2 | 支持 AutoGen `ConversableAgent` | 3.5.1 | 注册为 `reply_func` 或使用 middleware pattern | 15m |
| 3.5.3 | 多 agent 场景 | 3.5.1 | 自动检测 agent 间消息传递，生成 A2A handoff 记录 | 20m |
| 3.5.4 | 测试 | 3.5.1-3.5.3 | ≥8 个测试（mock AutoGen classes，不依赖安装） | 15m |

**与 P0-P2 逻辑闭环**：
- ✅ 零依赖原则：`import autogen` 在运行时，`HAS_AUTOGEN` flag（与 LangChain/CrewAI adapter 模式一致）
- ✅ 调用 `core.create_record()` 生成 ECP 记录（与其他 adapter 一致）
- ✅ A2A handoff 记录与 `a2a.py` 的 `Handoff` dataclass 兼容
- ✅ `adapters/__init__.py` 注册新 adapter
- ✅ 不硬依赖 AutoGen 版本（runtime import + try/except）

---

### P3-6: ECP-SERVER-SPEC.md v1.1 更新 (~30m)

**背景**：P3 新增了多个端点（insights × 3, handoffs, discovery, webhook），需要更新规范文档。

| ID | 任务 | 依赖 | 验收标准 | 估时 |
|----|------|------|---------|------|
| 3.6.1 | 添加 Insights 端点文档 | P3-1 | 3 个 insights 端点的请求/响应格式 | 10m |
| 3.6.2 | 添加 Handoffs 端点文档 | P3-2 | handoffs 端点请求/响应格式 | 5m |
| 3.6.3 | 添加 Webhook 配置文档 | P3-3 | webhook 配置方式 + payload 格式引用 CERTIFICATE-SCHEMA.md | 5m |
| 3.6.4 | 添加 Discovery 端点文档 | P3-4 | `.well-known/ecp.json` 完整规范 | 5m |
| 3.6.5 | 版本号更新 | 3.6.1-3.6.4 | v1.0 → v1.1，添加变更摘要 | 5m |

---

### P3-7: PyPI v0.7.0 + GitHub Release (~30m)

| ID | 任务 | 依赖 | 验收标准 | 估时 |
|----|------|------|---------|------|
| 3.7.1 | `pyproject.toml` 版本 → 0.7.0 | 全部 P3 | version 字段更新 | 2m |
| 3.7.2 | CHANGELOG.md 更新 | 3.7.1 | v0.7.0 条目：Insights B, API 增强, Webhook, Discovery, AutoGen | 10m |
| 3.7.3 | Git commit + push | 3.7.2 | 所有 P3 代码 + 文档推到 origin/main | 5m |
| 3.7.4 | GitHub Release v0.7.0 | 3.7.3 | 创建 Release → 触发 GitHub Actions → PyPI 发布 | 10m |
| 3.7.5 | 验证 PyPI | 3.7.4 | `pip install atlast-ecp==0.7.0` 成功 | 3m |

---

### P3-8: 全面质量审计 (~1.5h)

| ID | 任务 | 依赖 | 验收标准 | 估时 |
|----|------|------|---------|------|
| 3.8.1 | 全测试套件 | 全部 | `python3 -m pytest` 全部 pass，0 regressions | 10m |
| 3.8.2 | Cross-SDK hash 一致性 | 3.8.1 | Python `sha256()` = Go `Hash()` = TS `computeHash()` 对相同输入 | 15m |
| 3.8.3 | ECP-SPEC 合规检查 | 3.8.1 | 所有模块生成的记录符合 ECP-SPEC.md v1.0 | 15m |
| 3.8.4 | Server-SDK 端点一致性 | 3.8.1 | Reference Server 端点与 ECP-SERVER-SPEC.md v1.1 100% 对齐 | 10m |
| 3.8.5 | Adapter 一致性 | 3.8.1 | LangChain/CrewAI/AutoGen 三个 adapter 的 record 输出格式一致 | 10m |
| 3.8.6 | CERTIFICATE-SCHEMA 对齐 | 3.8.1 | webhook payload 与 CERTIFICATE-SCHEMA.md Section 3 一致 | 5m |
| 3.8.7 | A2A + Handoff 端点一致性 | 3.8.1 | `a2a.py` Handoff fields ⊆ `/v1/agents/{did}/handoffs` response fields | 10m |
| 3.8.8 | Config 路径验证 | 3.8.1 | `~/.atlast/config.json` 支持所有新增字段 (webhook_url, webhook_token) | 5m |
| 3.8.9 | CLI 子命令完整性 | 3.8.1 | `atlast --help` 列出所有命令；每个子命令 `--help` 正常 | 5m |

---

## P3 不做（列入 P4+）

| 项目 | 原因 | 计划阶段 |
|------|------|---------|
| Base Mainnet 迁移 | Sepolia 余额足够测试；Mainnet 需要真实 ETH | P4 |
| Enterprise 外部数据源 | Boss 决定 P4 roadmap，等真实客户需求 | P4 |
| IETF/W3C 标准草案 | 协议还在快速迭代，过早提交浪费时间 | P4+ |
| Gateway 合并 | 技术限制 + 收益不明确 | 不做 |
| TS SDK v0.2.0 | TS 当前 v0.1.0 够用，Python 是主战场 | P4 |
| Go SDK 测试 | Go 未安装，需要 CI 环境 | P4 |
| AIP/ASP/ACP 子协议 | 路线图上 Q3-Q4 2026 | P5+ |
| Insights Layer C (Agent 自优化) | 需要足够数据积累 | P4+ |

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| AutoGen API 变更 (v0.4 vs v0.2) | 中 | 中 | runtime import + version detect |
| Webhook 在 Reference Server 无外部验证目标 | 低 | 低 | 使用 httpbin 或 mock server 测试 |
| Insights 拆分破坏现有 JSON 输出 | 中 | 高 | `analyze_records()` 保持向后兼容 |
| 新端点与 Alex Production Server 不一致 | 中 | 中 | P3 完成后发 alignment 给 Alex |

---

## 执行检查清单

- [ ] P3-1: Insights 拆分 → `analyze_performance()` / `analyze_trends()` / `analyze_tools()`
- [ ] P3-2: API 增强 → 分页 + batch records + handoffs
- [ ] P3-3: Webhook → `fire_webhook()` + config + server 集成
- [ ] P3-4: Discovery → `.well-known/ecp.json` + CLI `atlast discover`
- [ ] P3-5: AutoGen Adapter → `ATLASTAutoGenMiddleware`
- [ ] P3-6: ECP-SERVER-SPEC.md v1.1
- [ ] P3-7: PyPI v0.7.0 发布
- [ ] P3-8: 全面质量审计（0 regressions, 跨 SDK 一致性）

---

## 逻辑碰撞验证：P0-P3 全局一致性矩阵

### 1. 数据流一致性

```
Agent Code
  ↓ (Layer 0: Proxy intercepts, or Layer 1: @track, or Layer 2: Adapter callback)
core.create_record()          ← P0 核心, 所有路径汇聚
  ↓
storage.save()                ← 本地 .jsonl
  ↓
atlast flush / atlast push    ← P1 CLI
  ↓
POST /v1/batches              ← P1 路由, P2-1 Server 实现
  ↓
Server stores + fire_webhook  ← P3-3 新增
  ↓
.well-known/ecp.json          ← P3-4 新增 (discovery)
```

**验证**：✅ 每一步的数据格式向下兼容，新功能是追加不是替换。

### 2. Record Format 兼容性

| 版本 | 格式 | 产出模块 | 消费模块 |
|------|------|---------|---------|
| v0.1 | nested (input/reasoning/execution) | 旧 SDK | Server accepts ✅, insights accepts ✅ |
| v1.0 L1 | flat 7 fields | Proxy, @track minimal | Server accepts ✅, insights accepts ✅ |
| v1.0 L2-L5 | flat 7 + optional fields | SDK full | Server accepts ✅, insights accepts ✅ |

**验证**：✅ `analyze_records()` 在 P3-1 拆分后仍然接受所有版本格式。

### 3. 端点路由一致性

| 端点 | ECP-SERVER-SPEC | Reference Server | SDK CLI |
|------|----------------|-------------------|---------|
| `POST /v1/agents/register` | v1.0 ✅ | P2-1 ✅ | `atlast register` ✅ |
| `POST /v1/batches` | v1.0 ✅ | P2-1 ✅ | `atlast flush` ✅ |
| `GET /v1/agents/{did}/profile` | v1.0 ✅ | P2-1 ✅ | — |
| `GET /v1/leaderboard` | v1.0 ✅ | P2-1 ✅ | — |
| `GET /v1/insights/performance` | v1.1 (P3) | P3-1 🔲 | `atlast insights --section perf` 🔲 |
| `GET /v1/insights/trends` | v1.1 (P3) | P3-1 🔲 | `atlast insights --section trends` 🔲 |
| `GET /v1/insights/tools` | v1.1 (P3) | P3-1 🔲 | `atlast insights --section tools` 🔲 |
| `GET /v1/agents/{did}/handoffs` | v1.1 (P3) | P3-2 🔲 | `atlast a2a --agent {did}` 🔲 |
| `GET /.well-known/ecp.json` | v1.1 (P3) | P3-4 🔲 | `atlast discover` 🔲 |

**验证**：✅ 所有新端点在 P3-6 中统一写入 ECP-SERVER-SPEC.md v1.1。

### 4. 分工边界检查

| 模块 | 负责人 | P3 是否触碰 | 合规 |
|------|--------|------------|------|
| `atlast-ecp/` 全部 | Atlas | ✅ 触碰 | ✅ 在职责范围内 |
| `llachat-platform/` | Alex | ❌ 不触碰 | ✅ 铁律遵守 |
| Production API (api.llachat.com) | Alex | ❌ 不触碰 | ✅ |
| Trust Score 算法 | Alex 私有 | ❌ 不触碰 | ✅ Boss 决策 |
| Reference Server `scoring.py` | Atlas | ✅ 已有，P3 不改 | ✅ 独立实现，非 LLaChat 算法 |

### 5. 配置系统一致性

```json
// ~/.atlast/config.json — P3 后完整字段
{
  "endpoint": "https://api.example.com",    // P1 已有
  "api_key": "atl_xxx",                     // P1 已有
  "agent_did": "did:ecp:xxx",               // P1 已有
  "webhook_url": "https://...",             // P3-3 新增
  "webhook_token": "ecp-internal-xxx"       // P3-3 新增
}
```

**验证**：✅ `config.py` 的 `load_config()` 使用 `.get()` 读取，新字段不影响旧配置。

### 6. 跨系统接口一致性（Atlas ↔ Alex）

| 接口 | Atlas 状态 | Alex 需要 | 对齐状态 |
|------|-----------|-----------|---------|
| ECP 数据格式 | ECP-SPEC.md v1.0 ✅ | Dashboard 展示 | ✅ 已对齐 |
| Certificate 字段 | CERTIFICATE-SCHEMA.md ✅ | DB 表结构 | ✅ 已对齐 |
| Webhook payload | P3-3 实现 🔲 | `/v1/internal/ecp-webhook` 端点 | ✅ 格式已对齐，实现待双方各做 |
| Insights 拆分 | P3-1 实现 🔲 | Dashboard 3 个 panel | ✅ Alex 提出，Atlas 同意 |
| 分页格式 | P3-2 实现 🔲 | Dashboard 列表页 | ✅ `{total,page,limit,items}` 已对齐 |
| Handoffs API | P3-2 实现 🔲 | Dashboard handoff 视图 | ✅ Alex 提出，Atlas 同意 |

### 7. Hash 算法一致性

| SDK | 函数 | 算法 | 输入规范化 |
|-----|------|------|-----------|
| Python | `core.compute_hash()` | SHA-256 | `json.dumps(sort_keys=True)` |
| TypeScript | `computeHash()` | SHA-256 | canonical JSON sort |
| Go | `Hash()` | SHA-256 | `json.Marshal()` (Go 默认 sorted keys) |
| OpenClaw Plugin | `canonicalJSON()` | SHA-256 | recursive sort (P2 audit 修复) |
| Reference Server | `merkle.py` | SHA-256 | 同 Python SDK |

**验证**：✅ 所有 SDK 对相同输入产生相同 hash（P2 审计已验证）。

### 8. DID 格式一致性

| 位置 | DID 前缀 | 格式 |
|------|---------|------|
| `identity.py` | `did:ecp:` | `did:ecp:` + 32 hex |
| `CERTIFICATE-SCHEMA.md` | `did:ecp:` | ✅ 一致 |
| `ECP-SERVER-SPEC.md` | `did:ecp:z6Mk...` | ⚠️ 示例用了不同后缀格式 |
| Reference Server | `did:ecp:` | ✅ 一致 |
| Production DB | `did:ecp:` | ✅ Alex 确认 |

**注意**：ECP-SERVER-SPEC.md 的示例用了 `z6Mk` multibase 风格，而实际 SDK 用 hex。P3-6 中统一示例为 hex 格式。

---

## 总预算

| 阶段 | 估时 | 新测试 |
|------|------|--------|
| P3-1 Insights B | 2h | ≥12 |
| P3-2 API 增强 | 2h | ≥10 |
| P3-3 Webhook | 1.5h | ≥6 |
| P3-4 Discovery | 1h | ≥4 |
| P3-5 AutoGen | 1.5h | ≥8 |
| P3-6 Spec v1.1 | 0.5h | — |
| P3-7 Release | 0.5h | — |
| P3-8 审计 | 1.5h | — |
| **合计** | **~10.5h** | **≥40 新测试** |

预计完成后总测试数：**450+**
