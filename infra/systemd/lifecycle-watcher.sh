#!/bin/bash
# Poll IMDSv2 for the ASG lifecycle state. On "Terminated" (instance is in Terminating:Wait),
# stop the worker gracefully so it finishes its in-flight message, then complete the hook.
set -euo pipefail

imds() {
  local token
  token=$(curl -sf -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
  curl -sf -H "X-aws-ec2-metadata-token: $token" "http://169.254.169.254/latest/meta-data/$1"
}

INSTANCE_ID=$(imds instance-id)
while true; do
  state=$(imds autoscaling/target-lifecycle-state || echo "InService")
  if [ "$state" = "Terminated" ]; then
    echo "scale-in: draining model worker on $INSTANCE_ID"
    systemctl stop smarthome-worker || true
    aws autoscaling complete-lifecycle-action \
      --region "$AWS_REGION" \
      --auto-scaling-group-name "$ASG_NAME" \
      --lifecycle-hook-name drain \
      --instance-id "$INSTANCE_ID" \
      --lifecycle-action-result CONTINUE
    exit 0
  fi
  sleep 5
done
