#!/usr/bin/env bash
# Edge outbox status for the demo device (buffer depth during an outage).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/edge/.venv/bin/edge-agent" status --env-file "$ROOT/edge/.demo/edge.env"
