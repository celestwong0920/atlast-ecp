# Phase 6: Market-Ready Polish + Standardization Prep

> **目标**: 零遗留 → 白皮书最终版 → 标准化文件 → 反滥用设计 → 开源发布就绪
> **原则**: 每个任务可独立验证 · 不引入新依赖 · 不与其他 section 逻辑冲突
> **生成时间**: 2026-03-22 22:15 MYT（v2 — 基于 R1-R8 已完成后的最终版）

---

## ✅ Section R — 遗留清零（8/8 已完成）

> commit `f05f033`，2026-03-22

| # | 任务 | 状态 |
|---|------|------|
| R1 | README npm 包名 `atlast-ecp-ts` → `@atlast/sdk` | ✅ |
| R2 | README TS SDK test count 12 → 14 | ✅ |
| R3 | CHANGELOG v0.8.0 补充 17 项 Phase 5 成果 | ✅ |
| R4 | npm-publish.yml 确认正确 | ✅ |
| R5 | Go SDK import path `sdk-go` → `sdk/go` | ✅ |
| R6 | Whitepaper Trust Score 0-1000 独立标准说明（EN+ZH） | ✅ |
| R7 | ECP-SPEC §7.2 batch protocol version vs record format version | ✅ |
| R8 | G1-G5 Alex 通知标记完成，Phase 5 = 100% | ✅ |

---

## Section A — 白皮书最终版（6 项）

| # | 任务 | 说明 | 依赖 | 验证方式 |
|---|------|------|------|---------|
| A1 | ZH 白皮书 sync v2.2 | ZH 版缺少 v2.2 部分新增内容（工作证书 mockup、用户旅程 6 步骤细节） | 无 | diff EN vs ZH 关键段落 |
| A2 | ZH Litepaper sync | 同步商业模式 4 层、TAM $19B | 无 | 对比 EN litepaper |
| A3 | Trust Score 章节完善 | 添加平台可组合说明 + Alex 维度映射示例（Reliability/Transparency/Efficiency/Authority → α/β/γ） | F1 | EN+ZH 同步 |
| A4 | 全文最终逻辑审查 | grep 扫描：零 `$X`、零 `TODO`、零矛盾、版本号全一致 | A1-A3 | 自动化脚本 |
| A5 | 文档历史更新 | EN+ZH 版本号确认 2.2，文档历史条目完整 | A4 | 检查 |
| A6 | PDF 生成 + Desktop 备份 | 最终版复制到 Desktop | A5 | 文件存在 |

---

## Section B — 标准化准备（7 项）

| # | 任务 | 说明 | 依赖 | 验证方式 |
|---|------|------|------|---------|
| B1 | OpenAPI 3.1 Spec | ECP Server 全部 11 个端点的正式 OpenAPI YAML | 无 | `swagger-cli validate` 或 `redocly lint` |
| B2 | JSON Schema — ECP Record v1.0 | Minimal 6-field 格式 + Full nested 格式 | 无 | ajv validate 实际记录通过 |
| B3 | JSON Schema — Batch Payload | SDK → LLaChat 的 batch submit payload | 无 | ajv validate 实际 payload 通过 |
| B4 | JSON Schema — Webhook Payload | attestation.anchored 事件 payload | 无 | ajv validate 实际 webhook 通过 |
| B5 | ECP-SPEC v2.1 更新 | 同步：`in_hash`/`out_hash` 字段、`a2a_delegated` flag、`a2a_call` action type | B2 | spec 反映实际代码 |
| B6 | IETF Internet-Draft 格式评估 | 研究 xml2rfc、I-D 提交流程、写转换计划文档（不实际转换） | B5 | 评估文档 |
| B7 | W3C VC/DID 映射文档 | `did:ecp` ↔ W3C DID Core、ECP Record ↔ Verifiable Credential 的映射 | 无 | 映射表 |

---

## Section C — 反滥用框架（6 项）

