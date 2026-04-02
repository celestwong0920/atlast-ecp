# ATLAST Protocol — 用户视角测试手册

> **给 Boss 的完整测试指南**  
> 你不需要写任何代码。每一步都有具体的命令可以复制粘贴。  
> 预计总测试时间：30-45 分钟

---

## 目录

1. [测试前准备](#1-测试前准备)
2. [测试 A：EAS Explorer 链上验证](#2-测试-a-eas-explorer-链上验证)
3. [测试 B：Dashboard UI 验证](#3-测试-b-dashboard-ui-验证)
4. [测试 C：9 个 Agent 真实用户场景](#4-测试-c-9-个-agent-真实用户场景)
5. [测试 D：API 数据验证](#5-测试-d-api-数据验证)
6. [测试 E：Alex 侧 LLAChat 数据确认](#6-测试-e-alex-侧-llachat-数据确认)
7. [测试结果记录表](#7-测试结果记录表)

---

## 1. 测试前准备

### 你需要的工具
- 浏览器（Chrome）
- 终端（Terminal.app）
- 能 SSH 到 Mac Mini（命令已准备好，复制粘贴即可）

### 测试环境信息
| 项目 | 地址 |
|------|------|
| ECP Server | https://api.weba0.com |
| LLAChat API | https://api.llachat.com |
| EAS Explorer | https://base.easscan.org |
| Dashboard | https://api.weba0.com/dashboard |
| Mac Mini SSH | `ssh mad-imac1@100.79.169.126` |
| PyPI 包 | `pip install atlast-ecp==0.11.0` |

---

## 2. 测试 A：EAS Explorer 链上验证

**场景**：验证 ATLAST 的数据确实写入了区块链，任何人都可以公开查看。

### 步骤

1. **打开浏览器**，访问以下两个链接：

   **链接 1（Super-batch 1）：**
   ```
   https://base.easscan.org/attestation/view/0xbf5aa9429b44743f9cd0175697103ea42538f25253d029143bc77b5b0de7c609
   ```

   **链接 2（Super-batch 2）：**
   ```
   https://base.easscan.org/attestation/view/0xd4485037c5c7601a9a5bc5bc0ed2536a8434ef0b7f77a6af0c9078d5d83b423e
   ```

2. **检查以下内容**：

   | 检查项 | 预期结果 |
   |--------|----------|
   | 页面能正常打开 | ✅ 不是 404 |
   | 显示 "Attestation" 标题 | ✅ |
   | Chain 显示 "Base" | ✅ |
   | Schema UID 存在 | ✅ 不是空的 |
   | Attester 地址存在 | ✅ 0x开头的以太坊地址 |
   | Decoded Data 里有 merkle_root | ✅ sha256:开头的哈希 |
   | Decoded Data 里有 batch_count | ✅ 数字 5 |
   | Transaction Hash 可以点击 | ✅ 链接到 Basescan |

3. **点击 Transaction Hash**，确认：
   - 交易状态是 "Success" ✅
   - 网络是 "Base" ✅

### 这证明了什么
> Agent 的工作记录经过 Merkle 树打包后，哈希被永久写入 Base L2 区块链。任何人都可以验证这些数据没有被篡改。

---

## 3. 测试 B：Dashboard UI 验证

### 步骤

1. **打开浏览器**，访问：
   ```
   https://api.weba0.com/dashboard
   ```

2. **检查 Overview 页面**：

   | 检查项 | 预期结果 |
   |--------|----------|
   | 页面正常加载 | ✅ 不是空白或错误 |
   | Total Anchored 显示数字 | ✅ 应该是 29+ |
   | Total Webhooks Sent | ✅ 应该是 29+ |
   | Total Errors ≤ 4 | ✅ |
   | Server Start 有日期 | ✅ |

3. **点击不同的 Tab**（如果有 Activity / Evidence Chain / Audit），确认每个都能正常展示数据。

### 这证明了什么
> Dashboard 是 ATLAST Protocol 的数据可视化界面，用户可以看到自己 agent 的所有活动记录和链上锚定状态。

---

## 4. 测试 C：9 个 Agent 真实用户场景

### 总体说明

这 9 个 agent 模拟了 **9 种不同的用户接入方式**。每种方式代表一个真实开发者会用的方法来接入 ATLAST Protocol。

SSH 到 Mac Mini 后，以下所有命令都在 Mac Mini 上执行：

```bash
ssh mad-imac1@100.79.169.126
```

---

### Agent 01 — LangChain ReAct（最主流的 AI 框架）

**用户场景**：一个开发者已经在用 LangChain 开发 AI agent，想接入 ATLAST 来记录工作证据。只需要加 1 行 callback。

**检查步骤**：
```bash
# 1. 看 agent 代码结构
cat ~/agents/01-langchain-react/agent.py | head -30

# 2. 看 ATLAST 接入方式（应该只有1行 callback 配置）
grep -n "ATLAST\|atlast\|callback" ~/agents/01-langchain-react/agent.py

# 3. 看运行结果（最后10个task）
tail -20 ~/agents/01-langchain-react/run2.log 2>/dev/null || tail -20 ~/agents/01-langchain-react/run.log

# 4. 检查 ECP 记录是否生成
grep "langchain\|deepseek" ~/.ecp/records/2026-04-01.jsonl | head -3 | python3 -m json.tool
```

**预期**：
- agent.py 里有 `ATLASTCallbackHandler` 
- 运行日志显示 105 个 task 完成
- ECP records 有 `step.type: "llm_call"` 和 `chain.hash`

---

### Agent 02 — LangGraph StateGraph（多步骤工作流）

**用户场景**：开发者用 LangGraph 构建复杂的多步骤工作流（research → draft → review → final）。每一步都被 ATLAST 记录。

**检查步骤**：
```bash
# 1. 看 agent 结构
cat ~/agents/02-langgraph-workflow/agent.py | head -30

# 2. 看工作流步骤定义
grep -n "StateGraph\|add_node\|research\|draft\|review" ~/agents/02-langgraph-workflow/agent.py

# 3. 看运行结果
tail -20 ~/agents/02-langgraph-workflow/run2.log 2>/dev/null || tail -20 ~/agents/02-langgraph-workflow/run.log

# 4. 看一个完整task的多步骤记录
grep "02-langgraph\|unknown" ~/.ecp/records/2026-04-01.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    if r.get('step',{}).get('delegation_depth',0) > 0:
        print(f'{r[\"id\"][:20]} depth={r[\"step\"][\"delegation_depth\"]} model={r[\"step\"].get(\"model\",\"?\")[:20]}')
" | head -10
```

**预期**：
- StateGraph 有多个节点（research, draft, review）
- 记录里有 `delegation_depth > 0`（表示子步骤）

---

### Agent 03 — CrewAI Team（多 Agent 协作）

**用户场景**：开发者用 CrewAI 构建多个 AI agent 组成的团队（researcher + writer + reviewer），ATLAST 记录每个 agent 的工作。

**检查步骤**：
```bash
# 1. 看 CrewAI 团队定义
cat ~/agents/03-crewai-team/agent.py | head -50

# 2. 看团队成员
grep -n "Agent\|Task\|Crew\|researcher\|writer\|reviewer" ~/agents/03-crewai-team/agent.py | head -15

# 3. 看运行结果
tail -20 ~/agents/03-crewai-team/run_batched.log 2>/dev/null

# 4. 检查 ECP 记录
grep "gpt-4o-mini" ~/.ecp/records/2026-04-01.jsonl | head -3 | python3 -m json.tool
```

**预期**：
- CrewAI 定义了 3 个角色（researcher, writer, reviewer）
- 使用了 `gpt-4o-mini` 模型
- 日志显示 batched 执行（10 tasks 一批）

---

### Agent 04 — AutoGen GroupChat（多 Agent 辩论）

**用户场景**：开发者用 Microsoft AutoGen 构建 group chat，多个 agent 轮流发言讨论同一个话题。

**检查步骤**：
```bash
# 1. 看 AutoGen 配置
cat ~/agents/04-autogen-groupchat/agent.py | head -40

# 2. 看 GroupChat 成员
grep -n "GroupChat\|agent\|ATLASTAutoGen" ~/agents/04-autogen-groupchat/agent.py

# 3. 看运行结果
tail -20 ~/agents/04-autogen-groupchat/run.log 2>/dev/null

# 4. 看一次辩论的记录
grep "autogen\|deepseek" ~/.ecp/records/2026-03-31.jsonl | head -5 | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(f'{r[\"id\"][:20]} type={r[\"step\"][\"type\"]} latency={r[\"step\"].get(\"latency_ms\",0)}ms')
" 
```

**预期**：
- GroupChat 有 RoundRobin 策略
- 每个 task ~3 分钟（多轮对话）
- ECP 记录类型是 `llm_call`

---

### Agent 05 — Raw wrap()（零代码接入）

**用户场景**：最简单的接入方式——开发者只需要把 `OpenAI()` 改成 `wrap(OpenAI())`，一行代码完成接入。

**检查步骤**：
```bash
# 1. 看代码——关键是 wrap() 一行
cat ~/agents/05-raw-wrap/agent.py | head -20

# 2. 看 ATLAST 接入点（应该只有1行！）
grep -n "wrap" ~/agents/05-raw-wrap/agent.py

# 3. 看运行结果
tail -10 ~/agents/05-raw-wrap/run.log 2>/dev/null

# 4. 验证 ECP 记录完整性
source ~/agents-venv/bin/activate && python3 -c "
from atlast_ecp.verify import verify_record
from atlast_ecp.storage import load_records
recs = load_records(limit=5)
for r in recs[:3]:
    result = verify_record(r)
    print(f'{r[\"id\"][:20]}: valid={result[\"valid\"]} chain_hash={result[\"chain_hash_ok\"]}')
"
```

**预期**：
- 代码里只有一行 `client = wrap(OpenAI(...))`
- 所有记录 `valid=True`, `chain_hash_ok=True`
- **这就是 Layer 0 零代码接入的核心卖点**

---

### Agent 06 — @trace Decorator（5 行代码接入）

**用户场景**：开发者想要更精细的控制，用装饰器标记要追踪的函数。

**检查步骤**：
```bash
# 1. 看装饰器用法
cat ~/agents/06-track-decorator/agent.py | head -30

# 2. 看 @trace 或 @track 装饰器
grep -n "trace\|track\|record" ~/agents/06-track-decorator/agent.py

# 3. 看运行结果
tail -10 ~/agents/06-track-decorator/run.log 2>/dev/null
```

**预期**：
- 代码里有 `@trace` 或 `record()` 调用
- 记录比 wrap() 更详细（有自定义 metadata）

---

### Agent 07 — OpenClaw Plugin（平台集成）

**用户场景**：OpenClaw 用户通过插件方式自动接入 ATLAST，完全不需要改 agent 代码。

**检查步骤**：
```bash
# 1. 看插件配置
cat ~/agents/07-openclaw-plugin/agent.py | head -30

# 2. 看多模型切换
grep -n "model\|gpt\|deepseek" ~/agents/07-openclaw-plugin/agent.py

# 3. 看运行结果
tail -10 ~/agents/07-openclaw-plugin/run.log 2>/dev/null
```

**预期**：
- 使用多个模型（gpt-4o-mini + deepseek）
- 自动切换模型

---

### Agent 08 — Node.js（TypeScript SDK）

**用户场景**：JavaScript/TypeScript 开发者接入 ATLAST。

**检查步骤**：
```bash
# 1. 看 TS/JS 代码
cat ~/agents/08-nodejs-agent/agent.js 2>/dev/null || cat ~/agents/08-nodejs-agent/agent.ts 2>/dev/null | head -30

# 2. 看 npm 包引用
grep -n "atlast\|ecp\|require\|import" ~/agents/08-nodejs-agent/agent.* | head -10

# 3. 看运行结果
tail -10 ~/agents/08-nodejs-agent/run.log 2>/dev/null
```

**预期**：
- 使用 `atlast-ecp-ts` npm 包
- 和 Python SDK 生成相同格式的 ECP 记录

---

### Agent 09 — Claude Code（Anthropic tool_use）

**用户场景**：开发者用 Anthropic Claude 的 tool_use 功能构建 coding agent，ATLAST 通过 wrap() 透明记录。

**检查步骤**：
```bash
# 1. 看 Claude agent 代码
cat ~/agents/09-claude-code/agent.py | head -30

# 2. 看 ATLAST 接入（wrap 了 OpenAI client，通过 OpenRouter 调 Claude）
grep -n "wrap\|claude\|anthropic\|tool" ~/agents/09-claude-code/agent.py | head -10

# 3. 看结果
tail -5 ~/agents/09-claude-code/results.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(f'Task {r.get(\"task_id\",\"?\")}: {r.get(\"success\",\"?\")} steps={r.get(\"steps\",0)} time={r.get(\"duration_s\",0):.0f}s')
"

# 4. 验证 Claude 的 ECP 记录
grep "claude" ~/.ecp/records/2026-04-01.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(f'{r[\"id\"][:20]} model={r[\"step\"].get(\"model\",\"?\")} latency={r[\"step\"].get(\"latency_ms\",0)}ms')
" | head -5
```

**预期**：
- 使用 `anthropic/claude-3.5-haiku` 模型
- 106/105 tasks 成功
- wrap() 透明记录了所有 Claude API 调用

---

## 5. 测试 D：API 数据验证

在你自己的电脑上打开终端，运行以下命令：

### D1. 服务器健康检查
```bash
curl -s https://api.weba0.com/v1/health | python3 -m json.tool
curl -s https://api.weba0.com/v1/stats | python3 -m json.tool
```
**预期**：health 返回 ok，stats 显示 total_anchored ≥ 29

### D2. 验证链上 attestation
```bash
curl -s "https://api.weba0.com/v1/verify/0xbf5aa9429b44743f9cd0175697103ea42538f25253d029143bc77b5b0de7c609" | python3 -m json.tool
```
**预期**：`verified: "explorer_link"`，有 `explorer_url`

### D3. 查看 Super-batch 详情
```bash
curl -s "https://api.weba0.com/v1/super-batches/sb_d479ce019a214d9a" | python3 -m json.tool
curl -s "https://api.weba0.com/v1/super-batches/sb_643ee533254b48c9" | python3 -m json.tool
```
**预期**：每个 super-batch 有 5 个 batch_ids，status = "anchored"

### D4. PyPI 安装验证
```bash
pip install atlast-ecp==0.11.0
python3 -c "import atlast_ecp; print(atlast_ecp.__version__)"
```
**预期**：输出 `0.11.0`

---

## 6. 测试 E：Alex 侧 LLAChat 数据确认

**这个需要问 Alex 确认**（或者登录 LLAChat 看）：

1. Alex 的 DB 里 `work_certificates` 表有没有来自 `did:ecp:c71dd204624d9d9ec7583a52845b378f` 的数据？
2. Webhook 收到了多少条？（预期 29 条）
3. `@atlas` DID (`did:ecp:03a3a65b9e5f9e95e4f872264e7fd716`) 的 trust_score 是否更新了？

我可以代你发消息给 Alex 确认这些。

---

## 7. 测试结果记录表

复制以下表格，逐项打 ✅ 或 ❌：

```
测试 A: EAS Explorer
[ ] A1. Super-batch 1 页面打开正常
[ ] A2. Super-batch 2 页面打开正常
[ ] A3. Decoded Data 有 merkle_root
[ ] A4. Transaction 状态 Success
[ ] A5. 网络是 Base

测试 B: Dashboard
[ ] B1. Dashboard 页面加载正常
[ ] B2. Total Anchored ≥ 29
[ ] B3. Webhooks Sent ≥ 29

测试 C: 9 个 Agent
[ ] C1. Agent 01 LangChain — callback 一行接入，105 tasks 完成
[ ] C2. Agent 02 LangGraph — 多步骤工作流，有 delegation 记录
[ ] C3. Agent 03 CrewAI — 3 角色团队，batched 执行
[ ] C4. Agent 04 AutoGen — GroupChat 辩论，多轮对话
[ ] C5. Agent 05 wrap() — 一行代码接入，records 全部 valid
[ ] C6. Agent 06 @trace — 装饰器接入
[ ] C7. Agent 07 OpenClaw — 多模型切换
[ ] C8. Agent 08 Node.js — TS SDK 接入
[ ] C9. Agent 09 Claude — Anthropic tool_use 透明记录

测试 D: API
[ ] D1. Server health OK
[ ] D2. Attestation verified
[ ] D3. Super-batch 数据正确
[ ] D4. PyPI 0.11.0 安装成功

测试 E: Alex 侧
[ ] E1. work_certificates 有数据
[ ] E2. Webhook 收到 29 条
[ ] E3. trust_score 已更新
```

---

## 常见问题

**Q: SSH 连不上 Mac Mini？**  
A: 确保在同一个 Tailscale 网络下。如果还是不行，告诉 Atlas。

**Q: curl 命令报错？**  
A: 确保用的是 `https://` 不是 `http://`。

**Q: Agent 日志文件找不到？**  
A: 有些 agent 的日志在 `run2.log`（重跑版），有些在 `run.log`（原始版）。

**Q: Dashboard 打不开？**  
A: Dashboard 可能需要直接访问 `https://api.weba0.com/dashboard/index.html`。
