import type { RetentionPolicy } from "../features/dataops/types";

export function retentionError(policy: RetentionPolicy): string | null {
  if (!Number.isInteger(policy.clip_expire_days) || policy.clip_expire_days < 1 || !Number.isInteger(policy.telemetry_ttl_days) || policy.telemetry_ttl_days < 1) return "Recording and telemetry retention must be positive whole days.";
  const transition = policy.clip_ia_transition_days;
  if (transition !== null && (!Number.isInteger(transition) || transition < 1 || transition >= policy.clip_expire_days)) return "Storage transition must be a positive whole day earlier than recording expiry.";
  return null;
}
