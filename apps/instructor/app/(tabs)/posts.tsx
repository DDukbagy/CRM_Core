import { useEffect, useState, useCallback } from "react";
import { View, Text, ScrollView, Pressable, Alert, Modal, TextInput, Switch, StyleSheet } from "react-native";
import { apiFetch } from "@/lib/api";
import type { PostRead } from "@/types/api";

export default function PostsScreen() {
  const [posts, setPosts] = useState<PostRead[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ type: "PROMOTION" as "PROMOTION" | "FEEDBACK", title: "", content: "", media_url: "", customer_id: "", is_public: false });

  const load = useCallback(async () => {
    try { setPosts(await apiFetch<PostRead[]>("/instructor-posts")); } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createPost() {
    if (!form.content && !form.title) { Alert.alert("오류", "제목 또는 내용을 입력해주세요."); return; }
    try {
      const body: Record<string, unknown> = { type: form.type, title: form.title || null, content: form.content || null, media_url: form.media_url || null, is_public: form.is_public };
      if (form.type === "FEEDBACK" && form.customer_id) body.customer_id = form.customer_id;
      await apiFetch("/instructor-posts", { method: "POST", body });
      setShowModal(false);
      setForm({ type: "PROMOTION", title: "", content: "", media_url: "", customer_id: "", is_public: false });
      await load();
    } catch (e: unknown) {
      Alert.alert("오류", e instanceof Error ? e.message : "게시물 등록 실패");
    }
  }

  async function deletePost(id: string) {
    Alert.alert("삭제", "게시물을 삭제하시겠습니까?", [
      { text: "취소", style: "cancel" },
      { text: "삭제", style: "destructive", onPress: async () => {
        try { await apiFetch(`/instructor-posts/${id}`, { method: "DELETE" }); await load(); }
        catch { Alert.alert("오류", "삭제 실패"); }
      }},
    ]);
  }

  return (
    <View style={s.container}>
      <Pressable style={s.fab} onPress={() => setShowModal(true)}>
        <Text style={s.fabText}>+ 게시물 등록</Text>
      </Pressable>

      <ScrollView contentContainerStyle={{ paddingTop: 8 }}>
        {posts.length === 0
          ? <View style={s.empty}><Text style={s.emptyText}>등록된 게시물이 없습니다.</Text></View>
          : posts.map(p => (
            <View key={p.id} style={s.card}>
              <View style={s.cardHeader}>
                <View style={[s.typeBadge, p.type === "PROMOTION" ? s.promo : s.feedback]}>
                  <Text style={s.typeText}>{p.type === "PROMOTION" ? "프로모션" : "피드백"}</Text>
                </View>
                {p.is_public
                  ? <Text style={s.pubTag}>공개</Text>
                  : <Text style={s.privateTag}>비공개</Text>
                }
              </View>
              {p.title && <Text style={s.postTitle}>{p.title}</Text>}
              {p.content && <Text style={s.postContent} numberOfLines={3}>{p.content}</Text>}
              {p.media_url && <Text style={s.mediaUrl} numberOfLines={1}>미디어</Text>}
              <Pressable onPress={() => deletePost(p.id)} style={s.deleteBtn}>
                <Text style={s.deleteText}>삭제</Text>
              </Pressable>
            </View>
          ))
        }
      </ScrollView>

      <Modal visible={showModal} animationType="slide" presentationStyle="pageSheet">
        <View style={s.modal}>
          <View style={s.modalHeader}>
            <Text style={s.modalTitle}>게시물 등록</Text>
            <Pressable onPress={() => setShowModal(false)}><Text style={s.modalClose}>✕</Text></Pressable>
          </View>

          <ScrollView style={s.modalBody}>
            {/* 타입 선택 */}
            <Text style={s.label}>유형</Text>
            <View style={s.typeRow}>
              {(["PROMOTION", "FEEDBACK"] as const).map(t => (
                <Pressable key={t} onPress={() => setForm(f => ({ ...f, type: t }))}
                  style={[s.typeBtn, form.type === t && s.typeBtnSel]}>
                  <Text style={[s.typeBtnText, form.type === t && s.typeBtnTextSel]}>
                    {t === "PROMOTION" ? "프로모션" : "고객 피드백"}
                  </Text>
                </Pressable>
              ))}
            </View>

            {form.type === "FEEDBACK" && (
              <>
                <Text style={s.label}>고객 ID</Text>
                <TextInput value={form.customer_id} onChangeText={v => setForm(f => ({ ...f, customer_id: v }))}
                  placeholder="고객 UUID 입력" style={s.input} />
              </>
            )}

            <Text style={s.label}>제목 (선택)</Text>
            <TextInput value={form.title} onChangeText={v => setForm(f => ({ ...f, title: v }))}
              placeholder="제목 입력" style={s.input} />

            <Text style={s.label}>내용</Text>
            <TextInput value={form.content} onChangeText={v => setForm(f => ({ ...f, content: v }))}
              placeholder="내용 입력" style={[s.input, s.inputMulti]} multiline numberOfLines={5} />

            <Text style={s.label}>미디어 URL (선택)</Text>
            <TextInput value={form.media_url} onChangeText={v => setForm(f => ({ ...f, media_url: v }))}
              placeholder="https://..." style={s.input} autoCapitalize="none" />

            <View style={s.switchRow}>
              <Text style={s.label}>전체 공개</Text>
              <Switch value={form.is_public} onValueChange={v => setForm(f => ({ ...f, is_public: v }))}
                trackColor={{ true: "#16a34a" }} />
            </View>
            {form.type === "FEEDBACK" && form.is_public && (
              <Text style={s.hint}>※ 피드백 공개는 고객 동의가 있어야 실제로 공개됩니다.</Text>
            )}

            <Pressable onPress={createPost} style={s.submitBtn}>
              <Text style={s.submitText}>등록</Text>
            </Pressable>
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  fab: { margin: 16, backgroundColor: "#16a34a", padding: 14, borderRadius: 10, alignItems: "center" },
  fabText: { color: "#fff", fontWeight: "700", fontSize: 15 },
  empty: { padding: 40, alignItems: "center" },
  emptyText: { color: "#9ca3af" },
  card: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 10, borderRadius: 12, padding: 14, elevation: 1 },
  cardHeader: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 8 },
  typeBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  promo: { backgroundColor: "#dbeafe" },
  feedback: { backgroundColor: "#fef3c7" },
  typeText: { fontSize: 11, fontWeight: "600", color: "#1e40af" },
  pubTag: { fontSize: 11, color: "#16a34a", fontWeight: "600" },
  privateTag: { fontSize: 11, color: "#9ca3af" },
  postTitle: { fontSize: 16, fontWeight: "700", marginBottom: 4 },
  postContent: { fontSize: 14, color: "#374151", lineHeight: 20, marginBottom: 6 },
  mediaUrl: { fontSize: 12, color: "#3b82f6", marginBottom: 6 },
  deleteBtn: { alignSelf: "flex-end", paddingHorizontal: 10, paddingVertical: 4 },
  deleteText: { color: "#ef4444", fontSize: 13 },
  modal: { flex: 1, backgroundColor: "#fff" },
  modalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 20, borderBottomWidth: 1, borderColor: "#e5e7eb" },
  modalTitle: { fontSize: 18, fontWeight: "700" },
  modalClose: { fontSize: 20, color: "#6b7280" },
  modalBody: { padding: 20 },
  label: { fontSize: 13, fontWeight: "600", color: "#374151", marginBottom: 6, marginTop: 14 },
  typeRow: { flexDirection: "row", gap: 8 },
  typeBtn: { flex: 1, padding: 10, borderRadius: 8, borderWidth: 1, borderColor: "#e5e7eb", alignItems: "center" },
  typeBtnSel: { borderColor: "#16a34a", backgroundColor: "#f0fdf4" },
  typeBtnText: { fontSize: 13, color: "#6b7280" },
  typeBtnTextSel: { color: "#16a34a", fontWeight: "600" },
  input: { borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 8, padding: 12, fontSize: 15 },
  inputMulti: { height: 100, textAlignVertical: "top" },
  switchRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 14 },
  hint: { fontSize: 12, color: "#f59e0b", marginTop: 4 },
  submitBtn: { backgroundColor: "#16a34a", padding: 14, borderRadius: 10, alignItems: "center", marginTop: 24, marginBottom: 40 },
  submitText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});
