/**
 * TourSafe Authority AI Copilot Client API.
 * Provides typed methods for Copilot Sessions, Grounded Chat Queries,
 * Action Previews, Human Confirmations, Feedback, and Audit Logs.
 */

import { api } from "./api";

export interface CitationSource {
  source_type: string;
  title: string;
  identifier?: string;
  version?: string;
  section?: string;
  freshness?: string;
  snippet?: string;
}

export interface ToolCallRecord {
  call_id: string;
  tool_name: string;
  arguments: Record<string, any>;
  timestamp: string;
}

export interface ToolResultRecord {
  call_id: string;
  tool_name: string;
  success: boolean;
  data?: any;
  error?: string;
  source: string;
  observed_at?: string;
  latency_ms: number;
}

export interface ActionProposal {
  action_id: string;
  session_id: string;
  user_id: string;
  tool_name: string;
  action_type: string;
  target_id: string;
  target_description: string;
  reason: string;
  policy_reference?: string;
  expected_effect: string;
  parameters: Record<string, any>;
  confirmation_token: string;
  idempotency_key: string;
  status: "pending" | "confirmed" | "cancelled" | "expired" | "failed";
  created_at: string;
  expires_at: string;
  confirmed_by?: string;
  confirmed_at?: string;
  execution_result?: Record<string, any>;
}

export interface CopilotMessage {
  message_id: string;
  session_id: string;
  role: "USER" | "ASSISTANT" | "TOOL" | "SYSTEM";
  content: string;
  citations: CitationSource[];
  tool_calls: ToolCallRecord[];
  tool_results: ToolResultRecord[];
  action_proposal?: ActionProposal;
  data_freshness?: string;
  uncertainty_note?: string;
  tokens_input: number;
  tokens_output: number;
  latency_ms: number;
  model?: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface CopilotSession {
  session_id: string;
  user_id: string;
  organization_id?: string;
  jurisdiction_id?: string;
  title: string;
  status: "active" | "archived";
  context_summary?: string;
  active_incident_id?: string;
  active_zone_id?: string;
  active_responder_id?: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  metadata: Record<string, any>;
}

export interface ToolDefinition {
  name: string;
  category: string;
  description: string;
  parameters: Record<string, any>;
  required_role: string[];
  read_only: boolean;
  requires_preview: boolean;
}

export interface CopilotMetrics {
  total_sessions: number;
  total_messages: number;
  total_tool_calls: number;
  total_actions_proposed: number;
  total_actions_confirmed: number;
  feedback_breakdown: Record<string, number>;
  avg_latency_ms: number;
  total_tokens_used: number;
  tools_usage_count: Record<string, number>;
}

export const copilotApi = {
  createSession: async (data?: {
    title?: string;
    active_incident_id?: string;
    active_zone_id?: string;
    active_responder_id?: string;
  }): Promise<CopilotSession> => {
    const res = await api.post<CopilotSession>("/copilot/sessions", data || {});
    return res.data;
  },

  listSessions: async (limit = 20): Promise<CopilotSession[]> => {
    const res = await api.get<CopilotSession[]>("/copilot/sessions", { params: { limit } });
    return res.data;
  },

  getSession: async (sessionId: string): Promise<{ session: CopilotSession; messages: CopilotMessage[] }> => {
    const res = await api.get<{ session: CopilotSession; messages: CopilotMessage[] }>(`/copilot/sessions/${sessionId}`);
    return res.data;
  },

  deleteSession: async (sessionId: string): Promise<{ detail: string }> => {
    const res = await api.delete<{ detail: string }>(`/copilot/sessions/${sessionId}`);
    return res.data;
  },

  sendMessage: async (
    sessionId: string,
    content: string,
    context?: { active_incident_id?: string; active_zone_id?: string; active_responder_id?: string }
  ): Promise<CopilotMessage> => {
    const res = await api.post<CopilotMessage>(`/copilot/sessions/${sessionId}/messages`, {
      content,
      active_incident_id: context?.active_incident_id,
      active_zone_id: context?.active_zone_id,
      active_responder_id: context?.active_responder_id,
    });
    return res.data;
  },

  confirmAction: async (
    actionId: string,
    confirmationToken: string,
    idempotencyKey?: string,
    reasonNote?: string
  ): Promise<{ action_id: string; status: string; message: string; execution_result?: any }> => {
    const res = await api.post(`/copilot/actions/${actionId}/confirm`, {
      confirmation_token: confirmationToken,
      idempotency_key: idempotencyKey,
      reason_note: reasonNote,
    });
    return res.data;
  },

  cancelAction: async (
    actionId: string,
    reasonNote?: string
  ): Promise<{ action_id: string; status: string; message: string }> => {
    const res = await api.post(`/copilot/actions/${actionId}/cancel`, {
      reason_note: reasonNote,
    });
    return res.data;
  },

  submitFeedback: async (
    messageId: string,
    rating: "HELPFUL" | "NOT_HELPFUL" | "INCORRECT" | "OUTDATED",
    reason?: string
  ): Promise<{ status: string; feedback_id: string }> => {
    const res = await api.post(`/copilot/messages/${messageId}/feedback`, { rating, reason });
    return res.data;
  },

  listTools: async (): Promise<ToolDefinition[]> => {
    const res = await api.get<ToolDefinition[]>("/copilot/tools");
    return res.data;
  },

  getMetrics: async (): Promise<CopilotMetrics> => {
    const res = await api.get<CopilotMetrics>("/copilot/metrics");
    return res.data;
  },

  getAuditLogs: async (sessionId?: string, limit = 50): Promise<any[]> => {
    const res = await api.get<any[]>("/copilot/audit", { params: { session_id: sessionId, limit } });
    return res.data;
  },
};
