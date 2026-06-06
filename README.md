# CoVest: Collaborative Investment Copilot

CoVest is a human-in-the-loop personal investment assistant inspired by [Collaborative Gym](https://github.com/SALT-NLP/collaborative-gym) ([Shao et al., 2025 — arXiv:2412.15701](https://arxiv.org/abs/2412.15701)).

The agent analyzes your portfolio and **proposes** rebalances — you approve, reject, or add constraints before anything is treated as final. It is a collaborative copilot, **not** an autonomous trading bot.

## Why this design (the research connection)

Collaborative Gym shows that for high-stakes tasks where humans have latent preferences, domain expertise, and a need for control, **collaborative agents beat fully autonomous ones**. Personal investing is exactly that kind of task. This project instantiates the paper's collaboration model:

| Collaborative Gym concept | This app |
|---------------------------|----------|
| Shared workspace (`CoEnv`) | Backend session state: portfolio + plan + collaboration log |
| Task actions | Analyze portfolio, propose trades, revise |
| `SendTeammateMessage` | Agent message + questions for the user |
| `WaitTeammateContinue` | Agent stops after proposing; nothing executes |
| `RequestTeammateConfirm` / controlled autonomy | Approve / Reject / Revise buttons |
| `--enhance-user-control` | Plan is never "approved" until the human clicks Approve |

## Architecture

```
frontend/  React + Vite + TypeScript
   |  HTTP (/api) + WebSocket (/ws) proxied to backend
backend/   FastAPI + Redis-backed Co-Gym runtime
   ├── collaborative_gym/envs/investment.py        CoInvestmentEnv (`CoEnv`)
   ├── collaborative_gym/nodes/task_env.py         TaskEnvNode
   ├── demo_agent/investment_collaborative_agent/  AgentNode policy
   ├── collaborative_gym/server.py                 distributed API + WebSocket
   ├── portfolio.py                                CSV parsing + rule analysis
   └── agent.py                                    Claude planner + fallback
```

The default app uses the distributed Co-Gym stack: `Runner` starts an environment process and an agent process, Redis carries actions/observations, and the frontend receives live updates over WebSocket. The agent uses Claude (Anthropic) when `ANTHROPIC_API_KEY` is set, and automatically falls back to a rule-based planner otherwise.

## Quick start

### 1. Backend Environment

The backend uses a real **`CoInvestmentEnv`** task environment (`collaborative_gym/envs/investment.py`) registered as `"investment"`.

**Option A — one-command setup (recommended):**

```bash
./scripts/setup_backend_env.sh
source backend/.venv/bin/activate
```

**Option B — conda (matches upstream Co-Gym README):**

```bash
cd backend
conda env create -f environment.yml
conda activate cogym-investment
cp secrets.example.toml secrets.toml   # add ANTHROPIC_API_KEY for the LLM agent
```

### 2. Start Redis

```bash
brew services start redis
```

Or, if Docker Desktop is running:

```bash
docker compose up -d redis-stack
```

### 3. Start the Distributed Backend

```bash
cd backend
.venv/bin/python -m uvicorn collaborative_gym.server:app --host 127.0.0.1 --port 8010
```

The legacy synchronous backend still exists at `backend/main.py`, but the frontend is wired to the distributed server by default.

### 4. Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and click **Load complex demo** for the hackathon scenario. The agent will analyze and propose through Redis/WebSocket.

### Smoke Tests

```bash
# CoEnv only
source backend/.venv/bin/activate
python scripts/test_investment_env.py

# Headless distributed Runner/Redis flow
python scripts/run_distributed_session.py

# HTTP + WebSocket distributed server flow
COGYM_HTTP_BASE=http://127.0.0.1:8010 \
COGYM_WS_BASE=ws://127.0.0.1:8010 \
python scripts/test_distributed_server.py

# Browser E2E flow (backend must already be running)
cd frontend
PLAYWRIGHT_BROWSERS_PATH=0 npm exec playwright install chromium
npm run test:e2e
```

## CSV format

| Column | Required | Description |
|--------|----------|-------------|
| `ticker` | yes | Symbol (e.g. AAPL) |
| `shares` | yes | Number of shares |
| `current_price` | yes | Current price per share |
| `cost_basis` | no | Average cost basis (for unrealized gain flags) |
| `asset_class` | no | stock, etf, bond, cash |

## Hackathon demo script (2 minutes)

Team name suggestion: **Controlled Alpha**.

1. **Open with the research** — show the homepage and say: “CoVest is built on Stanford's Collaborative Gym research, applied to personal investing.”
2. **Launch the workspace** — use **Slide to launch** to move from the research story into the copilot.
3. **Load complex demo** — this uses `backend/data/demo_complex_portfolio.csv`, a portfolio with AI/tech concentration, overlapping ETFs, limited bonds, and taxable winners.
4. **Let the agent propose** — point out that the agent analyzes through Redis/WebSocket and waits for the human instead of executing.
5. **Add a latent preference** — type `Cannot sell META because it is employer stock.` and revise, showing that the agent adapts to human constraints.
6. **Approve a cycle** — approve the revised plan, showing mock-applied trades and the collaboration score.
7. **Repeat** — start the next review cycle to show the workflow is continuous, not one-shot.
8. **Close on the dashboard** — show collaboration score by cycle and expected portfolio value.

Close line: **“The key is not autonomous trading. It is controlled collaboration for high-stakes financial decisions.”**

## Demo reliability checklist

- Start Redis: `brew services start redis`
- Start backend fresh: `cd backend && .venv/bin/python -m uvicorn collaborative_gym.server:app --host 127.0.0.1 --port 8010`
- Start frontend fresh: `cd frontend && npm run dev`
- Run frontend build: `npm --prefix frontend run build`
- Run backend/WebSocket smoke test: `COGYM_HTTP_BASE=http://127.0.0.1:8010 COGYM_WS_BASE=ws://127.0.0.1:8010 python scripts/test_distributed_server.py`
- Install Playwright browser once if needed: `cd frontend && PLAYWRIGHT_BROWSERS_PATH=0 npm exec playwright install chromium`
- Run browser E2E: `cd frontend && npm run test:e2e`
- If Claude/API is unavailable, use the built-in rule-based fallback planner.

## API endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/init_env` | Start an `investment` Co-Gym session |
| WS | `/ws/{session_id}/{user_id}` | Stream observations/chat updates |
| POST | `/api/post_action/{session_id}/{user_id}` | Publish human Co-Gym actions (`APPROVE_PLAN()`, `REJECT_PLAN()`, etc.) |
| GET | `/api/result/{session_id}` | Fetch event log and task performance metrics |

## Disclaimer

Educational hackathon demo only — **not financial advice**. No real trades are executed.

## License

MIT
