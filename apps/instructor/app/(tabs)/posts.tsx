import { useEffect, useState, useCallback, useRef } from "react";
import {
  View, Text, FlatList, Pressable, Alert, Modal,
  TextInput, StyleSheet, Image, ActivityIndicator,
  Dimensions, ScrollView, Platform,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useVideoPlayer, VideoView } from "expo-video";
import { apiFetch, ApiError } from "@/lib/api";
import type { PostRead, CommentRead, UserRead, UsersListResponse } from "@/types/api";

const SW = Dimensions.get("window").width;
const SH = Dimensions.get("window").height;
const CARD_W = SW - 32;
const MEDIA_W = Math.floor(CARD_W * 0.45);
const CARD_H = 240;
const LEFT_COL_W = Math.floor(SW * 0.48);
const GRID_COLS = 4;
const GRID_GAP = 3;
const GRID_ITEM_W = Math.floor((LEFT_COL_W - 16 - GRID_GAP * (GRID_COLS - 1)) / GRID_COLS);

interface LocalMedia { url: string; media_type: "IMAGE" | "VIDEO"; }
interface FormState { content: string; media_items: LocalMedia[]; customer_id: string; }

// ─── VideoItem ────────────────────────────────────────────────────────────────
function VideoItem({ uri, w, h, autoPlay }: { uri: string; w: number; h: number; autoPlay?: boolean }) {
  const player = useVideoPlayer(uri, (p) => { p.loop = false; if (autoPlay) p.play(); });
  return <VideoView player={player} style={{ width: w, height: h }} contentFit="cover" nativeControls />;
}

// ─── 풀스크린 미디어 뷰어 ────────────────────────────────────────────────────
function MediaViewer({ item, onClose }: { item: LocalMedia | null; onClose: () => void }) {
  if (!item) return null;
  return (
    <Modal visible animationType="fade" transparent statusBarTranslucent>
      <View style={mv.backdrop}>
        <Pressable style={mv.closeBtn} onPress={onClose}>
          <Text style={mv.closeText}>✕</Text>
        </Pressable>
        {item.media_type === "VIDEO"
          ? <VideoItem uri={item.url} w={SW} h={SH * 0.75} autoPlay />
          : <Image source={{ uri: item.url }} style={mv.img} resizeMode="contain" />
        }
      </View>
    </Modal>
  );
}

