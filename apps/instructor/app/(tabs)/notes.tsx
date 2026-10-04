// 레슨노트 탭: 담당 고객에게 노트 작성 (앱에서 글 작성 또는 수기 노트 스캔 → PDF)
// 피드백 게시물을 여기로 통합 (2026-10-04). 고객은 고객 앱 레슨노트 탭에서 본다
import { useCallback, useEffect, useState } from "react";
import {
  View, Text, FlatList, Pressable, Modal, TextInput, ScrollView, ActivityIndicator, RefreshControl, StyleSheet, Platform, Linking,
} from "react-native";
import { useFocusEffect } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";
import * as Print from "expo-print";
import { apiFetch } from "@/lib/api";
import { appAlert } from "@/lib/alert";
import type { LessonNoteRead, UserRead, UsersListResponse } from "@/types/api";

type Attachment = { uri: string; name: string } | null;

function fmtDate(iso: string) {
  const d = new Date(iso);
  return `${d.getFullYear()}.${d.getMonth() + 1}.${d.getDate()}`;
}

// 사진 여러 장 → PDF 한 파일 (휴대폰에서만, 웹은 printToFileAsync 미지원)
async function photosToPdf(assets: ImagePicker.ImagePickerAsset[]): Promise<string> {
  const pages = assets
    .map(a => `<div style="page-break-after:always;text-align:center"><img src="data:image/jpeg;base64,${a.base64}" style="max-width:100%;max-height:100vh"/></div>`)
    .join("");
  const { uri } = await Print.printToFileAsync({ html: `<html><body style="margin:0">${pages}</body></html>` });
  return uri;
}

// 서명 주소로 S3 에 PDF 를 올리고 key 를 돌려준다
async function uploadPdf(att: NonNullable<Attachment>): Promise<string> {
  const { upload_url, key } = await apiFetch<{ upload_url: string; key: string }>("/lesson-notes/upload-url", {
    method: "POST", body: { filename: att.name, content_type: "application/pdf" },
  });
  let blob: Blob;
  try {
    blob = await (await fetch(att.uri)).blob();
  } catch {
    throw new Error("선택한 파일을 읽지 못했습니다.");
  }
  let res: Response;
  try {
    res = await fetch(upload_url, { method: "PUT", headers: { "Content-Type": "application/pdf" }, body: blob });
  } catch {
    throw new Error("PDF 를 파일 저장소(S3)에 올리지 못했습니다. 네트워크와 저장소 설정을 확인하세요.");
  }
  if (!res.ok) throw new Error(`PDF 업로드 실패 (${res.status})`);
  return key;
}