| # | 任务 | 说明 | 依赖 | 验证方式 |
|---|------|------|------|---------|
| C1 | Anti-Abuse 设计总纲 | 总体策略文档：攻击面分析、防护层级、检测 vs 预防 | 无 | 设计文档 |
| C2 | Batch Spam 检测 | 规范 + 实现：同一 agent 短时间大量空/重复 batch（Server 端检测） | D2 | 测试 + 文档 |
| C3 | Timestamp 造假防护 | 规范 + 实现：batch_ts 与 server 时间偏差超过阈值拒绝/标记 | 无 | 测试 |
| C4 | Trust Score Anti-Gaming | 设计文档：Sybil attack、flag manipulation、cherry-picking batches | 无 | 设计文档 |
| C5 | Self-Deploy Gas Abuse | 设计文档：开源后自部署场景的 EAS 滥用防护 | 无 | 设计文档 |
| C6 | SDK 端节流 | 客户端最小 batch 间隔（默认 60s）+ 单 batch 最大 records（默认 1000） | 无 | SDK 测试 |

---

## Section D — 代码质量提升（10 项）

| # | 任务 | 说明 | 依赖 | 验证方式 |
|---|------|------|------|---------|
| D1 | Python SDK coverage → 80% | 从 63% 提升，重点覆盖 batch.py、wrap.py、proxy.py 未测路径 | 无 | `pytest --cov` ≥ 80% |
| D2 | Server tests 16 → 30+ | 新增：cron status、discovery 字段验证、metrics 格式、error paths、DB failure | 无 | pytest 通过 |
| D3 | TS SDK tests 14 → 25+ | 新增：batch upload、wrap mock、track decorator、identity persistence | 无 | jest 通过 |
| D4 | Streaming E2E test | Mock streaming response → `_RecordedStream` → 验证完整记录 | 无 | 测试通过 |
| D5 | Server 过时注释清理 | `verify.py:94` "Phase 5" 注释、`verify.py:110` "will use Redis" 注释 | 无 | grep 确认 |
| D6 | Redis 实际使用或移除 | Redis 已配置但未使用。选择：(a) 用于 stats 持久化 (b) 移除配置 | 无 | 代码干净 |
| D7 | Security audit | `pip-audit` + `npm audit` + Go `govulncheck` | 无 | 零 critical/high |
| D8 | Go SDK 测试验证 | `go test ./...` 确认通过，修复 import path 变更后的问题 | R5 | go test 通过 |
| D9 | Type hints 完善 | Python SDK 所有公开 API 100% type hints | 无 | mypy 检查 |
| D10 | CI 增强 | CI 加 Server tests + Go tests + coverage 上传 | D1-D3 | CI 全绿 |

---

## Section E — 文档完善（7 项）

| # | 任务 | 说明 | 依赖 | 验证方式 |
|---|------|------|------|---------|
| E1 | SDK Quick Start 更新 | 反映 v0.8.0：streaming wrap、adapters、`atlast run`、`atlast flush --endpoint` | R1 | README 准确 |
| E2 | Server API Reference | 基于 OpenAPI 生成 11 个端点的请求/响应文档 | B1 | 文档完整 |
| E3 | Deployment Guide | Railway 部署步骤、环境变量清单、Postgres/Redis 配置 | 无 | 新用户可跟随 |
| E4 | Architecture Decision Records | 5 个关键 ADR：Commit-Reveal、单向 Push、fail-open、Merkle 不排序、Ed25519 | 无 | ADR 文件 |
| E5 | Migration Guide 0.7→0.8 | Breaking changes、新 API、包名变更 `atlast-ecp-ts`→`@atlast/sdk` | 无 | 文档 |
| E6 | 中文 README 同步 | README.zh-CN.md 反映最新状态 | R1 | 和 EN 版对齐 |
| E7 | CONTRIBUTING.md 更新 | 添加 monorepo 结构说明、测试命令、PR 流程 | 无 | 文档 |

---

## Section F — Alex 对齐收尾（3 项）

| # | 任务 | 说明 | 依赖 | 验证方式 |
|---|------|------|------|---------|
| F1 | Trust Score 算法对齐 | 与 Alex 最终确认：Protocol 3 维度 → Product 4 维度映射文档化 | 无 | 双方 memory + 文档 |
| F2 | HMAC fail-closed 切换计划 | 与 Alex 约定切换时间 + 测试方案 | 无 | 计划文档 |
| F3 | Phase 6 完成后互验 | 全部任务完成后双方交叉验证一次 | 全部完成 | 互验通过 |

