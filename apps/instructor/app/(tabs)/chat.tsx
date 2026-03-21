import { useState, useCallback, useRef, useEffect } from "react";
import {
  View, Text, StyleSheet, Pressable, FlatList, TextInput,
  ActivityIndicator, RefreshControl, KeyboardAvoidingView, Platform,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";

// ── 타입 ──────────────────────────────────────────────────────
interface ChatRoom {
  id: string;
  customer_id: string;
  instructor_id: string;
  other_name: string;
  other_id: string;
  last_message: string | null;
  last_message_at: string | null;
  unread_count: number;
  created_at: string;
}

interface ChatMessage {
  id: string;
  room_id: string;
  sender_id: string;
  content: string;
  is_read: boolean;
  is_mine: boolean;
  created_at: string;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "방금";
  if (mins < 60) return `${mins}분 전`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}시간 전`;
  return `${Math.floor(hrs / 24)}일 전`;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const h = d.getHours();
  const m = String(d.getMinutes()).padStart(2, "0");
  const ampm = h < 12 ? "오전" : "오후";
  return `${ampm} ${h % 12 || 12}:${m}`;
}

// ── 채팅방 목록 ───────────────────────────────────────────────
function RoomList({ onSelect }: { onSelect: (room: ChatRoom) => void }) {
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      const data = await apiFetch<ChatRoom[]>("/chat/rooms");
      setRooms(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("채팅방 목록 로딩 실패:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useFocusEffect(useCallback(() => {
    setLoading(true);
    load();
  }, []));

  if (loading) return <View style={s.center}><ActivityIndicator size="large" /></View>;

  return (
    <FlatList
      data={rooms}
      keyExtractor={(r) => r.id}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
      contentContainerStyle={rooms.length === 0 ? s.emptyContainer : undefined}
      ListEmptyComponent={
        <View style={s.emptyBox}>
          <Text style={s.emptyIcon}>💬</Text>
          <Text style={s.emptyText}>채팅방이 없습니다</Text>
          <Text style={s.emptySubText}>매칭을 수락하면 고객과 채팅이 시작됩니다</Text>
        </View>
      }
      renderItem={({ item }) => (
        <Pressable style={s.roomItem} onPress={() => onSelect(item)}>
          <View style={s.roomAvatar}>
            <Text style={s.roomAvatarText}>{item.other_name[0]}</Text>
          </View>
          <View style={s.roomInfo}>
            <View style={s.roomRow}>
              <Text style={s.roomName}>{item.other_name}</Text>
              {item.last_message_at && (
                <Text style={s.roomTime}>{timeAgo(item.last_message_at)}</Text>
              )}
            </View>
            <View style={s.roomRow}>
              <Text style={s.roomLastMsg} numberOfLines={1}>
                {item.last_message ?? "대화를 시작해보세요"}
              </Text>
              {item.unread_count > 0 && (
                <View style={s.badge}>
                  <Text style={s.badgeText}>{item.unread_count}</Text>
                </View>
              )}
            </View>
          </View>
        </Pressable>
      )}
    />
  );
}

// ── 채팅 상세 ─────────────────────────────────────────────────
function ChatDetail({ room, onBack }: { room: ChatRoom; onBack: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const flatRef = useRef<FlatList>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function loadMessages() {
    try {
      const data = await apiFetch<ChatMessage[]>(`/chat/rooms/${room.id}/messages`);
      setMessages(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("메시지 로딩 실패:", e);
    }
  }

  useEffect(() => {
    loadMessages();
    pollingRef.current = setInterval(loadMessages, 2000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [room.id]);

  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => flatRef.current?.scrollToEnd({ animated: false }), 100);
    }
  }, [messages.length]);

  async function send() {
    const content = text.trim();
    if (!content || sending) return;
    setSending(true);
    setText("");
    try {
      const msg = await apiFetch<ChatMessage>(`/chat/rooms/${room.id}/messages`, {
        method: "POST",
        body: { content },
      });
      setMessages((prev) => [...prev, msg]);
      setTimeout(() => flatRef.current?.scrollToEnd({ animated: true }), 100);
    } catch (e) {
      console.error("메시지 전송 실패:", e);
      setText(content);
    } finally {
      setSending(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={90}
    >
      <View style={s.detailHeader}>
        <Pressable onPress={onBack} style={s.backBtn}>
          <Text style={s.backBtnText}>‹</Text>
        </Pressable>
        <Text style={s.detailTitle}>{room.other_name}</Text>
      </View>

      <FlatList
        ref={flatRef}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={{ padding: 12, gap: 8 }}
        renderItem={({ item }) => (
          <View style={[s.bubble, item.is_mine ? s.bubbleMine : s.bubbleOther]}>
            <Text style={[s.bubbleText, item.is_mine ? s.bubbleTextMine : s.bubbleTextOther]}>
              {item.content}
            </Text>
            <Text style={[s.bubbleTime, item.is_mine ? s.bubbleTimeMine : s.bubbleTimeOther]}>
              {formatTime(item.created_at)}
            </Text>
          </View>
        )}
      />

      <View style={s.inputRow}>
        <TextInput
          style={s.input}
          value={text}
          onChangeText={setText}
          placeholder="메시지 입력..."
          multiline
          maxLength={2000}
        />
        <Pressable
          style={[s.sendBtn, (!text.trim() || sending) && s.sendBtnDisabled]}
          onPress={send}
          disabled={!text.trim() || sending}
        >
          <Text style={s.sendBtnText}>전송</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

// ── 메인 ─────────────────────────────────────────────────────
export default function ChatScreen() {
  const [selectedRoom, setSelectedRoom] = useState<ChatRoom | null>(null);

  if (selectedRoom) {
    return <ChatDetail room={selectedRoom} onBack={() => setSelectedRoom(null)} />;
  }
  return (
    <View style={s.container}>
      <RoomList onSelect={setSelectedRoom} />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  emptyContainer: { flex: 1 },
  emptyBox: { flex: 1, alignItems: "center", justifyContent: "center", paddingTop: 80 },
  emptyIcon: { fontSize: 48, marginBottom: 8 },
  emptyText: { fontSize: 15, fontWeight: "600", color: "#374151", marginBottom: 6 },
  emptySubText: { fontSize: 13, color: "#9ca3af", textAlign: "center", paddingHorizontal: 32 },

  roomItem: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: "#fff", paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: "#f3f4f6",
  },
  roomAvatar: {
    width: 46, height: 46, borderRadius: 23,
    backgroundColor: "#dcfce7", alignItems: "center", justifyContent: "center",
    marginRight: 12,
  },
  roomAvatarText: { fontSize: 18, fontWeight: "700", color: "#16a34a" },
  roomInfo: { flex: 1 },
  roomRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  roomName: { fontSize: 15, fontWeight: "700", color: "#111" },
  roomTime: { fontSize: 12, color: "#9ca3af" },
  roomLastMsg: { flex: 1, fontSize: 13, color: "#6b7280", marginTop: 3 },
  badge: {
    backgroundColor: "#16a34a", borderRadius: 10,
    minWidth: 20, height: 20, alignItems: "center", justifyContent: "center",
    paddingHorizontal: 5, marginLeft: 8,
  },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "700" },

  detailHeader: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: "#fff", paddingHorizontal: 8, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: "#e5e7eb",
  },
  backBtn: { padding: 8 },
  backBtnText: { fontSize: 28, color: "#16a34a", lineHeight: 30 },
  detailTitle: { fontSize: 16, fontWeight: "700", color: "#111", marginLeft: 4 },

  bubble: { maxWidth: "75%", borderRadius: 16, padding: 10 },
  bubbleMine: { alignSelf: "flex-end", backgroundColor: "#16a34a", borderBottomRightRadius: 4 },
  bubbleOther: { alignSelf: "flex-start", backgroundColor: "#fff", borderBottomLeftRadius: 4, elevation: 1, shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 3, shadowOffset: { width: 0, height: 1 } },
  bubbleText: { fontSize: 14, lineHeight: 20 },
  bubbleTextMine: { color: "#fff" },
  bubbleTextOther: { color: "#111" },
  bubbleTime: { fontSize: 10, marginTop: 4 },
  bubbleTimeMine: { color: "rgba(255,255,255,0.7)", textAlign: "right" },
  bubbleTimeOther: { color: "#9ca3af" },

  inputRow: {
    flexDirection: "row", alignItems: "flex-end",
    backgroundColor: "#fff", padding: 10,
    borderTopWidth: 1, borderTopColor: "#e5e7eb",
  },
  input: {
    flex: 1, minHeight: 40, maxHeight: 100,
    backgroundColor: "#f3f4f6", borderRadius: 20,
    paddingHorizontal: 14, paddingVertical: 8,
    fontSize: 14, color: "#111",
  },
  sendBtn: {
    marginLeft: 8, backgroundColor: "#16a34a",
    borderRadius: 20, paddingHorizontal: 16, paddingVertical: 10,
  },
  sendBtnDisabled: { backgroundColor: "#d1d5db" },
  sendBtnText: { color: "#fff", fontWeight: "700", fontSize: 14 },
});
