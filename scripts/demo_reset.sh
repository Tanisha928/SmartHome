#!/usr/bin/env bash
# Fresh demo stack for the Component 2 (IoT Device Manager) demo.
# WIPES local Postgres/Mongo/LocalStack data, then: start services (demo timings), migrate,
# seed, and create a demo owner with no house yet (link them by registering a house in A4).
#   scripts/demo_reset.sh        # asks before wiping
#   scripts/demo_reset.sh -y     # no prompt
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.demo.yml)
API=http://localhost:8000
DEMO_OWNER_EMAIL=owner.demo@example.com
DEMO_OWNER_PASSWORD=demo-owner-1

if [[ "${1:-}" != "-y" ]]; then
  read -r -p "This deletes all local demo data (Docker volumes). Continue? [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || exit 1
fi

echo "==> Stopping stack and removing volumes"
"${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true

echo "==> Starting Postgres, Mongo, LocalStack, API, model worker, sweepers"
"${COMPOSE[@]}" up -d --build postgres mongo localstack backend model-worker sweepers

echo "==> Waiting for the API"
for _ in $(seq 1 90); do curl -sf "$API/healthz" >/dev/null && break; sleep 2; done
curl -sf "$API/healthz" >/dev/null || { echo "API did not come up; see: docker compose logs backend"; exit 1; }

echo "==> Waiting for LocalStack bucket and queues"
for _ in $(seq 1 60); do
  "${COMPOSE[@]}" exec -T localstack awslocal sqs get-queue-url --queue-name inference-events >/dev/null 2>&1 && break
  sleep 2
done

echo "==> Migrating and seeding"
"${COMPOSE[@]}" exec -T backend alembic upgrade head
"${COMPOSE[@]}" exec -T -e PYTHONPATH=/app backend python /scripts/seed_dev_data.py >/dev/null

echo "==> Creating demo owner"
curl -sf -X POST "$API/api/auth/signup" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$DEMO_OWNER_EMAIL\",\"password\":\"$DEMO_OWNER_PASSWORD\",\"full_name\":\"Dana Demo\",\"phone\":\"+15550100100\"}" >/dev/null

"${COMPOSE[@]}" restart model-worker sweepers >/dev/null
rm -rf edge/.demo

cat <<SUMMARY

Demo stack ready (devices go offline 1 min after their last heartbeat).
  Admin:  admin@smarthome.local / admin-password-1
  Owner:  $DEMO_OWNER_EMAIL / $DEMO_OWNER_PASSWORD   (register a house with this owner email in A4)
  UI:     cd frontend && VITE_API_BASE=$API npm run dev   →  http://localhost:5173
Next: register house/room/device in A4, then  scripts/demo_agent.sh <device_id> <api_key> <house_id>
SUMMARY
