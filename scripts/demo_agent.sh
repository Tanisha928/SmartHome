#!/usr/bin/env bash
# Run the edge agent as the demo device (foreground, logs visible).
#   scripts/demo_agent.sh <device_id> <api_key> <house_id>   # first time: saves edge/.demo/edge.env
#   scripts/demo_agent.sh                                    # later: reuse saved config
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="$ROOT/edge/.demo"
ENV_FILE="$DEMO/edge.env"
mkdir -p "$DEMO"

if [[ $# -eq 3 ]]; then
  cat > "$ENV_FILE" <<CFG
API_BASE=http://localhost:8000
DEVICE_ID=$1
API_KEY=$2
HOUSE_ID=$3
OUTBOX_DB=$DEMO/outbox.sqlite
CLIP_DIR=$DEMO/clips
HEARTBEAT_SEC=5
SEND_CYCLE_SEC=2
MAX_BACKOFF_SEC=5
CFG
  chmod 600 "$ENV_FILE"
elif [[ ! -f "$ENV_FILE" ]]; then
  echo "usage: $0 <device_id> <api_key> <house_id>   (copy them from the A4 key dialog)" >&2
  exit 1
fi

exec "$ROOT/edge/.venv/bin/edge-agent" run --env-file "$ENV_FILE"
