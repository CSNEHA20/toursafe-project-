export type NotificationChannel = "IN_APP" | "REALTIME" | "PUSH" | "SMS" | "EMAIL" | "VOICE";

export type NotificationPriority = "LOW" | "NORMAL" | "HIGH" | "CRITICAL";

export type NotificationCategory =
  | "SAFETY"
  | "INCIDENT"
  | "SOS"
  | "ZONE"
  | "RESPONDER"
  | "ASSIGNMENT"
  | "SYSTEM"
  | "ACCOUNT";

export type NotificationStatus =
  | "CREATED"
  | "QUEUED"
  | "SENDING"
  | "SENT"
  | "DELIVERED"
  | "FAILED"
  | "RETRYING"
  | "CANCELLED"
  | "EXPIRED"
  | "NOT_CONFIGURED"
  | "UNKNOWN";

export type RecipientType = "TOURIST" | "AUTHORITY" | "RESPONDER" | "EMERGENCY_CONTACT" | "SYSTEM";

export interface NotificationPayload {
  title: string;
  body: string;
  data?: Record<string, any>;
  action_url?: string;
  incident_id?: string;
  zone_id?: string;
  assignment_id?: string;
  deep_link?: string;
}

export interface NotificationRecord {
  notification_id: string;
  event_id: string;
  recipient_id: string;
  recipient_type: RecipientType;
  recipient_target?: string;
  incident_id?: string;
  channel: NotificationChannel;
  priority: NotificationPriority;
  category: NotificationCategory;
  template_id?: string;
  template_version?: string;
  policy_version?: string;
  idempotency_key: string;
  correlation_id?: string;
  status: NotificationStatus;
  payload: NotificationPayload;
  created_at: string;
  scheduled_at?: string;
  sent_at?: string;
  delivered_at?: string;
  failed_at?: string;
  expires_at?: string;
  provider: string;
  provider_message_id?: string;
  retry_count: number;
  max_retries: number;
  error_code?: string;
  error_message?: string;
  is_read: boolean;
  read_at?: string;
}

export interface UserNotificationPreferences {
  user_id: string;
  user_role: string;
  in_app_enabled: boolean;
  realtime_enabled: boolean;
  push_enabled: boolean;
  email_enabled: boolean;
  sms_enabled: boolean;
  voice_enabled: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  category_preferences?: Record<string, any>;
}

export interface ProviderHealthResponse {
  provider_name: string;
  channel: NotificationChannel;
  configured: boolean;
  status: string;
  detail: string;
  last_health_check?: string;
}
