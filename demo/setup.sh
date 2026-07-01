#!/usr/bin/env bash
# demo/setup.sh — provisions a reproducible broken FastAPI target for the agent to fix.
#
# Usage:
#   bash demo/setup.sh
#
# Produces /tmp/demo-target/ containing a tiny FastAPI app whose /users endpoint
# raises TypeError. Feed demo/prompt.txt into the agent pointed at this dir.

set -euo pipefail

TARGET="/tmp/demo-target"

echo "[demo] Wiping ${TARGET} ..."
rm -rf "${TARGET}"
mkdir -p "${TARGET}"

echo "[demo] Writing broken FastAPI app to ${TARGET}/app.py ..."
cat > "${TARGET}/app.py" <<'PYEOF'
from fastapi import FastAPI

app = FastAPI()

USERS = [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Linus"}]

@app.get("/users")
def list_users():
    # BUG: concatenating a dict list with a string raises TypeError at request time.
    return USERS + "trailing"
PYEOF

echo "[demo] Writing requirements.txt ..."
cat > "${TARGET}/requirements.txt" <<'REQEOF'
fastapi>=0.110.0
uvicorn>=0.29.0
httpx>=0.27.0
pytest>=8.0.0
REQEOF

echo "[demo] Writing README.md ..."
cat > "${TARGET}/README.md" <<'MDEOF'
# demo-target

Intentionally broken FastAPI app used to demo the autonomous coding agent.

The `/users` endpoint returns HTTP 500 because it concatenates a list of dicts
with a string. The agent is expected to identify the bug, fix it, and add a
regression test.

## Run
```bash
pip install -r requirements.txt
uvicorn app:app --reload
curl http://localhost:8000/users
```
MDEOF

echo "[demo] Done. Broken target ready at ${TARGET}"
echo "[demo] Next: python main.py \"$(cat demo/prompt.txt)\""
