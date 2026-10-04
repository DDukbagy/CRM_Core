// 레슨노트 탭: 강사가 남긴 레슨 노트(글·스캔 PDF)를 본다. 피드백 게시물을 여기로 통합 (2026-10-04)
import { useState, useCallback, useRef } from "react";
import {
  View, Text, StyleSheet, FlatList, Pressable, Modal,
  ActivityIndicator, RefreshControl, ScrollView,
} from "react-native";
import { useFocusEffect } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { apiFetch } from "@/lib/api";
import type { LessonNoteRead } from "@/types/api";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "방금";
  if (mins < 60) return `${mins}분 전`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}시간 전`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}일 전`;
  return new Date(iso).toLocaleDateString("ko-KR");
}

// ─── 노트 상세 ────────────────────────────────────────────────────────────────
function NoteDetail({ note, onClose }: { note: LessonNoteRead; onClose: () => void }) {
  return (
    <Modal visible animationType="slide" presentationStyle="pageSheet">
      <View style={dt.container}>
        <View style={dt.header}>
          <Text style={dt.title}>{note.title || "레슨노트"}</Text>
          <Pressable onPress={onClose} style={dt.closeBtn}>
            <Text style={dt.closeText}>닫기</Text>
          </Pressable>
        </View>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={dt.body}>
          <Text style={dt.date}>
            {new Date(note.created_at).toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" })}
            {note.instructor_name ? ` · ${note.instructor_name} 강사` : ""}
          </Text>
          {note.content ? (
            <Text style={dt.content}>{note.content}</Text>
          ) : !note.file_url ? (
            <Text style={dt.noContent}>내용 없음</Text>
          ) : null}
          {note.file_url && (
            <Pressable style={dt.pdfBtn} onPress={() => WebBrowser.openBrowserAsync(note.file_url!)}>
              <Text style={dt.pdfBtnText}>📄 {note.file_name ?? "레슨노트.pdf"} 보기</Text>
            </Pressable>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

const dt = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 20, paddingVertical: 16,
    borderBottomWidth: 1, borderBottomColor: "#f3f4f6",
  },
  title: { fontSize: 17, fontWeight: "700", color: "#111" },
  closeBtn: { paddingHorizontal: 8, paddingVertical: 4 },
  closeText: { fontSize: 15, color: "#6b7280" },
  body: { padding: 24, gap: 12 },
  date: { fontSize: 13, color: "#9ca3af" },
  content: { fontSize: 15, color: "#374151", lineHeight: 24 },
  noContent: { fontSize: 14, color: "#9ca3af", fontStyle: "italic" },
  pdfBtn: { marginTop: 8, padding: 14, borderRadius: 10, backgroundColor: "#eff6ff", borderWidth: 1, borderColor: "#bfdbfe" },
  pdfBtnText: { fontSize: 14, color: "#2563eb", fontWeight: "600" },
});

// ─── 노트 리스트 아이템 ───────────────────────────────────────────────────────
function NoteRow({ note, onPress }: { note: LessonNoteRead; onPress: () => void }) {
  const text = note.title || note.content;
  const preview = text ? text.slice(0, 60) + (text.length > 60 ? "…" : "") : null;

  return (
    <Pressable style={s.row} onPress={onPress}>
      {note.file_url && (
        <View style={[s.thumb, s.pdfThumb]}><Text style={s.pdfThumbText}>PDF</Text></View>
      )}
      <View style={s.rowBody}>
        {preview
          ? <Text style={s.preview} numberOfLines={2}>{preview}</Text>
          : <Text style={s.noPreview}>스캔한 레슨노트</Text>
        }
        <Text style={s.rowDate}>{timeAgo(note.created_at)}{note.instructor_name ? ` · ${note.instructor_name}` : ""}</Text>
      </View>
      <Text style={s.chevron}>›</Text>
    </Pressable>
  );
}

// ─── 메인 화면 ────────────────────────────────────────────────────────────────
export default function LessonNotesScreen() {
  const [notes, setNotes] = useState<LessonNoteRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selected, setSelected] = useState<LessonNoteRead | null>(null);
  const initialLoaded = useRef(false);

  async function load() {
    try {
      const data = await apiFetch<LessonNoteRead[]>("/lesson-notes");
      setNotes(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("레슨노트 로딩 실패:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
      initialLoaded.current = true;
    }
  }

  useFocusEffect(useCallback(() => {
    if (!initialLoaded.current) setLoading(true);
    load();
  }, []));

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#16a34a" /></View>;

  return (
    <View style={s.container}>
      <FlatList
        data={notes}
        keyExtractor={(n) => n.id}
        renderItem={({ item }) => (
          <NoteRow note={item} onPress={() => setSelected(item)} />
        )}
        contentContainerStyle={notes.length === 0 ? s.emptyContainer : { paddingVertical: 8 }}
        ItemSeparatorComponent={() => <View style={s.separator} />}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={
          <View style={s.emptyBox}>
            <Text style={s.emptyIcon}>📒</Text>
            <Text style={s.emptyText}>아직 레슨노트가 없습니다</Text>
            <Text style={s.emptySubText}>강사가 레슨노트를 남기면 여기에 표시됩니다</Text>
          </View>
        }
      />

      {selected && (
        <NoteDetail note={selected} onClose={() => setSelected(null)} />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  emptyContainer: { flex: 1 },
  emptyBox: { flex: 1, alignItems: "center", justifyContent: "center", paddingTop: 100, gap: 8 },
  emptyIcon: { fontSize: 44 },
  emptyText: { fontSize: 15, fontWeight: "600", color: "#374151" },
  emptySubText: { fontSize: 13, color: "#9ca3af", textAlign: "center", paddingHorizontal: 32 },
  separator: { height: 1, backgroundColor: "#f3f4f6", marginLeft: 16 },
  row: {
    flexDirection: "row", alignItems: "center",
    paddingHorizontal: 16, paddingVertical: 14, gap: 12,
    backgroundColor: "#fff",
  },
  thumb: { width: 52, height: 52, borderRadius: 8, backgroundColor: "#f3f4f6" },
  pdfThumb: { alignItems: "center", justifyContent: "center", backgroundColor: "#eff6ff" },
  pdfThumbText: { fontSize: 12, fontWeight: "700", color: "#2563eb" },
  rowBody: { flex: 1, gap: 4 },
  preview: { fontSize: 14, color: "#374151", lineHeight: 20 },
  noPreview: { fontSize: 14, color: "#9ca3af", fontStyle: "italic" },
  rowDate: { fontSize: 12, color: "#9ca3af" },
  chevron: { fontSize: 20, color: "#d1d5db", fontWeight: "300" },
});
