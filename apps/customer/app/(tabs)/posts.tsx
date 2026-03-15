// app/(tabs)/posts.tsx
import { useCallback, useRef, useState } from "react";
import {
  View, Text, FlatList, StyleSheet, ActivityIndicator,
  RefreshControl, Image, Dimensions, Pressable, TextInput, Platform,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { useVideoPlayer, VideoView } from "expo-video";
import { apiFetch } from "@/lib/api";
import type { InstructorPostRead, CommentRead, MediaItemRead } from "@/types/api";

const SW = Dimensions.get("window").width;
const MEDIA_W = SW - 32;
const MEDIA_H = Math.round(MEDIA_W * 0.6);

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "방금";
  if (mins < 60) return `${mins}분 전`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}시간 전`;
  return `${Math.floor(hrs / 24)}일 전`;
}

// ─── 비디오 아이템 ────────────────────────────────────────
function VideoItem({ uri }: { uri: string }) {
  const player = useVideoPlayer(uri, (p) => { p.loop = false; });
  return (
    <VideoView
      player={player}
      style={{ width: MEDIA_W, height: MEDIA_H }}
      contentFit="cover"
      nativeControls
    />
  );
}

// ─── 미디어 캐러셀 ────────────────────────────────────────
function MediaCarousel({ items }: { items: MediaItemRead[] }) {
  const [page, setPage] = useState(0);
  const listRef = useRef<FlatList>(null);
  if (items.length === 0) return null;

  function goTo(idx: number) {
    const next = Math.max(0, Math.min(idx, items.length - 1));
    listRef.current?.scrollToIndex({ index: next, animated: true });
    setPage(next);
  }

  return (
    <View style={mc.wrap}>
      <View style={{ borderRadius: 8, overflow: "hidden" }}>
        <FlatList
          ref={listRef}
          data={items}
          keyExtractor={item => String(item.id)}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          snapToInterval={MEDIA_W}
          decelerationRate="fast"
          onMomentumScrollEnd={e => {
            const idx = Math.round(e.nativeEvent.contentOffset.x / MEDIA_W);
            setPage(idx);
          }}
          getItemLayout={(_, index) => ({ length: MEDIA_W, offset: MEDIA_W * index, index })}
          renderItem={({ item }) =>
            item.media_type === "VIDEO" ? (
              <VideoItem uri={item.url} />
            ) : (
              <Image
                source={{ uri: item.url }}
                style={{ width: MEDIA_W, height: MEDIA_H }}
                resizeMode="cover"
              />
            )
          }
        />
        {/* 웹/터치 모두를 위한 화살표 버튼 */}
        {items.length > 1 && (
          <>
            {page > 0 && (
              <Pressable style={[mc.arrow, mc.arrowLeft]} onPress={() => goTo(page - 1)}>
                <Text style={mc.arrowTxt}>‹</Text>
              </Pressable>
            )}
            {page < items.length - 1 && (
              <Pressable style={[mc.arrow, mc.arrowRight]} onPress={() => goTo(page + 1)}>
                <Text style={mc.arrowTxt}>›</Text>
              </Pressable>
            )}
          </>
        )}
      </View>
      {items.length > 1 && (
        <View style={mc.dots}>
          {items.map((_, i) => (
            <View key={i} style={[mc.dot, i === page && mc.dotActive]} />
          ))}
        </View>
      )}
    </View>
  );
}

const mc = StyleSheet.create({
  wrap: { marginBottom: 4 },
  arrow: {
    position: "absolute", top: 0, bottom: 0,
    width: 36, justifyContent: "center", alignItems: "center",
    backgroundColor: "rgba(0,0,0,0.28)",
  },
  arrowLeft: { left: 0 },
  arrowRight: { right: 0 },
  arrowTxt: { color: "#fff", fontSize: 24, fontWeight: "700", lineHeight: 28 },
  dots: { flexDirection: "row", justifyContent: "center", marginTop: 8, gap: 5 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: "#d1d5db" },
  dotActive: { backgroundColor: "#1a1a1a" },
});

// ─── 댓글 섹션 ────────────────────────────────────────────
function CommentsSection({ postId }: { postId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [comments, setComments] = useState<CommentRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [newText, setNewText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const loaded = useRef(false);

  async function loadComments() {
    if (loading) return;
    setLoading(true);
    try {
      const data = await apiFetch<CommentRead[]>(`/instructor-posts/${postId}/comments`);
      setComments(Array.isArray(data) ? data : []);
      loaded.current = true;
    } catch (e) {
      console.error("댓글 로딩 실패:", e);
    } finally {
      setLoading(false);
    }
  }

  function toggle() {
    if (!expanded && !loaded.current) loadComments();
    setExpanded(v => !v);
  }

  async function submitComment() {
    if (!newText.trim() || submitting) return;
    setSubmitting(true);
    try {
      const c = await apiFetch<CommentRead>(`/instructor-posts/${postId}/comments`, {
        method: "POST",
        body: { content: newText.trim() },
      });
      setComments(prev => [...prev, c]);
      setNewText("");
    } catch (e) {
      console.error("댓글 등록 실패:", e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={cs.wrap}>
      <Pressable style={cs.toggleBtn} onPress={toggle}>
        <Text style={cs.toggleTxt}>
          {expanded ? "댓글 닫기" : `댓글 보기${comments.length > 0 ? ` (${comments.length})` : ""}`}
        </Text>
      </Pressable>

      {expanded && (
        <View style={cs.body}>
          {loading ? (
            <ActivityIndicator size="small" style={{ marginVertical: 8 }} />
          ) : comments.length === 0 ? (
            <Text style={cs.empty}>댓글이 없습니다</Text>
          ) : (
            comments.map(c => (
              <View key={c.id} style={cs.commentRow}>
                <Text style={cs.name}>{c.user_name ?? "사용자"}</Text>
                <Text style={cs.content}>{c.content}</Text>
              </View>
            ))
          )}

          <View style={cs.inputRow}>
            <TextInput
              value={newText}
              onChangeText={setNewText}
              placeholder="댓글 달기..."
              style={cs.input}
              returnKeyType="send"
              onSubmitEditing={submitComment}
            />
            <Pressable
              onPress={submitComment}
              disabled={submitting || !newText.trim()}
              style={[cs.sendBtn, (!newText.trim() || submitting) && { opacity: 0.4 }]}
            >
              <Text style={cs.sendTxt}>등록</Text>
            </Pressable>
          </View>
        </View>
      )}
    </View>
  );
}

const cs = StyleSheet.create({
  wrap: { marginTop: 8, borderTopWidth: 1, borderTopColor: "#f3f4f6", paddingTop: 8 },
  toggleBtn: { alignSelf: "flex-start" },
  toggleTxt: { fontSize: 12, color: "#6b7280", fontWeight: "600" },
  body: { marginTop: 8 },
  empty: { fontSize: 13, color: "#9ca3af", textAlign: "center", paddingVertical: 8 },
  commentRow: { paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: "#f9fafb" },
  name: { fontSize: 12, fontWeight: "700", color: "#374151", marginBottom: 2 },
  content: { fontSize: 13, color: "#374151" },
  inputRow: { flexDirection: "row", alignItems: "center", marginTop: 8, gap: 8 },
  input: {
    flex: 1, borderWidth: 1, borderColor: "#e5e7eb",
    borderRadius: 20, paddingHorizontal: 12, paddingVertical: 7,
    fontSize: 13, backgroundColor: "#f9fafb",
  },
  sendBtn: { paddingHorizontal: 12, paddingVertical: 7, backgroundColor: "#1a1a1a", borderRadius: 20 },
  sendTxt: { color: "#fff", fontSize: 12, fontWeight: "700" },
});

// ─── 포스트 카드 ──────────────────────────────────────────
function PostCard({ post }: { post: InstructorPostRead }) {
  const isFeedback = post.type === "FEEDBACK";

  return (
    <View style={s.card}>
      {/* 헤더 */}
      <View style={s.cardHeader}>
        <View style={[s.typeBadge, isFeedback ? s.feedbackBadge : s.promoBadge]}>
          <Text style={[s.typeBadgeText, isFeedback ? s.feedbackText : s.promoText]}>
            {isFeedback ? "피드백" : "홍보"}
          </Text>
        </View>
        {isFeedback && post.customer_name && (
          <Text style={s.customerName}>{post.customer_name}</Text>
        )}
        <Text style={s.timeAgo}>{timeAgo(post.created_at)}</Text>
      </View>

      {/* 본문 */}
      {post.content ? <Text style={s.content}>{post.content}</Text> : null}

      {/* 미디어 캐러셀 */}
      {post.media_items.length > 0 && (
        <MediaCarousel items={post.media_items} />
      )}

      {/* 댓글 */}
      <CommentsSection postId={post.id} />
    </View>
  );
}

// ─── 메인 화면 ────────────────────────────────────────────
export default function PostsScreen() {
  const [posts, setPosts] = useState<InstructorPostRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const initialLoaded = useRef(false);

  async function load() {
    try {
      const data = await apiFetch<InstructorPostRead[]>("/instructor-posts");
      setPosts(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("게시물 로딩 실패:", e);
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

  if (loading) {
    return <View style={s.center}><ActivityIndicator size="large" /></View>;
  }

  return (
    <FlatList
      data={posts}
      keyExtractor={p => p.id}
      renderItem={({ item }) => <PostCard post={item} />}
      contentContainerStyle={posts.length === 0 ? s.emptyContainer : { paddingVertical: 12 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
      ListEmptyComponent={
        <View style={s.emptyBox}>
          <Text style={s.emptyText}>게시물이 없습니다</Text>
          <Text style={s.emptySubText}>강사가 게시물을 올리면 여기에 표시됩니다</Text>
        </View>
      }
    />
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  emptyContainer: { flex: 1 },
  emptyBox: { flex: 1, alignItems: "center", justifyContent: "center", paddingTop: 80 },
  emptyText: { fontSize: 15, fontWeight: "600", color: "#374151", marginBottom: 6 },
  emptySubText: { fontSize: 13, color: "#9ca3af" },
  card: {
    marginHorizontal: 16, marginBottom: 12,
    backgroundColor: "#fff", borderRadius: 14,
    padding: 14, elevation: 2,
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.07, shadowRadius: 4,
  },
  cardHeader: { flexDirection: "row", alignItems: "center", marginBottom: 10, gap: 6 },
  typeBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  promoBadge: { backgroundColor: "#eff6ff" },
  feedbackBadge: { backgroundColor: "#f0fdf4" },
  typeBadgeText: { fontSize: 11, fontWeight: "700" },
  promoText: { color: "#2563eb" },
  feedbackText: { color: "#16a34a" },
  customerName: { fontSize: 13, fontWeight: "600", color: "#374151", flex: 1 },
  timeAgo: { fontSize: 12, color: "#9ca3af", marginLeft: "auto" },
  content: { fontSize: 14, color: "#374151", lineHeight: 20, marginBottom: 10 },
});