// ─── 고객 드롭다운 ────────────────────────────────────────────────────────────
function CustomerDropdown({ customers, selectedId, onSelect }: {
  customers: UserRead[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = customers.find((c) => c.id === selectedId);
  return (
    <View>
      <Pressable style={dd.trigger} onPress={() => setOpen(true)}>
        <Text style={[dd.triggerText, !selected && { color: "#9ca3af" }]}>
          {selected?.display_name ?? "고객 선택 ▼"}
        </Text>
        {selected && <Text style={dd.arrow}>▼</Text>}
      </Pressable>
      <Modal visible={open} transparent animationType="fade">
        <Pressable style={dd.backdrop} onPress={() => setOpen(false)}>
          <View style={dd.sheet}>
            <Text style={dd.sheetTitle}>고객 선택</Text>
            <ScrollView style={{ maxHeight: 320 }}>
              {customers.map((c) => (
                <Pressable
                  key={c.id}
                  style={[dd.item, c.id === selectedId && dd.itemSel]}
                  onPress={() => { onSelect(c.id); setOpen(false); }}
                >
                  <Text style={[dd.itemText, c.id === selectedId && dd.itemTextSel]}>
                    {c.display_name}
                  </Text>
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                    <Text style={c.feedback_consent ? dd.consentOn : dd.consentOff}>
                      {c.feedback_consent ? "공개" : "비공개"}
                    </Text>
                    {c.id === selectedId && <Text style={dd.check}>✓</Text>}
                  </View>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

// ─── 삭제 확인 모달 ──────────────────────────────────────────────────────────
function DeleteConfirmModal({ visible, onConfirm, onCancel }: {
  visible: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={del.backdrop}>
        <View style={del.box}>
          <Text style={del.title}>게시물 삭제</Text>
          <Text style={del.body}>정말 게시물을 삭제하시겠습니까?</Text>
          <View style={del.btnRow}>
            <Pressable onPress={onCancel} style={del.cancelBtn}><Text style={del.cancelText}>취소</Text></Pressable>
            <Pressable onPress={onConfirm} style={del.deleteBtn}><Text style={del.deleteText}>삭제</Text></Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

// ─── 댓글 섹션 ───────────────────────────────────────────────────────────────
function CommentsSection({ postId }: { postId: string }) {
  const [open, setOpen] = useState(false);
  const [comments, setComments] = useState<CommentRead[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);

  async function loadComments() {
    setLoading(true);
    try { setComments(await apiFetch<CommentRead[]>(`/instructor-posts/${postId}/comments`)); }
    catch { /* ignore */ } finally { setLoading(false); }
  }

  function toggle() { if (!open) loadComments(); setOpen((v) => !v); }

  async function send() {
    if (!input.trim()) return;
    setSending(true);
    try {
      const c = await apiFetch<CommentRead>(`/instructor-posts/${postId}/comments`, {
        method: "POST", body: { content: input.trim() },
      });
      setComments((p) => [...p, c]);
      setInput("");
    } catch { Alert.alert("오류", "댓글 등록 실패"); } finally { setSending(false); }
  }

  return (
    <View>
      <Pressable onPress={toggle} style={cm.btn}>
        <Text style={cm.btnText}>💬 댓글 {open ? "접기" : "보기"}</Text>
      </Pressable>
      {open && (
        <View style={cm.box}>
          {loading ? <ActivityIndicator size="small" color="#6b7280" />
            : comments.length === 0 ? <Text style={cm.empty}>댓글이 없습니다</Text>
            : comments.map((c) => (
              <View key={c.id} style={cm.row}>
                <Text style={cm.name}>{c.user_name ?? "알 수 없음"}</Text>
                <Text style={cm.content}>{c.content}</Text>
              </View>
            ))
          }
          <View style={cm.inputRow}>
            <TextInput value={input} onChangeText={setInput} placeholder="댓글 입력..." style={cm.input} placeholderTextColor="#9ca3af" />
            <Pressable onPress={send} disabled={sending} style={cm.sendBtn}>
              <Text style={cm.sendText}>{sending ? "..." : "전송"}</Text>
            </Pressable>
          </View>
        </View>
      )}
    </View>
  );
}

// ─── 게시물 카드 ─────────────────────────────────────────────────────────────
function PostCard({ post, onDelete, onEdit }: {
  post: PostRead; onDelete: (id: string) => void; onEdit: (post: PostRead) => void;
}) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [mediaIdx, setMediaIdx] = useState(0);
  const [viewerItem, setViewerItem] = useState<LocalMedia | null>(null);
  const isFeedback = post.type === "FEEDBACK";
  const media = post.media_items ?? [];
  const cur = media[mediaIdx];

  return (
    <View style={s.card}>
      <View style={s.cardInner}>
        {/* 왼쪽: 미디어 */}
        <View style={[s.mediaCol, !cur && s.mediaColEmpty]}>
          {cur ? (
            <>
              <Pressable onPress={() => setViewerItem({ url: cur.url, media_type: cur.media_type as "IMAGE" | "VIDEO" })}>
                {cur.media_type === "VIDEO"
                  ? <VideoItem uri={cur.url} w={MEDIA_W} h={CARD_H} />
                  : <Image source={{ uri: cur.url }} style={{ width: MEDIA_W, height: CARD_H }} resizeMode="cover" />
                }
              </Pressable>
              {media.length > 1 && (
                <View style={s.mediaNav}>
                  <Pressable onPress={() => setMediaIdx((i) => Math.max(0, i - 1))} style={s.navBtn} disabled={mediaIdx === 0}>
                    <Text style={[s.navText, mediaIdx === 0 && { opacity: 0.3 }]}>◀</Text>
                  </Pressable>
                  <Text style={s.navCount}>{mediaIdx + 1}/{media.length}</Text>
                  <Pressable onPress={() => setMediaIdx((i) => Math.min(media.length - 1, i + 1))} style={s.navBtn} disabled={mediaIdx === media.length - 1}>
                    <Text style={[s.navText, mediaIdx === media.length - 1 && { opacity: 0.3 }]}>▶</Text>
                  </Pressable>
                </View>
              )}
            </>
          ) : (
            <View style={s.noMediaBox}>
              <Text style={s.noMediaIcon}>{isFeedback ? "💬" : "📢"}</Text>
              <Text style={s.noMediaLabel}>텍스트</Text>
            </View>
          )}
        </View>

        {/* 오른쪽 */}
        <View style={s.infoCol}>
          <View style={s.badgeRow}>
            <View style={[s.badge, isFeedback ? s.badgeFeedback : s.badgePromo]}>
              <Text style={s.badgeText}>{isFeedback ? "피드백" : "프로모션"}</Text>
            </View>
            {post.is_public && <View style={s.badgePublic}><Text style={s.badgeText}>공개</Text></View>}
          </View>
          <Text style={s.postContent} numberOfLines={6}>{post.content ?? ""}</Text>
          {isFeedback && (
            <Text style={s.customerLabel}>👤 {post.customer_name ?? post.customer_id?.slice(0, 8) ?? "-"}</Text>
          )}
          <CommentsSection postId={post.id} />
          <View style={s.cardFooter}>
            <Text style={s.dateText}>{new Date(post.created_at).toLocaleDateString("ko-KR")}</Text>
            <View style={s.actionRow}>
              <Pressable onPress={() => onEdit(post)} style={s.editBtn}><Text style={s.editText}>수정</Text></Pressable>
              <Pressable onPress={() => setShowDeleteModal(true)} style={s.deleteBtn}><Text style={s.deleteText}>삭제</Text></Pressable>
            </View>
          </View>
        </View>
      </View>

      <DeleteConfirmModal
        visible={showDeleteModal}
        onConfirm={() => { setShowDeleteModal(false); onDelete(post.id); }}
        onCancel={() => setShowDeleteModal(false)}
      />
      <MediaViewer item={viewerItem} onClose={() => setViewerItem(null)} />
    </View>
  );
}

// ─── 게시물 폼 (top-level — 타이핑 버그 방지) ────────────────────────────────
interface PostFormProps {
  form: FormState;
  onChangeContent: (v: string) => void;
  onChangeCustomerId: (v: string) => void;
  onChangeMedia: (items: LocalMedia[]) => void;
  uploading: boolean;
  onUpload: () => void;
  postType: "PROMOTION" | "FEEDBACK" | null;
  isEditing: boolean;
  customers: UserRead[];
  onSubmit: () => void;
  onCancel: () => void;
  submitting: boolean;
}

function PostForm({
  form, onChangeContent, onChangeCustomerId, onChangeMedia,
  uploading, onUpload, postType, isEditing,
  customers, onSubmit, onCancel, submitting,
}: PostFormProps) {
  const [viewerItem, setViewerItem] = useState<LocalMedia | null>(null);

  function move(idx: number, dir: -1 | 1) {
    const next = [...form.media_items];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    onChangeMedia(next);
  }

  function remove(idx: number) {
    onChangeMedia(form.media_items.filter((_, i) => i !== idx));
  }

  // 4열 그리드
  const rows: LocalMedia[][] = [];
  for (let i = 0; i < form.media_items.length; i += GRID_COLS) {
    rows.push(form.media_items.slice(i, i + GRID_COLS));
  }

  return (
    <View style={fm.container}>
      {/* 왼쪽: 미디어 갤러리 */}
      <View style={fm.leftCol}>
        <ScrollView style={fm.grid} showsVerticalScrollIndicator={false}>
          {rows.length === 0 && (
            <View style={fm.emptyGrid}>
              <Text style={fm.emptyGridIcon}>🖼️</Text>
              <Text style={fm.emptyGridText}>미디어를 추가하세요</Text>
            </View>
          )}
          {rows.map((row, rowIdx) => (
            <View key={rowIdx} style={fm.gridRow}>
              {row.map((m, colIdx) => {
                const idx = rowIdx * GRID_COLS + colIdx;
                return (
                  <View key={idx} style={fm.gridCell}>
                    <Pressable onPress={() => setViewerItem(m)} style={{ flex: 1 }}>
                      {m.media_type === "VIDEO"
                        ? <VideoItem uri={m.url} w={GRID_ITEM_W} h={GRID_ITEM_W} />
                        : <Image source={{ uri: m.url }} style={{ width: GRID_ITEM_W, height: GRID_ITEM_W }} resizeMode="cover" />
                      }
                    </Pressable>
                    {/* ✕ 삭제 */}
                    <Pressable onPress={() => remove(idx)} style={fm.removeX}>
                      <Text style={fm.removeXText}>✕</Text>
                    </Pressable>
                    {/* ← → 순서 */}
                    <View style={fm.orderRow}>
                      <Pressable onPress={() => move(idx, -1)} disabled={idx === 0} style={fm.orderBtn}>
                        <Text style={[fm.orderText, idx === 0 && { opacity: 0.25 }]}>←</Text>
                      </Pressable>
                      <Pressable onPress={() => move(idx, 1)} disabled={idx === form.media_items.length - 1} style={fm.orderBtn}>
                        <Text style={[fm.orderText, idx === form.media_items.length - 1 && { opacity: 0.25 }]}>→</Text>
                      </Pressable>
                    </View>
                  </View>
                );
              })}
              {/* 부족한 셀 채우기 */}
              {Array.from({ length: GRID_COLS - row.length }).map((_, i) => (
                <View key={`empty-${i}`} style={[fm.gridCell, { backgroundColor: "transparent" }]} />
              ))}
            </View>
          ))}
        </ScrollView>

        {uploading ? (
          <View style={fm.uploadingRow}>
            <ActivityIndicator color="#16a34a" />
            <Text style={fm.uploadingText}>업로드 중...</Text>
          </View>
        ) : (
          <Pressable style={fm.addBtn} onPress={onUpload}>
            <Text style={fm.addBtnIcon}>＋</Text>
            <Text style={fm.addBtnText}>미디어 추가</Text>
          </Pressable>
        )}
      </View>

      {/* 오른쪽: 내용 + 고객 + 버튼 */}
      <View style={fm.rightCol}>
        <TextInput
          value={form.content}
          onChangeText={onChangeContent}
          placeholder="내용을 입력하세요..."
          style={fm.contentInput}
          multiline
          placeholderTextColor="#9ca3af"
          textAlignVertical="top"
        />

        {postType === "FEEDBACK" && !isEditing && (
          <View style={fm.customerSection}>
            <CustomerDropdown
              customers={customers}
              selectedId={form.customer_id}
              onSelect={onChangeCustomerId}
            />
          </View>
        )}

        <View style={fm.btnRow}>
          <Pressable
            onPress={onSubmit}
            disabled={submitting || uploading}
            style={[fm.confirmBtn, (submitting || uploading) && { opacity: 0.5 }]}
          >
            <Text style={fm.confirmText}>{submitting ? "..." : "확인"}</Text>
          </Pressable>
          <Pressable onPress={onCancel} style={fm.cancelBtn}>
            <Text style={fm.cancelBtnText}>취소</Text>
          </Pressable>
        </View>
      </View>

      <MediaViewer item={viewerItem} onClose={() => setViewerItem(null)} />
    </View>
  );
}

// ─── 메인 화면 ────────────────────────────────────────────────────────────────
export default function PostsScreen() {
  const [posts, setPosts] = useState<PostRead[]>([]);
  const [customers, setCustomers] = useState<UserRead[]>([]);
  const [createType, setCreateType] = useState<"PROMOTION" | "FEEDBACK" | "_select" | null>(null);
  const [editTarget, setEditTarget] = useState<PostRead | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<FormState>({ content: "", media_items: [], customer_id: "" });

  // refs — 항상 최신값 동기 접근 (stale closure 완전 방지)
  const formRef = useRef(form);
  const createTypeRef = useRef(createType);
  const editTargetRef = useRef(editTarget);
  const uploadedUrisRef = useRef(new Set<string>());

  const load = useCallback(async () => {
    try { setPosts(await apiFetch<PostRead[]>("/instructor-posts")); } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    load();
    apiFetch<UsersListResponse>("/users?role=CUSTOMER&limit=100")
      .then((r) => setCustomers(r.items ?? [])).catch(() => { });
  }, [load]);

  // ─── 미디어 업로드 (다중 선택 지원) ─────────────────────────────────────
  const uploadMedia = useCallback(async () => {
    if (Platform.OS !== "web") {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== "granted") {
        Alert.alert("권한 필요", "사진/동영상 라이브러리 접근 권한이 필요합니다.");
        return;
      }
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images", "videos"] as ImagePicker.MediaType[],
      quality: 0.85,
      videoMaxDuration: 60,
      allowsMultipleSelection: true,
    });
    if (result.canceled || !result.assets?.length) return;

    // 중복 제거
    const dupCount = result.assets.filter((a) => uploadedUrisRef.current.has(a.uri)).length;
    const toUpload = result.assets.filter((a) => !uploadedUrisRef.current.has(a.uri));

    if (toUpload.length === 0) {
      Alert.alert("중복 파일", "이미 추가된 파일입니다.");
      return;
    }
    if (dupCount > 0) {
      Alert.alert("알림", `중복 파일 ${dupCount}개는 건너뜁니다.`);
    }

    // 파일 크기 클라이언트 검증 (이미지 10MB, 영상 100MB)
    const MAX_IMAGE = 10 * 1024 * 1024;
    const MAX_VIDEO = 100 * 1024 * 1024;
    for (const asset of toUpload) {
      const isVideo =
        asset.type === "video" ||
        (asset.mimeType ?? "").startsWith("video/") ||
        (asset.fileName ?? "").match(/\.(mp4|mov|avi|mkv)$/i) !== null;
      const limit = isVideo ? MAX_VIDEO : MAX_IMAGE;
      const label = isVideo ? "100MB" : "10MB";
      if (asset.fileSize && asset.fileSize > limit) {
        Alert.alert("파일 크기 초과", `${asset.fileName ?? "파일"} 크기가 ${label}를 초과합니다.`);
        return;
      }
    }

    try {
      setUploading(true);
      for (const asset of toUpload) {
        const isVideo =
          asset.type === "video" ||
          (asset.mimeType ?? "").startsWith("video/") ||
          (asset.fileName ?? "").match(/\.(mp4|mov|avi|mkv)$/i) !== null;
        const mediaType: "IMAGE" | "VIDEO" = isVideo ? "VIDEO" : "IMAGE";
        const fileName = asset.fileName ?? `upload.${isVideo ? "mp4" : "jpg"}`;
        const contentType = asset.mimeType ?? (isVideo ? "video/mp4" : "image/jpeg");

        // 1. 서버에서 presigned POST URL + fields 발급
        const { upload_url, fields, public_url } = await apiFetch<{
          upload_url: string;
          fields: Record<string, string>;
          key: string;
          public_url: string;
        }>("/instructor-posts/upload-url", {
          method: "POST",
          body: { filename: fileName, content_type: contentType },
        });

        // 2. S3에 직접 multipart POST (서버 경유 없음)
        const formData = new FormData();
        for (const [k, v] of Object.entries(fields)) {
          formData.append(k, v);
        }
        formData.append("file", { uri: asset.uri, type: contentType, name: fileName } as unknown as Blob);

        const res = await fetch(upload_url, { method: "POST", body: formData });
        // S3 presigned POST 성공 응답은 204 No Content
        if (res.status !== 204 && !res.ok) throw new Error(`S3 업로드 실패 (${res.status})`);

        uploadedUrisRef.current.add(asset.uri);
        setForm((f) => {
          const next = { ...f, media_items: [...f.media_items, { url: public_url, media_type: mediaType }] };
          formRef.current = next;
          return next;
        });
      }
    } catch (e: unknown) {
      Alert.alert("업로드 오류", e instanceof Error ? e.message : "업로드에 실패했습니다.");
    } finally { setUploading(false); }
  }, []);

  // ─── 등록 ─────────────────────────────────────────────────────────────────
  function openCreate(type: "PROMOTION" | "FEEDBACK") {
    const blank: FormState = { content: "", media_items: [], customer_id: "" };
    createTypeRef.current = type;   // 즉시 동기화
    formRef.current = blank;
    setCreateType(type);
    setForm(blank);
    uploadedUrisRef.current.clear();
  }

  // stable — refs로 최신값 접근
  const submitCreate = useCallback(async () => {
    const f = formRef.current;
    const ct = createTypeRef.current;
    if (!f.content && f.media_items.length === 0) {
      Alert.alert("오류", "내용을 입력하거나 미디어를 추가해주세요."); return;
    }
    if (ct === "FEEDBACK" && !f.customer_id) {
      Alert.alert("오류", "피드백 대상 고객을 선택해주세요."); return;
    }
    try {
      setSubmitting(true);
      await apiFetch("/instructor-posts", {
        method: "POST",
        body: {
          type: ct,
          content: f.content || null,
          media_items: f.media_items.map((m, i) => ({ url: m.url, media_type: m.media_type, sort_order: i })),
          customer_id: ct === "FEEDBACK" ? f.customer_id : undefined,
        },
      });
      setCreateType(null);
      await load();
    } catch (e: unknown) {
      let msg = "등록 실패";
      if (e instanceof ApiError) {
        msg = `HTTP ${e.status}`;
        if (e.body) msg += "\n" + JSON.stringify(e.body).slice(0, 400);
      } else if (e instanceof Error) {
        msg = e.message;
      }
      console.error("[submitCreate]", e);
      Alert.alert("등록 오류", msg);
    } finally { setSubmitting(false); }
  }, [load]);

  // ─── 수정 ─────────────────────────────────────────────────────────────────
  function openEdit(post: PostRead) {
    const newForm: FormState = {
      content: post.content ?? "",
      media_items: (post.media_items ?? []).map((m) => ({
        url: m.url,
        media_type: m.media_type as "IMAGE" | "VIDEO",
      })),
      customer_id: post.customer_id ?? "",
    };
    editTargetRef.current = post;  // 즉시 동기화
    formRef.current = newForm;
    setEditTarget(post);
    setForm(newForm);
    uploadedUrisRef.current.clear();
  }

  // stable — refs로 최신값 접근
  const submitEdit = useCallback(async () => {
    const et = editTargetRef.current;
    const f = formRef.current;
    if (!et) return;
    try {
      setSubmitting(true);
      await apiFetch(`/instructor-posts/${et.id}`, {
        method: "PATCH",
        body: {
          content: f.content || null,
          media_items: f.media_items.map((m, i) => ({
            url: m.url, media_type: m.media_type, sort_order: i,
          })),
        },
      });
      setEditTarget(null);
      await load();
    } catch (e: unknown) {
      let msg = "수정 실패";
      if (e instanceof ApiError) {
        msg = `HTTP ${e.status}`;
        if (e.body) msg += "\n" + JSON.stringify(e.body).slice(0, 400);
      } else if (e instanceof Error) {
        msg = e.message;
      }
      console.error("[submitEdit]", e);
      Alert.alert("수정 오류", msg);
    } finally { setSubmitting(false); }
  }, [load]);

  async function deletePost(id: string) {
    try { await apiFetch(`/instructor-posts/${id}`, { method: "DELETE" }); await load(); }
    catch { Alert.alert("오류", "삭제 실패"); }
  }

  // stable 콜백 — setForm 안에서 ref도 동기 업데이트
  const handleChangeContent = useCallback((v: string) => setForm((f) => {
    const next = { ...f, content: v };
    formRef.current = next;
    return next;
  }), []);
  const handleChangeCustomerId = useCallback((v: string) => setForm((f) => {
    const next = { ...f, customer_id: v };
    formRef.current = next;
    return next;
  }), []);
  const handleChangeMedia = useCallback((items: LocalMedia[]) => setForm((f) => {
    const next = { ...f, media_items: items };
    formRef.current = next;
    return next;
  }), []);

  const isEditing = editTarget !== null;
  const postType = isEditing
    ? (editTarget?.type as "PROMOTION" | "FEEDBACK")
    : (createType as "PROMOTION" | "FEEDBACK" | null);
  const showForm = (createType !== null && createType !== "_select") || isEditing;

  return (
    <View style={s.container}>
      <FlatList
        data={posts}
        keyExtractor={(p) => p.id}
        renderItem={({ item }) => <PostCard post={item} onDelete={deletePost} onEdit={openEdit} />}
        contentContainerStyle={posts.length === 0 ? s.emptyContainer : { paddingBottom: 100 }}
        ListEmptyComponent={
          <View style={s.emptyBox}>
            <Text style={s.emptyIcon}>📭</Text>
            <Text style={s.emptyText}>등록된 게시물이 없습니다</Text>
          </View>
        }
      />

      <Pressable style={s.fab} onPress={() => setCreateType("_select")}>
        <Text style={s.fabText}>＋</Text>
      </Pressable>

      {/* 타입 선택 시트 */}
      <Modal visible={createType === "_select"} transparent animationType="fade">
        <Pressable style={s.backdrop} onPress={() => setCreateType(null)}>
          <Pressable style={s.typeSheet} onPress={() => {}}>
            <Text style={s.typeSheetTitle}>어떤 게시물을 올리시겠어요?</Text>
            <View style={s.typeCards}>
              {([
                { key: "PROMOTION", icon: "📢", label: "프로모션", sub: "홍보·소식" },
                { key: "FEEDBACK", icon: "💬", label: "피드백", sub: "고객 피드백" },
              ] as { key: "PROMOTION" | "FEEDBACK"; icon: string; label: string; sub: string }[]).map((t) => (
                <Pressable key={t.key} style={s.typeCard} onPress={() => openCreate(t.key)}>
                  <Text style={s.typeCardIcon}>{t.icon}</Text>
                  <Text style={s.typeCardLabel}>{t.label}</Text>
                  <Text style={s.typeCardSub}>{t.sub}</Text>
                </Pressable>
              ))}
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      {/* 등록/수정 모달 */}
      <Modal visible={showForm} animationType="slide" presentationStyle="pageSheet">
        <View style={s.modal}>
          <View style={s.modalHeader}>
            <Text style={s.modalTitle}>
              {isEditing ? "게시물 수정" : postType === "PROMOTION" ? "📢 프로모션" : "💬 피드백"}
            </Text>
          </View>
          <PostForm
            form={form}
            onChangeContent={handleChangeContent}
            onChangeCustomerId={handleChangeCustomerId}
            onChangeMedia={handleChangeMedia}
            uploading={uploading}
            onUpload={uploadMedia}
            postType={postType}
            isEditing={isEditing}
            customers={customers}
            onSubmit={isEditing ? submitEdit : submitCreate}
            onCancel={() => { setCreateType(null); setEditTarget(null); }}
            submitting={submitting}
          />
        </View>
      </Modal>
    </View>
  );
}

// ─── 풀스크린 뷰어 스타일 ────────────────────────────────────────────────────
const mv = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.95)", justifyContent: "center", alignItems: "center" },
  closeBtn: { position: "absolute", top: 52, right: 20, zIndex: 10, width: 36, height: 36, borderRadius: 18, backgroundColor: "rgba(255,255,255,0.2)", alignItems: "center", justifyContent: "center" },
  closeText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  img: { width: SW, height: SH * 0.8 },
});

// ─── 드롭다운 스타일 ─────────────────────────────────────────────────────────
const dd = StyleSheet.create({
  trigger: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderWidth: 1, borderColor: "#d1d5db", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, backgroundColor: "#fff" },
  triggerText: { fontSize: 14, color: "#111827", flex: 1 },
  arrow: { fontSize: 11, color: "#9ca3af" },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", alignItems: "center" },
  sheet: { backgroundColor: "#fff", borderRadius: 14, width: SW * 0.75, maxHeight: 400, overflow: "hidden" },
  sheetTitle: { fontSize: 15, fontWeight: "700", color: "#111827", padding: 16, borderBottomWidth: 1, borderColor: "#f3f4f6" },
  item: { flexDirection: "row", alignItems: "center", paddingVertical: 13, paddingHorizontal: 16, borderBottomWidth: 1, borderColor: "#f9fafb" },
  itemSel: { backgroundColor: "#f0fdf4" },
  itemText: { fontSize: 14, color: "#374151", flex: 1 },
  itemTextSel: { color: "#16a34a", fontWeight: "600" },
  check: { fontSize: 14, color: "#16a34a", fontWeight: "700" },
  consentOn: { fontSize: 11, color: "#16a34a", fontWeight: "600", backgroundColor: "#f0fdf4", paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, overflow: "hidden" },
  consentOff: { fontSize: 11, color: "#9ca3af", fontWeight: "500", backgroundColor: "#f3f4f6", paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, overflow: "hidden" },
});

// ─── 삭제 확인 스타일 ─────────────────────────────────────────────────────────
const del = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "center", alignItems: "center" },
  box: { backgroundColor: "#fff", borderRadius: 14, padding: 24, width: 280, gap: 8 },
  title: { fontSize: 16, fontWeight: "700", color: "#111827" },
  body: { fontSize: 14, color: "#6b7280", lineHeight: 20 },
  btnRow: { flexDirection: "row", gap: 10, marginTop: 8 },
  cancelBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: "#e5e7eb", alignItems: "center" },
  cancelText: { fontSize: 14, color: "#374151" },
  deleteBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, backgroundColor: "#ef4444", alignItems: "center" },
  deleteText: { fontSize: 14, color: "#fff", fontWeight: "700" },
});

