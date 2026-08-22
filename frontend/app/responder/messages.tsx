import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { ArrowLeft, MessageSquare, Send, Shield, User } from 'lucide-react-native';
import Toast from 'react-native-toast-message';
import { incidentAssignmentApi, responderApi } from '@/lib/api';
import type { OperationalMessageRecord, ResponderSelfProfile } from '@/types';

export default function ResponderMessagesScreen() {
  const params = useLocalSearchParams<{ incident_id?: string }>();
  const [messages, setMessages] = useState<OperationalMessageRecord[]>([]);
  const [profile, setProfile] = useState<ResponderSelfProfile | null>(null);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(fetchMessagesOnly, 4000);
    return () => clearInterval(interval);
  }, [params.incident_id]);

  async function loadData() {
    try {
      setLoading(true);
      const profRes = await responderApi.getMe();
      if (profRes?.data) {
        setProfile(profRes.data);
      }
      const incId = params.incident_id || profRes?.data?.active_incident?.incident_id;
      if (incId) {
        const msgRes = await incidentAssignmentApi.getMessages(incId);
        if (Array.isArray(msgRes.data)) {
          setMessages(msgRes.data);
        }
        await incidentAssignmentApi.markMessagesRead(incId);
      }
    } catch (e: any) {
      console.warn('Failed to load operational comms:', e);
    } finally {
      setLoading(false);
    }
  }

  async function fetchMessagesOnly() {
    const incId = params.incident_id || profile?.active_incident?.incident_id;
    if (!incId) return;
    try {
      const msgRes = await incidentAssignmentApi.getMessages(incId);
      if (Array.isArray(msgRes.data)) {
        setMessages(msgRes.data);
      }
    } catch (e) {
      // Background poll silently
    }
  }

  async function handleSendMessage() {
    const content = inputText.trim();
    const incId = params.incident_id || profile?.active_incident?.incident_id;
    if (!content || !incId) return;

    try {
      setSending(true);
      setInputText('');
      const res = await incidentAssignmentApi.sendMessage(incId, {
        content,
        assignment_id: profile?.active_assignment?.assignment_id,
      });
      if (res.data) {
        setMessages((prev) => [...prev, res.data]);
        setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
      }
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Message Transmission Failed',
        text2: err?.response?.data?.detail || err?.message || 'Could not send operational message',
      });
    } finally {
      setSending(false);
    }
  }

  const incId = params.incident_id || profile?.active_incident?.incident_id;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      {/* Top Comms Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.headerBackBtn} onPress={() => router.back()}>
          <ArrowLeft size={20} color="#F8FAFC" />
        </TouchableOpacity>
        <View style={styles.headerTitleWrap}>
          <Text style={styles.headerTitle}>OPERATIONAL COMMS</Text>
          <Text style={styles.headerSubtitle}>
            {incId ? `Incident: ${incId}` : 'Secure Tactical Link'}
          </Text>
        </View>
        <View style={styles.liveIndicator}>
          <View style={styles.liveDot} />
          <Text style={styles.liveText}>ENCRYPTED</Text>
        </View>
      </View>

      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#3B82F6" />
          <Text style={styles.loadingText}>Establishing Comms Channel...</Text>
        </View>
      ) : !incId ? (
        <View style={styles.centerContainer}>
          <MessageSquare size={32} color="#4B5563" />
          <Text style={styles.emptyTitle}>No Active Incident Linked</Text>
          <Text style={styles.emptySub}>
            Operational comms are established during active incident assignments.
          </Text>
        </View>
      ) : (
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.message_id}
          contentContainerStyle={styles.messagesList}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: false })}
          ListEmptyComponent={
            <View style={styles.emptyChatWrap}>
              <Text style={styles.emptyChatText}>
                No messages yet. Dispatch and responder messages will appear here.
              </Text>
            </View>
          }
          renderItem={({ item }) => {
            const isMe = item.sender_type === 'RESPONDER';
            const isAuthority = item.sender_type === 'AUTHORITY';
            return (
              <View
                style={[
                  styles.messageBubbleWrap,
                  isMe ? styles.myMessageWrap : styles.theirMessageWrap,
                ]}
              >
                <View
                  style={[
                    styles.messageBubble,
                    isMe
                      ? styles.myMessageBubble
                      : isAuthority
                      ? styles.authorityMessageBubble
                      : styles.systemMessageBubble,
                  ]}
                >
                  <View style={styles.senderHeader}>
                    <Text
                      style={[
                        styles.senderName,
                        isMe
                          ? styles.mySenderText
                          : isAuthority
                          ? styles.authoritySenderText
                          : styles.systemSenderText,
                      ]}
                    >
                      {item.sender_name || (isMe ? 'Field Unit (You)' : isAuthority ? 'Authority Command' : 'System')}
                    </Text>
                    <Text style={styles.messageTime}>
                      {new Date(item.timestamp).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </Text>
                  </View>
                  <Text style={styles.messageBody}>{item.content}</Text>
                </View>
              </View>
            );
          }}
        />
      )}

      {/* Message Input Box */}
      {incId && (
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.textInput}
            placeholder="Type tactical message to Command..."
            placeholderTextColor="#64748B"
            value={inputText}
            onChangeText={setInputText}
            multiline
            maxLength={1000}
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!inputText.trim() || sending) && styles.sendBtnDisabled]}
            disabled={!inputText.trim() || sending}
            onPress={handleSendMessage}
          >
            {sending ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Send size={18} color="#FFFFFF" />
            )}
          </TouchableOpacity>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090D16',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
    gap: 10,
  },
  loadingText: {
    color: '#94A3B8',
    fontSize: 13,
  },
  emptyTitle: {
    color: '#94A3B8',
    fontSize: 15,
    fontWeight: '700',
  },
  emptySub: {
    color: '#64748B',
    fontSize: 12,
    textAlign: 'center',
  },
  header: {
    paddingTop: 54,
    paddingHorizontal: 16,
    paddingBottom: 14,
    backgroundColor: '#0D1424',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerBackBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitleWrap: {
    alignItems: 'center',
  },
  headerTitle: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  headerSubtitle: {
    color: '#94A3B8',
    fontSize: 11,
  },
  liveIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#1E293B',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#10B981',
  },
  liveText: {
    color: '#10B981',
    fontSize: 10,
    fontWeight: '700',
  },
  messagesList: {
    padding: 16,
    gap: 12,
  },
  emptyChatWrap: {
    padding: 32,
    alignItems: 'center',
  },
  emptyChatText: {
    color: '#64748B',
    fontSize: 12,
    textAlign: 'center',
  },
  messageBubbleWrap: {
    flexDirection: 'row',
    marginVertical: 2,
  },
  myMessageWrap: {
    justifyContent: 'flex-end',
  },
  theirMessageWrap: {
    justifyContent: 'flex-start',
  },
  messageBubble: {
    maxWidth: '82%',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 14,
  },
  myMessageBubble: {
    backgroundColor: '#1E3A8A',
    borderBottomRightRadius: 2,
  },
  authorityMessageBubble: {
    backgroundColor: '#1E293B',
    borderBottomLeftRadius: 2,
    borderWidth: 1,
    borderColor: '#334155',
  },
  systemMessageBubble: {
    backgroundColor: '#2D2013',
    borderColor: '#78350F',
    borderWidth: 1,
  },
  senderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  senderName: {
    fontSize: 11,
    fontWeight: '700',
  },
  mySenderText: {
    color: '#93C5FD',
  },
  authoritySenderText: {
    color: '#FCA5A5',
  },
  systemSenderText: {
    color: '#FDE68A',
  },
  messageTime: {
    color: '#94A3B8',
    fontSize: 9,
  },
  messageBody: {
    color: '#F8FAFC',
    fontSize: 13,
    lineHeight: 18,
  },
  inputContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#0D1424',
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  textInput: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: '#F8FAFC',
    fontSize: 13,
    maxHeight: 100,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#2563EB',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: '#334155',
  },
});
