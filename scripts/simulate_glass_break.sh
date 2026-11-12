#!/usr/bin/env bash
# "Capture" glass-break sounds on the demo device: drops clips into the running agent's inbox.
#   scripts/simulate_glass_break.sh        # one clip
#   scripts/simulate_glass_break.sh 3      # three clips
#   SOUND=fall scripts/simulate_glass_break.sh   # glass_break | smoke_fire_alarm | fall | distress
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COUNT="${1:-1}"
SOUND="${SOUND:-glass_break}"
SAMPLE="$ROOT/edge/samples/$SOUND.wav"
INBOX="$ROOT/edge/.demo/clips/inbox"

[[ -f "$SAMPLE" ]] || { echo "no sample $SAMPLE" >&2; exit 1; }
[[ -f "$ROOT/edge/.demo/edge.env" ]] || { echo "start the agent first: scripts/demo_agent.sh <device_id> <api_key> <house_id>" >&2; exit 1; }
mkdir -p "$INBOX"
for i in $(seq 1 "$COUNT"); do
  cp "$SAMPLE" "$INBOX/$SOUND-$(date +%s)-$i.wav"
done
echo "captured $COUNT $SOUND clip(s) on the demo device"