// ─── 댓글 스타일 ─────────────────────────────────────────────────────────────
const cm = StyleSheet.create({
  btn: { paddingVertical: 4, marginTop: 4 },
  btnText: { fontSize: 12, color: "#6b7280" },
  box: { marginTop: 6, gap: 4 },
  empty: { fontSize: 12, color: "#9ca3af", fontStyle: "italic" },
  row: { backgroundColor: "#f9fafb", borderRadius: 6, padding: 6 },
  name: { fontSize: 11, fontWeight: "700", color: "#374151", marginBottom: 2 },
  content: { fontSize: 12, color: "#374151" },
  inputRow: { flexDirection: "row", gap: 6, marginTop: 4 },
  input: { flex: 1, borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 6, paddingHorizontal: 8, paddingVertical: 5, fontSize: 12 },
  sendBtn: { backgroundColor: "#16a34a", borderRadius: 6, paddingHorizontal: 10, justifyContent: "center" },
  sendText: { color: "#fff", fontSize: 12, fontWeight: "600" },
});

// ─── 폼 스타일 ───────────────────────────────────────────────────────────────
const fm = StyleSheet.create({
  container: { flex: 1, flexDirection: "row" },
  leftCol: { width: LEFT_COL_W, borderRightWidth: 1, borderColor: "#e5e7eb", padding: 8 },
  grid: { flex: 1 },
  gridRow: { flexDirection: "row", gap: GRID_GAP, marginBottom: GRID_GAP },
  gridCell: { width: GRID_ITEM_W, height: GRID_ITEM_W, borderRadius: 6, overflow: "hidden", backgroundColor: "#e5e7eb", position: "relative" },
  removeX: { position: "absolute", top: 4, right: 4, width: 22, height: 22, borderRadius: 11, backgroundColor: "rgba(0,0,0,0.65)", alignItems: "center", justifyContent: "center", zIndex: 10 },
  removeXText: { color: "#fff", fontSize: 10, fontWeight: "700" },
  orderRow: { position: "absolute", bottom: 4, left: 0, right: 0, flexDirection: "row", justifyContent: "center", gap: 4, zIndex: 10 },
  orderBtn: { backgroundColor: "rgba(0,0,0,0.55)", borderRadius: 4, paddingHorizontal: 7, paddingVertical: 2 },
  orderText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  emptyGrid: { alignItems: "center", justifyContent: "center", paddingVertical: 32, gap: 6 },
  emptyGridIcon: { fontSize: 30 },
  emptyGridText: { fontSize: 12, color: "#9ca3af" },
  uploadingRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: 12 },
  uploadingText: { color: "#16a34a", fontSize: 12 },
  addBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4, paddingVertical: 11, borderRadius: 8, borderWidth: 1.5, borderColor: "#d1d5db", borderStyle: "dashed", marginTop: 6 },
  addBtnIcon: { fontSize: 17, color: "#6b7280", fontWeight: "700" },
  addBtnText: { fontSize: 13, color: "#6b7280" },
  rightCol: { flex: 1, padding: 10, justifyContent: "space-between" },
  contentInput: { flex: 1, fontSize: 14, color: "#111827", textAlignVertical: "top", paddingTop: 4, lineHeight: 20 },
  customerSection: { paddingTop: 8, borderTopWidth: 1, borderColor: "#f3f4f6" },
  btnRow: { flexDirection: "row", gap: 8, paddingTop: 10, borderTopWidth: 1, borderColor: "#f3f4f6" },
  confirmBtn: { flex: 1, paddingVertical: 11, borderRadius: 8, backgroundColor: "#16a34a", alignItems: "center" },
  confirmText: { color: "#fff", fontSize: 14, fontWeight: "700" },
  cancelBtn: { flex: 1, paddingVertical: 11, borderRadius: 8, borderWidth: 1, borderColor: "#e5e7eb", alignItems: "center" },
  cancelBtnText: { fontSize: 14, color: "#374151" },
});

