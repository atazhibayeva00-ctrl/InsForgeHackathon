#!/usr/bin/env bash
# Bootstrap the backend Python environment (Co-Gym style, Python 3.11).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
VENV="$BACKEND/.venv"

pick_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    echo python3.11
  elif command -v python3 >/dev/null 2>&1; then
    echo python3
  else
    echo "python3.11 or python3 is required." >&2
    exit 1
  fi
}

PYTHON="$(pick_python)"
echo "Using $("$PYTHON" --version)"

NEED_VENV=1
if [[ -d "$VENV" ]]; then
  VENV_PY="$("$VENV/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")"
  WANT_PY="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "$VENV_PY" == "$WANT_PY" ]]; then
    NEED_VENV=0
  else
    echo "Recreating virtualenv (found Python $VENV_PY, want $WANT_PY)"
    rm -rf "$VENV"
  fi
fi

if [[ "$NEED_VENV" -eq 1 ]]; then
  echo "Creating virtualenv at $VENV"
  "$PYTHON" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip
# Use public PyPI when a corporate index is unavailable or times out.
pip install --index-url https://pypi.org/simple -r "$BACKEND/requirements.txt"

if [[ ! -f "$BACKEND/.env" && -f "$ROOT/.env.example" ]]; then
  cp "$ROOT/.env.example" "$BACKEND/.env"
  echo "Copied .env.example -> backend/.env (add your ANTHROPIC_API_KEY to enable the LLM agent)"
fi

echo ""
echo "Backend environment ready."
echo "  source backend/.venv/bin/activate"
echo "  cd backend && uvicorn main:app --reload --port 8000"
