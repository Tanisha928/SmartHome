#!/bin/bash
# Build a release tarball (backend + edge + built frontend + infra configs), upload it, and
# roll every ASG onto it. Usage: scripts/deploy.sh <env> <artifact-bucket> [release-id]
set -euo pipefail

ENV="${1:?env (e.g. prod)}"
BUCKET="${2:?artifact bucket}"
RELEASE="${3:-$(git rev-parse --short HEAD)}"
REGION="${AWS_REGION:-us-west-2}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> building frontend"
(cd "$ROOT/frontend" && npm ci && npm run build)

echo "==> staging release $RELEASE"
mkdir -p "$STAGE/infra"
rsync -a --exclude '.venv' --exclude '__pycache__' --exclude 'tests' "$ROOT/backend" "$STAGE/"
cp -r "$ROOT/frontend/dist" "$STAGE/frontend-dist"
cp -r "$ROOT/infra/nginx" "$ROOT/infra/systemd" "$STAGE/infra/"
tar -czf "$STAGE/$RELEASE.tar.gz" -C "$STAGE" backend frontend-dist infra

echo "==> uploading"
aws s3 cp "$STAGE/$RELEASE.tar.gz" "s3://$BUCKET/releases/$RELEASE.tar.gz" --region "$REGION"
aws s3 cp "$STAGE/$RELEASE.tar.gz" "s3://$BUCKET/releases/current.tar.gz" --region "$REGION"

echo "==> rolling ASGs (sweeper first so migrations run before new API code)"
for tier in sweeper api worker; do
  asg="smarthome-$ENV-$tier"
  aws autoscaling start-instance-refresh --region "$REGION" \
    --auto-scaling-group-name "$asg" \
    --preferences '{"MinHealthyPercentage": 50, "InstanceWarmup": 120}' >/dev/null
  echo "    refresh started: $asg"
  if [ "$tier" = "sweeper" ]; then
    echo "    waiting for sweeper refresh (migrations)…"
    until [ "$(aws autoscaling describe-instance-refreshes --region "$REGION" \
      --auto-scaling-group-name "$asg" --max-records 1 \
      --query 'InstanceRefreshes[0].Status' --output text)" = "Successful" ]; do sleep 15; done
  fi
done
echo "==> deployed $RELEASE to $ENV"