// ─── 메인 스타일 ─────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f3f4f6" },
  card: { marginHorizontal: 16, marginTop: 12, backgroundColor: "#fff", borderRadius: 14, overflow: "hidden", elevation: 2 },
  cardInner: { flexDirection: "row", minHeight: CARD_H },
  mediaCol: { width: MEDIA_W, backgroundColor: "#1a1a1a", position: "relative" },
  mediaColEmpty: { backgroundColor: "#f9fafb", alignItems: "center", justifyContent: "center" },
  mediaNav: { position: "absolute", bottom: 0, left: 0, right: 0, flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: "rgba(0,0,0,0.45)", paddingHorizontal: 6, paddingVertical: 4 },
  navBtn: { padding: 4 },
  navText: { color: "#fff", fontSize: 13 },
  navCount: { color: "#fff", fontSize: 11 },
  noMediaBox: { alignItems: "center", gap: 6 },
  noMediaIcon: { fontSize: 32 },
  noMediaLabel: { fontSize: 12, color: "#9ca3af" },
  infoCol: { flex: 1, padding: 12, justifyContent: "space-between" },
  badgeRow: { flexDirection: "row", gap: 6, marginBottom: 6 },
  badge: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: 20 },
  badgePromo: { backgroundColor: "#dbeafe" },
  badgeFeedback: { backgroundColor: "#fef3c7" },
  badgePublic: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: 20, backgroundColor: "#dcfce7" },
  badgeText: { fontSize: 10, fontWeight: "700", color: "#374151" },
  postContent: { fontSize: 12, color: "#6b7280", lineHeight: 17, flex: 1 },
  customerLabel: { fontSize: 12, color: "#374151", marginTop: 4 },
  cardFooter: { marginTop: 6 },
  dateText: { fontSize: 11, color: "#9ca3af", marginBottom: 4 },
  actionRow: { flexDirection: "row", gap: 6 },
  editBtn: { flex: 1, paddingVertical: 6, borderRadius: 6, borderWidth: 1, borderColor: "#e5e7eb", alignItems: "center" },
  editText: { fontSize: 12, color: "#374151" },
  deleteBtn: { flex: 1, paddingVertical: 6, borderRadius: 6, backgroundColor: "#fef2f2", alignItems: "center" },
  deleteText: { fontSize: 12, color: "#ef4444", fontWeight: "600" },
  emptyContainer: { flex: 1 },
  emptyBox: { paddingTop: 100, alignItems: "center", gap: 10 },
  emptyIcon: { fontSize: 40 },
  emptyText: { fontSize: 15, color: "#9ca3af" },
  fab: { position: "absolute", bottom: 28, right: 20, width: 52, height: 52, borderRadius: 26, backgroundColor: "#16a34a", alignItems: "center", justifyContent: "center", elevation: 6 },
  fabText: { fontSize: 26, color: "#fff", lineHeight: 30 },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "flex-end" },
  typeSheet: { backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  typeSheetTitle: { fontSize: 17, fontWeight: "700", textAlign: "center", marginBottom: 20 },
  typeCards: { flexDirection: "row", gap: 12 },
  typeCard: { flex: 1, alignItems: "center", padding: 16, borderRadius: 12, borderWidth: 1, borderColor: "#e5e7eb", gap: 4 },
  typeCardIcon: { fontSize: 28 },
  typeCardLabel: { fontSize: 14, fontWeight: "700", color: "#111827" },
  typeCardSub: { fontSize: 11, color: "#9ca3af", textAlign: "center" },
  modal: { flex: 1, backgroundColor: "#fff" },
  modalHeader: { paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderColor: "#e5e7eb" },
  modalTitle: { fontSize: 16, fontWeight: "700", textAlign: "center" },
});
