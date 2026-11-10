# Review Launch on your own machine (Windows, macOS or Linux)

Prerequisites (one time): Python 3.11+, Git, Node 18+, and an Anthropic API key.

```powershell
# 1. Claude CLI (the agent runtime used by the Claude Agent SDK)
npm install -g @anthropic-ai/claude-code

# 2. Launch
git clone https://github.com/balakrishnen/Launch
cd Launch
python -m venv .venv
.\.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e .

# 3. Key and run
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # macOS/Linux: export ANTHROPIC_API_KEY=sk-ant-...
launch build examples/sabi               # diagrams, docs, SysML (optional, ~30 s)
launch ui examples/sabi                  # opens http://127.0.0.1:8765
```

Multi-user with Postgres instead: `docker compose up` (reads ANTHROPIC_API_KEY from the environment), then open
http://localhost:8765, sign in with any email, create a project or
`launch import examples/sabi --database postgresql://launch:launch@localhost:5432/launch`.

## What to review, in order

1. **Overview → Scorecard** — the quality dimensions and the requirements flagged by the INCOSE rules.
2. **Requirements → R-010** — an element page: fields, upstream/downstream, failure modes, impact if changed, provenance. Click *Show in graph*.
3. **DFMEA (AIAG-VDA form)** — filter by AP, double-click a severity cell, change it, *Save*. Watch the patch land and the scorecard card appear in the chat.
4. **Chat** — type: `Assess every remaining failure-mode candidate of F07 with causes derived from the architecture`. Review the patch card (diff per element, coverage delta), approve or reject.
5. **Role chips** — run *Risk and reliability engineer* on the e-bike project (`launch ui examples/ebike`) to see a whole stage staged for review.
6. **Integrations** — the OSLC endpoints and the DOORS Next consumer registration; `curl -u you@x.io:<token> http://127.0.0.1:8765/oslc/catalog -H "Accept: text/turtle"`.
7. **Diagrams / Design documentation / SysML text** — everything generated from the same model.