---

## 执行顺序（逻辑依赖图）

```
┌─────────────────────────────────────────┐
│ Week 1: 基础层                           │
│                                          │
│  B1-B4 (OpenAPI+Schema)  ──────┐        │
│  D1-D4 (Coverage+Tests)  ──┐   │        │
│  D5-D6 (代码清理)         │   │        │
│  F1 (Trust Score对齐)      │   │        │
│                              ↓   ↓        │
├──────────────────────────────────────────┤
│ Week 2: 内容层                           │
│                                          │
│  A1-A6 (白皮书最终版)   ← F1            │
│  B5-B7 (标准化文件)     ← B1-B4         │
│  E1-E7 (文档)           ← B1, R1        │
│                                          │
├──────────────────────────────────────────┤
│ Week 3: 防护层 + 收尾                    │
│                                          │
│  C1-C6 (反滥用)         ← D2            │
│  D7-D10 (安全+CI)       ← D1-D3         │
│  F2-F3 (Alex收尾+互验)  ← 全部          │
│                                          │
└──────────────────────────────────────────┘
```

---

## 逻辑碰撞检查矩阵

| 任务对 | 潜在冲突 | 防护措施 |
|--------|---------|---------|
| A3 ↔ F1 | Trust Score 写入白皮书前需 Alex 共识 | **F1 先做 → A3 基于共识写** |
| B1 ↔ Server 代码 | OpenAPI 必须反映实际端点 | **从代码路由自动提取，不手写** |
| B2-B4 ↔ INTERFACE-CONTRACT | Schema 必须和接口契约一致 | **以 INTERFACE-CONTRACT.md 为 source of truth** |
| C2 ↔ 现有 batch 流程 | Spam 检测不能误拦正常 batch | **只 flag 不拒绝 + 可配置阈值** |
| C6 ↔ batch.py scheduler | SDK 节流不修改 batch 核心逻辑 | **新增 throttle 层包裹，不改 run_batch()** |
| D6 ↔ Railway Redis | 移除 Redis 会影响 Railway 配置 | **选方案 (a) 用于 stats，不移除** |
| E1 ↔ R1 | Quick Start 引用正确包名 | **R1 已完成 ✅** |
| D5 ↔ verify.py | 改注释不改逻辑 | **只改注释文字** |

---

## 任务统计

| Section | 数量 | 状态 |
|---------|------|------|
| R — 遗留清零 | 8 | ✅ **全部完成** |
| A — 白皮书最终版 | 6 | 🔲 |
| B — 标准化准备 | 7 | 🔲 |
| C — 反滥用框架 | 6 | 🔲 |
| D — 代码质量 | 10 | 🔲 |
| E — 文档完善 | 7 | 🔲 |
| F — Alex 对齐 | 3 | 🔲 |
| **合计** | **47** | **8 done / 39 remaining** |

---

## 完成标准（13 项）

1. ✅ Phase 0-5 遗留全部清零（R1-R8）
2. 🔲 白皮书 EN+ZH 最终版，零矛盾零 placeholder
3. 🔲 OpenAPI 3.1 spec（YAML，可验证）
4. 🔲 3 个 JSON Schema 文件（record、batch、webhook）
5. 🔲 ECP-SPEC v2.1 反映所有实际代码
6. 🔲 Python SDK coverage ≥ 80%
7. 🔲 Server tests ≥ 30
8. 🔲 TS SDK tests ≥ 25
9. 🔲 Anti-Abuse 设计文档 + 基础检测实现
10. 🔲 零 critical/high security vulnerability
11. 🔲 所有 README/文档准确反映当前状态
12. 🔲 Trust Score 算法 Alex 最终对齐文档化
13. 🔲 IETF/W3C 评估文档完成

---

*Version: 2.0 | Created: 2026-03-22 22:15 MYT | R1-R8 completed: 2026-03-22 22:10 MYT*
