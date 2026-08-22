/**
 * TourSafe Authority AI Copilot Panel.
 * Premium B2G Command Center decision-support UI with grounded reasoning,
 * tool activity status, source citation badges, and human-in-the-loop action confirmations.
 */

import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  ActionProposal,
  CitationSource,
  CopilotMessage,
  CopilotSession,
  copilotApi,
} from "@/lib/copilotApi";
import { MaterialCommunityIcons } from "@expo/vector-icons";

interface CopilotPanelProps {
  visible: boolean;
  onClose: () => void;
  activeIncidentId?: string;
  activeZoneId?: string;
  activeResponderId?: string;
}

const SUGGESTED_QUESTIONS = [
  "What is happening right now?",
  "Which zones need attention?",
  "Why did response time increase today?",
  "Which responder units are under pressure?",
  "What does the escalation policy require?",
  "What changed in the last hour?",
];

export const CopilotPanel: React.FC<CopilotPanelProps> = ({
  visible,
  onClose,
  activeIncidentId,
  activeZoneId,
  activeResponderId,
}) => {
  const [session, setSession] = useState<CopilotSession | null>(null);
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [toolActivity, setToolActivity] = useState<string | null>(null);
  const [actionConfirming, setActionConfirming] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<Record<string, string>>({});
  const scrollViewRef = useRef<ScrollView>(null);

  // Initialize or resume session
  useEffect(() => {
    if (visible) {
      initSession();
    }
  }, [visible, activeIncidentId, activeZoneId]);

  const initSession = async () => {
    try {
      setLoading(true);
      const sessions = await copilotApi.listSessions(1);
      let activeSession: CopilotSession;
      if (sessions && sessions.length > 0) {
        activeSession = sessions[0];
      } else {
        activeSession = await copilotApi.createSession({
          title: "Command Center Operations",
          active_incident_id: activeIncidentId,
          active_zone_id: activeZoneId,
          active_responder_id: activeResponderId,
        });
      }
      setSession(activeSession);
      const data = await copilotApi.getSession(activeSession.session_id);
      setMessages(data.messages || []);
    } catch (e) {
      console.warn("Failed initializing copilot session:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend || inputText;
    if (!query.trim() || !session || loading) return;

    setInputText("");
    const tempUserMsg: CopilotMessage = {
      message_id: `temp_${Date.now()}`,
      session_id: session.session_id,
      role: "USER",
      content: query,
      citations: [],
      tool_calls: [],
      tool_results: [],
      tokens_input: 0,
      tokens_output: 0,
      latency_ms: 0,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setLoading(true);
    setToolActivity("Analyzing TourSafe live operational state...");

    try {
      // Simulate progressive tool activity update
      setTimeout(() => setToolActivity("Querying telemetry & safety fusion..."), 400);

      const resp = await copilotApi.sendMessage(session.session_id, query, {
        active_incident_id: activeIncidentId,
        active_zone_id: activeZoneId,
        active_responder_id: activeResponderId,
      });

      setMessages((prev) => [...prev, resp]);
    } catch (e: any) {
      const errorMsg: CopilotMessage = {
        message_id: `err_${Date.now()}`,
        session_id: session.session_id,
        role: "ASSISTANT",
        content: `⚠️ Failed to reach Copilot engine: ${e?.message || "Operational service unavailable"}`,
        citations: [],
        tool_calls: [],
        tool_results: [],
        tokens_input: 0,
        tokens_output: 0,
        latency_ms: 0,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
      setToolActivity(null);
      setTimeout(() => scrollViewRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  const handleConfirmAction = async (action: ActionProposal) => {
    setActionConfirming(action.action_id);
    try {
      const res = await copilotApi.confirmAction(
        action.action_id,
        action.confirmation_token,
        action.idempotency_key
      );
      setActionFeedback((prev) => ({
        ...prev,
        [action.action_id]: `✅ Confirmed: ${res.message}`,
      }));
    } catch (e: any) {
      setActionFeedback((prev) => ({
        ...prev,
        [action.action_id]: `❌ Error: ${e?.response?.data?.detail || e.message}`,
      }));
    } finally {
      setActionConfirming(null);
    }
  };

  const handleCancelAction = async (action: ActionProposal) => {
    setActionConfirming(action.action_id);
    try {
      const res = await copilotApi.cancelAction(action.action_id, "Cancelled by operator");
      setActionFeedback((prev) => ({
        ...prev,
        [action.action_id]: `🚫 Cancelled: ${res.message}`,
      }));
    } catch (e: any) {
      setActionFeedback((prev) => ({
        ...prev,
        [action.action_id]: `❌ Error: ${e?.message}`,
      }));
    } finally {
      setActionConfirming(null);
    }
  };

  const handleFeedback = async (messageId: string, rating: "HELPFUL" | "NOT_HELPFUL") => {
    try {
      await copilotApi.submitFeedback(messageId, rating);
      setActionFeedback((prev) => ({ ...prev, [messageId]: `Feedback recorded: ${rating}` }));
    } catch (e) {
      console.warn("Feedback error:", e);
    }
  };

  if (!visible) return null;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View className="flex-1 bg-black/60 justify-end md:justify-center md:items-center">
        <View className="w-full md:w-[680px] h-[90%] md:h-[760px] bg-[#0F172A] border border-slate-700/80 rounded-t-2xl md:rounded-2xl shadow-2xl flex-col overflow-hidden">
          
          {/* Header */}
          <View className="flex-row items-center justify-between px-5 py-4 bg-[#1E293B] border-b border-slate-700">
            <View className="flex-row items-center space-x-3">
              <View className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 items-center justify-center">
                <MaterialCommunityIcons name="shield-account" size={20} color="#06B6D4" />
              </View>
              <View>
                <Text className="text-white font-bold text-base tracking-wide">TourSafe Authority AI Copilot</Text>
                <Text className="text-xs text-slate-400">Database-Grounded Decision Support</Text>
              </View>
            </View>

            <View className="flex-row items-center space-x-2">
              {activeIncidentId && (
                <View className="px-2 py-0.5 rounded bg-amber-500/20 border border-amber-500/40">
                  <Text className="text-amber-400 text-xs font-mono">{activeIncidentId}</Text>
                </View>
              )}
              <Pressable
                onPress={onClose}
                className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center hover:bg-slate-700"
              >
                <MaterialCommunityIcons name="close" size={18} color="#94A3B8" />
              </Pressable>
            </View>
          </View>

          {/* Suggested Queries Chips */}
          <View className="bg-[#0B1120] py-2 px-4 border-b border-slate-800">
            <ScrollView horizontal showsHorizontalScrollIndicator={false} className="flex-row">
              {SUGGESTED_QUESTIONS.map((q, idx) => (
                <Pressable
                  key={idx}
                  onPress={() => handleSendMessage(q)}
                  className="mr-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700 hover:border-cyan-500/50"
                >
                  <Text className="text-xs text-slate-300">{q}</Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>

          {/* Messages Thread */}
          <ScrollView
            ref={scrollViewRef}
            className="flex-1 p-4 bg-[#0B1120]"
            contentContainerStyle={{ paddingBottom: 24 }}
          >
            {messages.map((m, idx) => {
              const isUser = m.role === "USER";
              const feedbackState = actionFeedback[m.message_id];

              return (
                <View
                  key={m.message_id || idx}
                  className={`mb-4 flex-col ${isUser ? "items-end" : "items-start"}`}
                >
                  <View
                    className={`max-w-[90%] p-4 rounded-xl ${
                      isUser
                        ? "bg-cyan-900/30 border border-cyan-500/40"
                        : "bg-[#1E293B] border border-slate-700/80"
                    }`}
                  >
                    {/* Role Header */}
                    <View className="flex-row items-center justify-between mb-2">
                      <Text className={`text-xs font-semibold uppercase tracking-wider ${isUser ? "text-cyan-400" : "text-slate-400"}`}>
                        {isUser ? "Authority Officer" : "TourSafe Copilot"}
                      </Text>
                      {m.data_freshness && (
                        <Text className="text-[10px] text-slate-400 font-mono">
                          {m.data_freshness}
                        </Text>
                      )}
                    </View>

                    {/* Content */}
                    <Text className="text-slate-100 text-sm leading-relaxed whitespace-pre-wrap">
                      {m.content}
                    </Text>

                    {/* Citations Badges */}
                    {m.citations && m.citations.length > 0 && (
                      <View className="mt-3 pt-2 border-t border-slate-700/60">
                        <Text className="text-[11px] text-slate-400 font-medium mb-1.5">Evidence & Grounding:</Text>
                        <View className="flex-row flex-wrap gap-1.5">
                          {m.citations.map((c, cIdx) => (
                            <View
                              key={cIdx}
                              className="px-2 py-1 rounded bg-slate-800/90 border border-slate-600/60 flex-row items-center space-x-1"
                            >
                              <MaterialCommunityIcons
                                name={c.source_type === "document" ? "file-document-outline" : "database-check"}
                                size={12}
                                color="#38BDF8"
                              />
                              <Text className="text-[10px] text-sky-300 font-mono">
                                {c.title} {c.section ? `(${c.section})` : ""}
                              </Text>
                            </View>
                          ))}
                        </View>
                      </View>
                    )}

                    {/* Action Proposal Preview Card */}
                    {m.action_proposal && (
                      <View className="mt-4 p-3.5 rounded-lg bg-amber-950/30 border border-amber-500/60">
                        <View className="flex-row items-center space-x-2 mb-2">
                          <MaterialCommunityIcons name="alert-decagram" size={16} color="#F59E0B" />
                          <Text className="text-xs font-bold text-amber-400 uppercase tracking-wider">
                            Action Proposal: {m.action_proposal.action_type.replace("_", " ")}
                          </Text>
                        </View>

                        <Text className="text-xs text-slate-200 mb-1">
                          <Text className="font-semibold text-slate-400">Target: </Text>
                          {m.action_proposal.target_description}
                        </Text>

                        <Text className="text-xs text-slate-200 mb-1">
                          <Text className="font-semibold text-slate-400">Reason: </Text>
                          {m.action_proposal.reason}
                        </Text>

                        <Text className="text-xs text-slate-300 mb-3 italic">
                          Expected Effect: {m.action_proposal.expected_effect}
                        </Text>

                        {actionFeedback[m.action_proposal.action_id] ? (
                          <View className="py-2 px-3 rounded bg-slate-900 border border-slate-700">
                            <Text className="text-xs font-mono text-slate-200">
                              {actionFeedback[m.action_proposal.action_id]}
                            </Text>
                          </View>
                        ) : (
                          <View className="flex-row space-x-2 justify-end">
                            <Pressable
                              onPress={() => handleCancelAction(m.action_proposal!)}
                              disabled={actionConfirming === m.action_proposal.action_id}
                              className="px-3 py-1.5 rounded bg-slate-800 border border-slate-600 hover:bg-slate-700"
                            >
                              <Text className="text-xs font-medium text-slate-300">Cancel</Text>
                            </Pressable>
                            <Pressable
                              onPress={() => handleConfirmAction(m.action_proposal!)}
                              disabled={actionConfirming === m.action_proposal.action_id}
                              className="px-4 py-1.5 rounded bg-emerald-600 border border-emerald-500 flex-row items-center space-x-1.5 hover:bg-emerald-500"
                            >
                              {actionConfirming === m.action_proposal.action_id ? (
                                <ActivityIndicator size="small" color="#FFFFFF" />
                              ) : (
                                <>
                                  <MaterialCommunityIcons name="check-bold" size={12} color="#FFFFFF" />
                                  <Text className="text-xs font-bold text-white">Confirm Execution</Text>
                                </>
                              )}
                            </Pressable>
                          </View>
                        )}
                      </View>
                    )}

                    {/* Feedback Actions for Assistant Messages */}
                    {!isUser && !m.action_proposal && (
                      <View className="mt-2.5 flex-row items-center justify-between border-t border-slate-800/80 pt-1.5">
                        <Text className="text-[10px] text-slate-500 font-mono">
                          {m.latency_ms > 0 ? `${m.latency_ms.toFixed(0)}ms` : "grounded"}
                        </Text>
                        {feedbackState ? (
                          <Text className="text-[10px] text-emerald-400 font-mono">{feedbackState}</Text>
                        ) : (
                          <View className="flex-row items-center space-x-2">
                            <Pressable
                              onPress={() => handleFeedback(m.message_id, "HELPFUL")}
                              className="p-1 rounded hover:bg-slate-800"
                            >
                              <MaterialCommunityIcons name="thumb-up-outline" size={13} color="#64748B" />
                            </Pressable>
                            <Pressable
                              onPress={() => handleFeedback(m.message_id, "NOT_HELPFUL")}
                              className="p-1 rounded hover:bg-slate-800"
                            >
                              <MaterialCommunityIcons name="thumb-down-outline" size={13} color="#64748B" />
                            </Pressable>
                          </View>
                        )}
                      </View>
                    )}
                  </View>
                </View>
              );
            })}

            {/* Live Tool Activity Progress */}
            {toolActivity && (
              <View className="p-3 rounded-lg bg-slate-900 border border-slate-700/60 flex-row items-center space-x-2.5 my-2">
                <ActivityIndicator size="small" color="#06B6D4" />
                <Text className="text-xs text-cyan-400 font-mono">{toolActivity}</Text>
              </View>
            )}
          </ScrollView>

          {/* Input Bar */}
          <View className="p-4 bg-[#1E293B] border-t border-slate-700 flex-row items-center space-x-3">
            <TextInput
              value={inputText}
              onChangeText={setInputText}
              placeholder="Ask Copilot about incidents, risk zones, responder workloads, or procedures..."
              placeholderTextColor="#64748B"
              className="flex-1 bg-[#0B1120] text-slate-100 px-4 py-2.5 rounded-xl border border-slate-700 text-sm"
              onSubmitEditing={() => handleSendMessage()}
              returnKeyType="send"
              editable={!loading}
            />
            <Pressable
              onPress={() => handleSendMessage()}
              disabled={loading || !inputText.trim()}
              className={`w-10 h-10 rounded-xl items-center justify-center ${
                loading || !inputText.trim() ? "bg-slate-800 opacity-50" : "bg-cyan-600 hover:bg-cyan-500"
              }`}
            >
              {loading ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <MaterialCommunityIcons name="send" size={18} color="#FFFFFF" />
              )}
            </Pressable>
          </View>

        </View>
      </View>
    </Modal>
  );
};
