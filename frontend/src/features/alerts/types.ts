export type AlertRole = "admin" | "owner";
export type AlertSeverity = "critical" | "high" | "medium" | "low";
export type AlertState = "new" | "notified" | "acknowledged" | "escalated" | "resolved" | "false_positive";

export type Alert = {
  alert_id: number;
  event_id: number;
  house_id: number;
  room_id: number;
  device_id: number;
  alert_category: string;
  sound_type: string | null;
  severity: AlertSeverity;
  state: AlertState;
  suppressed_count: number;
  version: number;
  created_at: string | null;
  updated_at: string | null;
  // Present only for administrators. Owner responses intentionally omit it.
  confidence?: number;
};

export type AlertHistory = {
  history_id: number;
  from_state: AlertState | null;
  to_state: AlertState;
  actor_user_id: number | null;
  note: string | null;
  changed_at: string | null;
};

export type AlertDelivery = {
  notification_id: number;
  recipient_id: number | null;
  recipient_label: string | null;
  channel: "email" | "sms";
  status: "pending" | "sent" | "failed";
  attempts: number;
  last_error: string | null;
  sent_at: string | null;
};

export type AlertDetail = Alert & { history: AlertHistory[]; deliveries: AlertDelivery[] };
export type AlertPage = { items: Alert[]; total: number; page: number; page_size: number };
export type AlertFilters = {
  house_id?: number;
  severity?: AlertSeverity;
  state?: AlertState;
  category?: string;
  sound_type?: string;
  from?: string;
  to?: string;
  min_confidence?: number;
  max_confidence?: number;
  q?: string;
};

export type AlertStats = {
  total: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
  by_state: Record<string, number>;
};

export type FalseAlertStat = {
  sound_type: string;
  total: number;
  false_positive: number;
  rate: number;
  sample_count: number;
  low_sample: boolean;
};

export type NotificationPreference = {
  alert_category: string;
  email: boolean;
  sms: boolean;
  min_severity: AlertSeverity;
};

export type Threshold = {
  id: number;
  scope: "global" | "house" | "device";
  scope_id: number | null;
  sound_type: string;
  threshold: number;
};
