#!/usr/bin/env bash
set -euo pipefail

echo "[localstack-init] Creating S3 bucket smarthome-clips..."
awslocal s3 mb s3://smarthome-clips || true
awslocal s3api put-bucket-encryption --bucket smarthome-clips --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
awslocal s3api put-public-access-block --bucket smarthome-clips --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "[localstack-init] Creating SQS queues..."
awslocal sqs create-queue --queue-name inference-events-dlq || true
DLQ_ARN=$(awslocal sqs get-queue-attributes --queue-url http://localhost:4566/000000000000/inference-events-dlq --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)
awslocal sqs create-queue --queue-name inference-events --attributes "{\"VisibilityTimeout\":\"120\",\"ReceiveMessageWaitTimeSeconds\":\"20\",\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"${DLQ_ARN}\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}" || true
echo "[localstack-init] Done."
