# ECP × China AI Regulations Mapping

## Applicable Regulations

1. **《生成式人工智能服务管理暂行办法》** (Interim Measures for GenAI Services, 2023)
2. **《个人信息保护法》(PIPL)** (Personal Information Protection Law, 2021)
3. **《算法推荐管理规定》** (Algorithm Recommendation Regulations, 2022)

## Key Requirements → ECP

| Requirement | Source | ECP Feature | Status |
|------------|--------|------------|--------|
| Retain training/generation records | GenAI Art. 17 | `record()` + JSONL storage | ✅ Full |
| Monitoring and evaluation | GenAI Art. 14 | `meta.flags[]` + `atlast insights` | ✅ Full |
| Transparency of services | GenAI Art. 4 | `action`, `meta.model`, agent DID | ✅ Full |
| Data minimization | PIPL Art. 7 | Hash-only design, content stays local | ✅ Full |
| Algorithmic accountability | Algorithm Reg. Art. 6 | Hash chain + multi-agent verification | ✅ Full |
| User complaint handling | GenAI Art. 15 | Audit trail for investigation | ✅ Full |
| Content labeling | GenAI Art. 12 | Agent DID identifies AI-generated content | 🟡 Partial |

## Key Strength for China Market

ECP's **hash-only design** is uniquely suited for China's data sovereignty requirements. Raw content never leaves the device — only SHA-256 hashes are transmitted. This aligns with both PIPL's data minimization principle and cross-border data transfer restrictions.

## Gaps

- Content labeling (Art. 12): ECP identifies agent actions, but visible watermarking is application-level
- Safety assessment reporting: Requires integration with regulatory submission systems
