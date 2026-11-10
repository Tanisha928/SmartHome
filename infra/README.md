# AWS deployment (Phase 11)

Owners: Sakshat (network, compute, IAM, alarms) · Tanisha (RDS, MongoDB, S3, SQS, SNS data tier).

```
Internet ─ ALB (public subnets, HTTPS/ACM, 80→443)
             ├─ /api/ingest/*  → tg-ingest ┐
             ├─ /api/*, /ws/*  → tg-api    ├─ API ASG (2–6, t3.medium, private app subnets, 2 AZs)
             └─ /              → tg-web    ┘     nginx :80 → uvicorn :8000
           SQS inference-events ──► Worker ASG (1–8, scales on queue depth > 100 for 2 min)
           Sweeper ASG (exactly 1): connectivity / stuck-event / escalation / retention + migrations
           RDS PostgreSQL + MongoDB EC2 in private data subnets (no internet route)
```

## Files

| File | What |
|---|---|
| `terraform/providers.tf` | provider, AZs, data-tier names/ARNs used by compute |
| `terraform/vpc.tf` | VPC 10.0.0.0/16, public/app/data subnets ×2 AZ, NAT, S3 gateway endpoint, DB subnet group |
| `terraform/security_groups.tf` | alb → api → postgres/mongo; workers/sweeper egress only; no SSH |
| `terraform/alb.tf` | ALB, TLS 1.2+ policy, 3 target groups (least-outstanding-requests, health `/healthz` 15 s, no stickiness) |
| `terraform/asg.tf` | launch templates (AL2023, IMDSv2, encrypted gp3), ASGs, CPU 60% + 1000 req/target tracking, SQS step scaling, worker drain lifecycle hook |
| `terraform/iam.tf` | per-tier instance roles (least privilege), SSM Session Manager |
| `terraform/cloudwatch.tf` | alarms (API p95 > 500 ms, queue > 500, DLQ > 0, inference p95 > 3 s, delivery failures, status checks, healthy hosts < 2), 70 % budget, dashboard |
| `terraform/user_data/bootstrap.sh.tftpl` | boot: install release, build `/etc/smarthome.env` from SSM, start the tier's systemd units |
| `systemd/*` | `smarthome-api`, `smarthome-worker` (graceful SIGTERM), `smarthome-sweepers`, lifecycle watcher |
| `nginx/default.conf` | proxy + WebSocket upgrade + 26 MB uploads + SPA |
| `../scripts/deploy.sh` | build frontend, tar release, upload, instance-refresh sweeper → api → worker |

## First deploy

1. Create an artifact bucket and an ACM certificate; copy `terraform/terraform.tfvars.example` to `terraform.tfvars`.
2. Put secrets in SSM Parameter Store (SecureString) under `/smarthome/<env>/`:
   `DATABASE_URL`, `MONGO_URL`, `MONGO_DB`, `JWT_SECRET`, `INTERNAL_API_KEY`, `CORS_ORIGINS`
   (any other key from `.env.example` can be overridden the same way).
3. `scripts/deploy.sh <env> <artifact-bucket>` once so `releases/current.tar.gz` exists.
4. `cd infra/terraform && terraform init && terraform apply`.
5. Confirm the alarm email subscription. Shell access: `aws ssm start-session --target <instance-id>`.

Data tier hooks for `rds.tf` / Mongo: use `aws_db_subnet_group.data`, `aws_security_group.postgres`
and `aws_security_group.mongo` (also exported as outputs).

> Not yet validated with `terraform validate`/`plan` — Terraform wasn't available where this was
> written. Run both before the first apply.
