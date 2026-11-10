export type HealthSnapshot = {
  postgres: string;
  mongo: string;
  s3: string;
  sqs: { visible: number; in_flight: number };
  dlq: { visible: number };
  backups: { rds_snapshot_age_h: number | null; mongo_dump_age_d: number | null };
  unprocessed_events: number;
};

export type PipelineEvent = {
  event_id: number;
  house_id: number;
  device_id: number;
  processing_state: "queued" | "scored" | "failed";
  retry_count: number;
  s3_key?: string;
  captured_at: string;
  correlation_id?: string;
};

export type InferenceLog = {
  id: string;
  event_id: number;
  house_id: number;
  model?: { name?: string; version?: string };
  predictions?: Array<{ label: string; confidence: number }>;
  created_at?: string;
};

export type AuditRow = {
  audit_id: number;
  actor_user_id: number;
  house_id: number | null;
  action: string;
  resource?: string;
  ts?: string;
};

export type RetentionPolicy = {
  clip_expire_days: number;
  clip_ia_transition_days: number | null;
  telemetry_ttl_days: number;
};
