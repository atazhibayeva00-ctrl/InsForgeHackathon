# Collaborative Investment Copilot

A human-in-the-loop personal investment assistant inspired by [Collaborative Gym](https://github.com/SALT-NLP/collaborative-gym) ([Shao et al., 2025 — arXiv:2412.15701](https://arxiv.org/abs/2412.15701)).

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

Open http://localhost:5173 and click **Load sample portfolio**. The agent will analyze and propose through Redis/WebSocket.

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
```

## CSV format

| Column | Required | Description |
|--------|----------|-------------|
| `ticker` | yes | Symbol (e.g. AAPL) |
| `shares` | yes | Number of shares |
| `current_price` | yes | Current price per share |
| `cost_basis` | no | Average cost basis (for unrealized gain flags) |
| `asset_class` | no | stock, etf, bond, cash |

## Demo script (90 seconds)

1. **Load sample portfolio** — concentrated in NVDA + AAPL.
2. The distributed agent analyzes the portfolio and proposes a plan.
3. In the feedback box, type: `Don't sell NVDA — long-term hold` → **Revise with feedback**.
4. The agent revises through the Redis/WebSocket flow.
5. Click **Approve plan** — see the approved target allocation, collaboration log, and collaboration score.

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
