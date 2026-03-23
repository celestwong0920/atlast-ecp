import{_ as s,o as n,c as e,ag as t}from"./chunks/framework.BZohXCq9.js";const u=JSON.parse('{"title":"Architecture","description":"","frontmatter":{},"headers":[],"relativePath":"guide/architecture.md","filePath":"guide/architecture.md"}'),l={name:"guide/architecture.md"};function r(i,a,p,o,c,d){return n(),e("div",null,[...a[0]||(a[0]=[t(`<h1 id="architecture" tabindex="-1">Architecture <a class="header-anchor" href="#architecture" aria-label="Permalink to &quot;Architecture&quot;">​</a></h1><h2 id="system-overview" tabindex="-1">System Overview <a class="header-anchor" href="#system-overview" aria-label="Permalink to &quot;System Overview&quot;">​</a></h2><div class="language- vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>┌─────────────────────────────────────────────────────────┐</span></span>
<span class="line"><span>│                    User&#39;s Device                         │</span></span>
<span class="line"><span>│                                                         │</span></span>
<span class="line"><span>│  ┌─────────┐    ┌──────────┐    ┌────────────────────┐ │</span></span>
<span class="line"><span>│  │  Agent   │───&gt;│ ATLAST   │───&gt;│  ~/.ecp/           │ │</span></span>
<span class="line"><span>│  │ (GPT-4,  │    │   SDK    │    │  ├── records/      │ │</span></span>
<span class="line"><span>│  │  Claude) │    │  wrap()  │    │  ├── vault/        │ │</span></span>
<span class="line"><span>│  └─────────┘    └──────────┘    │  ├── identity/     │ │</span></span>
<span class="line"><span>│                       │          │  └── batch_state   │ │</span></span>
<span class="line"><span>│                       │          └────────────────────┘ │</span></span>
<span class="line"><span>│                       │ Merkle Root + Signature          │</span></span>
<span class="line"><span>└───────────────────────│─────────────────────────────────┘</span></span>
<span class="line"><span>                        ▼</span></span>
<span class="line"><span>              ┌──────────────────┐</span></span>
<span class="line"><span>              │  ATLAST Server   │</span></span>
<span class="line"><span>              │  api.weba0.com   │</span></span>
<span class="line"><span>              │                  │</span></span>
<span class="line"><span>              │  ┌────────────┐  │</span></span>
<span class="line"><span>              │  │ PostgreSQL │  │</span></span>
<span class="line"><span>              │  └────────────┘  │</span></span>
<span class="line"><span>              └────────│─────────┘</span></span>
<span class="line"><span>                       ▼</span></span>
<span class="line"><span>              ┌──────────────────┐</span></span>
<span class="line"><span>              │   Base (EAS)     │</span></span>
<span class="line"><span>              │   On-chain       │</span></span>
<span class="line"><span>              │   Anchoring      │</span></span>
<span class="line"><span>              └──────────────────┘</span></span></code></pre></div><h2 id="data-flow" tabindex="-1">Data Flow <a class="header-anchor" href="#data-flow" aria-label="Permalink to &quot;Data Flow&quot;">​</a></h2><ol><li><strong>Agent calls LLM</strong> → SDK intercepts (wrap/proxy)</li><li><strong>SDK creates ECP record</strong> → hashes input/output, links to chain, signs</li><li><strong>Record saved locally</strong> → <code>~/.ecp/records/</code> (JSONL) + <code>~/.ecp/vault/</code> (content)</li><li><strong>Hourly batch</strong> → Merkle tree computed, root signed, uploaded to server</li><li><strong>Server anchors</strong> → Merkle root written to EAS on Base blockchain</li><li><strong>Webhook</strong> → Notifies integrated platforms (e.g., LLaChat)</li></ol><h2 id="what-stays-local-vs-what-s-transmitted" tabindex="-1">What Stays Local vs. What&#39;s Transmitted <a class="header-anchor" href="#what-stays-local-vs-what-s-transmitted" aria-label="Permalink to &quot;What Stays Local vs. What&#39;s Transmitted&quot;">​</a></h2><table tabindex="0"><thead><tr><th>Data</th><th>Location</th><th>Transmitted?</th></tr></thead><tbody><tr><td>Original input/output</td><td><code>~/.ecp/vault/</code></td><td>❌ Never</td></tr><tr><td>Record hashes</td><td><code>~/.ecp/records/</code></td><td>✅ Hash only</td></tr><tr><td>Ed25519 private key</td><td><code>~/.ecp/identity/</code></td><td>❌ Never</td></tr><tr><td>Merkle root</td><td>Server + chain</td><td>✅ Hash only</td></tr><tr><td>Signature</td><td>Server + chain</td><td>✅</td></tr></tbody></table><h2 id="fail-open-design" tabindex="-1">Fail-Open Design <a class="header-anchor" href="#fail-open-design" aria-label="Permalink to &quot;Fail-Open Design&quot;">​</a></h2><p>Every component follows fail-open principle:</p><ul><li>SDK recording fails → agent continues normally</li><li>Batch upload fails → queued for retry (exponential backoff)</li><li>Server down → records accumulate locally</li><li>EAS anchoring fails → retried next cron cycle</li></ul><p><strong>Recording failures never affect agent operation.</strong></p>`,11)])])}const g=s(l,[["render",r]]);export{u as __pageData,g as default};