export default function LessonNotesScreen() {
  const [notes, setNotes] = useState<LessonNoteRead[]>([]);
  const [customers, setCustomers] = useState<UserRead[]>([]);
  const [filter, setFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [editing, setEditing] = useState<LessonNoteRead | "new" | null>(null);

  const load = useCallback(async () => {
    try {
      const [n, c] = await Promise.all([
        apiFetch<LessonNoteRead[]>("/lesson-notes"),
        apiFetch<UsersListResponse>("/users?limit=100"),
      ]);
      setNotes(n);
      setCustomers(c.items.filter(u => u.role === "CUSTOMER"));
    } catch (e) {
      console.error("레슨노트 로딩 실패:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const shown = filter ? notes.filter(n => n.customer_id === filter) : notes;

  if (loading) return <View style={s.center}><ActivityIndicator size="large" /></View>;

  return (
    <View style={s.container}>
      {/* 고객별 보기 */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.chips} contentContainerStyle={{ gap: 8, paddingHorizontal: 16 }}>
        <Pressable style={[s.chip, !filter && s.chipOn]} onPress={() => setFilter(null)}>
          <Text style={[s.chipTxt, !filter && s.chipTxtOn]}>전체</Text>
        </Pressable>
        {customers.map(c => (
          <Pressable key={c.id} style={[s.chip, filter === c.id && s.chipOn]} onPress={() => setFilter(c.id)}>
            <Text style={[s.chipTxt, filter === c.id && s.chipTxtOn]}>{c.display_name}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <FlatList
        data={shown}
        keyExtractor={n => n.id}
        contentContainerStyle={{ padding: 16, paddingBottom: 100, gap: 10 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={
          <View style={s.empty}>
            <Text style={s.emptyIcon}>📒</Text>
            <Text style={s.emptyTxt}>작성한 레슨노트가 없습니다</Text>
            <Text style={s.emptySub}>＋ 를 눌러 담당 고객에게 노트를 남겨 보세요</Text>
          </View>
        }
        renderItem={({ item }) => (
          <Pressable style={s.card} onPress={() => setEditing(item)}>
            <View style={s.cardTop}>
              <Text style={s.customer}>{item.customer_name ?? "고객"}</Text>
              <Text style={s.date}>{fmtDate(item.created_at)}</Text>
            </View>
            {item.title ? <Text style={s.title}>{item.title}</Text> : null}
            {item.content ? <Text style={s.content} numberOfLines={3}>{item.content}</Text> : null}
            <View style={s.badges}>
              {item.file_name ? <Text style={s.pdfBadge}>📄 {item.file_name}</Text> : null}
              {!item.is_shared ? <Text style={s.privateBadge}>고객 비공개</Text> : null}
            </View>
          </Pressable>
        )}
      />

      <Pressable style={s.fab} onPress={() => setEditing("new")}>
        <Text style={s.fabTxt}>＋</Text>
      </Pressable>

      <NoteForm
        target={editing}
        customers={customers}
        defaultCustomer={filter}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); load(); }}
      />
    </View>
  );
}

// ── 작성·수정 모달 ────────────────────────────────────────────
function NoteForm({
  target, customers, defaultCustomer, onClose, onSaved,
}: {
  target: LessonNoteRead | "new" | null;
  customers: UserRead[];
  defaultCustomer: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = target === "new";
  const note = target && target !== "new" ? target : null;
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [shared, setShared] = useState(true);
  const [attachment, setAttachment] = useState<Attachment>(null);
  const [removeFile, setRemoveFile] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!target) return;
    setCustomerId(note?.customer_id ?? defaultCustomer ?? null);
    setTitle(note?.title ?? "");
    setContent(note?.content ?? "");
    setShared(note?.is_shared ?? true);
    setAttachment(null);
    setRemoveFile(false);
  }, [target]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!target) return null;

  async function scanPhotos(fromCamera: boolean) {
    if (Platform.OS === "web") {
      appAlert("알림", "사진 스캔은 휴대폰 앱에서만 할 수 있습니다. 웹에서는 PDF 파일을 선택하세요.");
      return;
    }
    const perm = fromCamera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) { appAlert("권한 필요", fromCamera ? "카메라 권한이 필요합니다." : "사진 접근 권한이 필요합니다."); return; }
    const opts: ImagePicker.ImagePickerOptions = { mediaTypes: ["images"], base64: true, quality: 0.6, allowsMultipleSelection: !fromCamera };
    const res = fromCamera ? await ImagePicker.launchCameraAsync(opts) : await ImagePicker.launchImageLibraryAsync(opts);
    if (res.canceled || res.assets.length === 0) return;
    setBusy("PDF 만드는 중...");
    try {
      const uri = await photosToPdf(res.assets);
      setAttachment({ uri, name: `레슨노트_${new Date().toISOString().slice(0, 10)}.pdf` });
      setRemoveFile(false);
    } catch (e) {
      appAlert("오류", e instanceof Error ? e.message : "PDF 로 만들지 못했습니다.");
    } finally {
      setBusy(null);
    }
  }

  async function pickPdf() {
    const res = await DocumentPicker.getDocumentAsync({ type: "application/pdf", copyToCacheDirectory: true });
    if (res.canceled || !res.assets?.[0]) return;
    setAttachment({ uri: res.assets[0].uri, name: res.assets[0].name ?? "note.pdf" });
    setRemoveFile(false);
  }

  async function save() {
    if (isNew && !customerId) { appAlert("오류", "고객을 선택해주세요."); return; }
    const hasFile = !!attachment || (!!note?.file_name && !removeFile);
    if (!content.trim() && !hasFile) { appAlert("오류", "내용을 입력하거나 PDF 를 첨부해주세요."); return; }
    try {
      let file: { file_key?: string | null; file_name?: string | null } = {};
      if (attachment) {
        setBusy("PDF 올리는 중...");
        file = { file_key: await uploadPdf(attachment), file_name: attachment.name };
      } else if (removeFile) {
        file = { file_key: null, file_name: null };
      }
      setBusy("저장 중...");
      const body = { title: title.trim() || null, content: content.trim() || null, is_shared: shared, ...file };
      if (isNew) await apiFetch("/lesson-notes", { method: "POST", body: { customer_id: customerId, ...body } });
      else await apiFetch(`/lesson-notes/${note!.id}`, { method: "PATCH", body });
      onSaved();
    } catch (e) {
      appAlert("저장 실패", e instanceof Error ? e.message : "저장하지 못했습니다.");
    } finally {
      setBusy(null);
    }
  }

  function remove() {
    if (!note) return;
    appAlert("레슨노트 삭제", "이 노트를 삭제할까요?", [
      { text: "취소", style: "cancel" },
      {
        text: "삭제", style: "destructive", onPress: async () => {
          try { await apiFetch(`/lesson-notes/${note.id}`, { method: "DELETE" }); onSaved(); }
          catch (e) { appAlert("오류", e instanceof Error ? e.message : "삭제 실패"); }
        },
      },
    ]);
  }

  const existingFile = note?.file_name && !removeFile && !attachment ? note : null;

  return (
    <Modal visible animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={f.container}>
        <View style={f.header}>
          <Pressable onPress={onClose}><Text style={f.cancel}>취소</Text></Pressable>
          <Text style={f.headerTitle}>{isNew ? "레슨노트 작성" : "레슨노트"}</Text>
          <Pressable onPress={save} disabled={!!busy}><Text style={[f.save, !!busy && { opacity: 0.4 }]}>저장</Text></Pressable>
        </View>

        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
          <Text style={f.label}>고객</Text>
          {isNew ? (
            <View style={f.customerWrap}>
              {customers.length === 0 && <Text style={f.hint}>담당 고객이 없습니다.</Text>}
              {customers.map(c => (
                <Pressable key={c.id} style={[f.customerChip, customerId === c.id && f.customerChipOn]} onPress={() => setCustomerId(c.id)}>
                  <Text style={[f.customerTxt, customerId === c.id && f.customerTxtOn]}>{c.display_name}</Text>
                </Pressable>
              ))}
            </View>
          ) : (
            <Text style={f.fixedCustomer}>{note?.customer_name}</Text>
          )}

          <Text style={f.label}>제목 (선택)</Text>
          <TextInput value={title} onChangeText={setTitle} placeholder="예: 3회차 레슨" style={f.input} maxLength={200} />

          <Text style={f.label}>내용</Text>
          <TextInput value={content} onChangeText={setContent} placeholder="레슨 내용, 피드백, 다음 레슨 목표..." multiline style={[f.input, { height: 140, textAlignVertical: "top" }]} />

          <Text style={f.label}>수기 노트 (PDF)</Text>
          <View style={f.attachRow}>
            <Pressable style={f.attachBtn} onPress={() => scanPhotos(true)}><Text style={f.attachTxt}>📷 촬영해서 스캔</Text></Pressable>
            <Pressable style={f.attachBtn} onPress={() => scanPhotos(false)}><Text style={f.attachTxt}>🖼 사진으로 스캔</Text></Pressable>
            <Pressable style={f.attachBtn} onPress={pickPdf}><Text style={f.attachTxt}>📄 PDF 파일 선택</Text></Pressable>
          </View>
          {attachment && (
            <View style={f.fileRow}>
              <Text style={f.fileName} numberOfLines={1}>📄 {attachment.name} (새 파일)</Text>
              <Pressable onPress={() => setAttachment(null)}><Text style={f.fileRemove}>빼기</Text></Pressable>
            </View>
          )}
          {existingFile && (
            <View style={f.fileRow}>
              <Pressable style={{ flex: 1 }} onPress={() => existingFile.file_url && Linking.openURL(existingFile.file_url)}>
                <Text style={f.fileName} numberOfLines={1}>📄 {existingFile.file_name} (보기)</Text>
              </Pressable>
              <Pressable onPress={() => setRemoveFile(true)}><Text style={f.fileRemove}>삭제</Text></Pressable>
            </View>
          )}

          <Pressable style={f.shareRow} onPress={() => setShared(v => !v)}>
            <View style={[f.check, shared && f.checkOn]}>{shared && <Text style={f.checkMark}>✓</Text>}</View>
            <Text style={f.shareTxt}>고객에게 보여주기</Text>
          </Pressable>

          {busy && <View style={f.busy}><ActivityIndicator /><Text style={f.hint}>{busy}</Text></View>}

          {!isNew && (
            <Pressable style={f.deleteBtn} onPress={remove}><Text style={f.deleteTxt}>노트 삭제</Text></Pressable>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  chips: { flexGrow: 0, paddingVertical: 10, backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 16, backgroundColor: "#f3f4f6" },
  chipOn: { backgroundColor: "#16a34a" },
  chipTxt: { fontSize: 13, color: "#374151", fontWeight: "600" },
  chipTxtOn: { color: "#fff" },
  card: { backgroundColor: "#fff", borderRadius: 12, padding: 14, borderWidth: 1, borderColor: "#f3f4f6" },
  cardTop: { flexDirection: "row", justifyContent: "space-between", marginBottom: 6 },
  customer: { fontSize: 14, fontWeight: "700", color: "#16a34a" },
  date: { fontSize: 12, color: "#9ca3af" },
  title: { fontSize: 15, fontWeight: "700", color: "#111", marginBottom: 4 },
  content: { fontSize: 14, color: "#374151", lineHeight: 20 },
  badges: { flexDirection: "row", gap: 8, marginTop: 8, flexWrap: "wrap" },
  pdfBadge: { fontSize: 12, color: "#2563eb", backgroundColor: "#eff6ff", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  privateBadge: { fontSize: 12, color: "#6b7280", backgroundColor: "#f3f4f6", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  empty: { alignItems: "center", paddingTop: 80, gap: 6 },
  emptyIcon: { fontSize: 40 },
  emptyTxt: { fontSize: 15, fontWeight: "600", color: "#374151" },
  emptySub: { fontSize: 13, color: "#9ca3af" },
  fab: { position: "absolute", right: 20, bottom: 24, width: 56, height: 56, borderRadius: 28, backgroundColor: "#16a34a", alignItems: "center", justifyContent: "center", elevation: 4 },
  fabTxt: { color: "#fff", fontSize: 28, lineHeight: 30 },
});

const f = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16, backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  headerTitle: { fontSize: 16, fontWeight: "700" },
  cancel: { fontSize: 15, color: "#6b7280" },
  save: { fontSize: 15, color: "#16a34a", fontWeight: "700" },
  label: { fontSize: 13, fontWeight: "600", color: "#374151", marginTop: 16, marginBottom: 6 },
  hint: { fontSize: 13, color: "#9ca3af" },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 10, padding: 12, fontSize: 14 },
  customerWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  customerChip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 16, borderWidth: 1, borderColor: "#e5e7eb", backgroundColor: "#fff" },
  customerChipOn: { backgroundColor: "#16a34a", borderColor: "#16a34a" },
  customerTxt: { fontSize: 14, color: "#374151" },
  customerTxtOn: { color: "#fff", fontWeight: "700" },
  fixedCustomer: { fontSize: 15, fontWeight: "700", color: "#111" },
  attachRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  attachBtn: { paddingHorizontal: 12, paddingVertical: 9, borderRadius: 10, backgroundColor: "#fff", borderWidth: 1, borderColor: "#e5e7eb" },
  attachTxt: { fontSize: 13, color: "#111", fontWeight: "600" },
  fileRow: { flexDirection: "row", alignItems: "center", gap: 12, marginTop: 10, backgroundColor: "#eff6ff", borderRadius: 10, padding: 12 },
  fileName: { flex: 1, fontSize: 13, color: "#2563eb" },
  fileRemove: { fontSize: 13, color: "#dc2626", fontWeight: "600" },
  shareRow: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 20 },
  check: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, borderColor: "#d1d5db", alignItems: "center", justifyContent: "center" },
  checkOn: { backgroundColor: "#16a34a", borderColor: "#16a34a" },
  checkMark: { color: "#fff", fontSize: 14, fontWeight: "700" },
  shareTxt: { fontSize: 14, color: "#374151" },
  busy: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 16 },
  deleteBtn: { marginTop: 32, padding: 14, borderRadius: 10, borderWidth: 1, borderColor: "#fecaca", alignItems: "center" },
  deleteTxt: { color: "#dc2626", fontWeight: "600" },
});
