// app/(tabs)/bookings.tsx — 게시물 피드 (Instagram 스타일)
import { useState, useCallback, useRef } from "react";
import {
  View, Text, ScrollView, Pressable, ActivityIndicator,
  RefreshControl, StyleSheet, Image, TextInput,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { PostResponse, CommentRead } from "@/types/api";

const POST_TYPE_LABEL: Record<string, string> = {
  NOTICE: "공지", COMMUNITY: "커뮤니티", FEEDBACK: "피드백",
};
const TYPE_COLOR: Record<string, string> = {
  NOTICE: "#ef4444", COMMUNITY: "#3b82f6", FEEDBACK: "#8b5cf6",
};

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "방금";
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return days < 30 ? `${days}일 전` : dateStr.slice(0, 10);
}

export default function PostsFeedScreen() {
  const [posts, setPosts] = useState<PostResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const initialLoaded = useRef(false);

  // 좋아요 (클라이언트 상태)
  const [likedIds, setLikedIds] = useState<Set<string>>(new Set());
  const [likeCounts, setLikeCounts] = useState<Record<string, number>>({});

  // 댓글
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [comments, setComments] = useState<Record<string, CommentRead[]>>({});
  const [commentText, setCommentText] = useState<Record<string, string>>({});
  const [loadingComments, setLoadingComments] = useState<string | null>(null);
  const [submittingComment, setSubmittingComment] = useState<string | null>(null);

  async function load() {
    try {
      const data = await apiFetch<PostResponse[]>("/feed");
      const list: PostResponse[] = Array.isArray(data) ? data : [];
      setPosts(list);
      const liked = new Set<string>();
      const counts: Record<string, number> = {};
      list.forEach(p => { if (p.is_liked) liked.add(p.id); counts[p.id] = p.like_count; });
      setLikedIds(liked);
      setLikeCounts(counts);
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

  async function toggleLike(postId: string) {
    const wasLiked = likedIds.has(postId);
    // 낙관적 업데이트
    setLikedIds(prev => { const n = new Set(prev); wasLiked ? n.delete(postId) : n.add(postId); return n; });
    setLikeCounts(prev => ({ ...prev, [postId]: (prev[postId] ?? 0) + (wasLiked ? -1 : 1) }));
    try {
      const res = await apiFetch<{ ok: boolean; is_liked: boolean }>(`/posts/${postId}/like`, { method: "POST" });
      setLikedIds(prev => { const n = new Set(prev); res.is_liked ? n.add(postId) : n.delete(postId); return n; });
    } catch {
      // 롤백
      setLikedIds(prev => { const n = new Set(prev); wasLiked ? n.add(postId) : n.delete(postId); return n; });
      setLikeCounts(prev => ({ ...prev, [postId]: (prev[postId] ?? 0) + (wasLiked ? 1 : -1) }));
    }
  }

  async function toggleComments(postId: string) {
    if (expandedId === postId) { setExpandedId(null); return; }
    setExpandedId(postId);
    if (!comments[postId]) {
      setLoadingComments(postId);
      try {
        const data = await apiFetch<CommentRead[]>(`/posts/${postId}/comments`);
        setComments(prev => ({ ...prev, [postId]: Array.isArray(data) ? data : [] }));
      } catch {
        setComments(prev => ({ ...prev, [postId]: [] }));
      } finally {
        setLoadingComments(null);
      }
    }
  }

  async function submitComment(postId: string) {
    const text = (commentText[postId] ?? "").trim();
    if (!text) return;
    setSubmittingComment(postId);
    try {
      const comment = await apiFetch<CommentRead>(`/posts/${postId}/comments`, {
        method: "POST", body: { content: text },
      });
      setComments(prev => ({ ...prev, [postId]: [...(prev[postId] ?? []), comment] }));
      setCommentText(prev => ({ ...prev, [postId]: "" }));
      setPosts(prev => prev.map(p => p.id === postId ? { ...p, comment_count: p.comment_count + 1 } : p));
    } catch (e) {
      console.error("댓글 작성 실패:", e);
    } finally {
      setSubmittingComment(null);
    }
  }

  if (loading) return <View style={s.center}><ActivityIndicator size="large" /></View>;

  return (
    <ScrollView
      style={s.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      {posts.length === 0 ? (
        <View style={s.empty}><Text style={s.emptyTxt}>공개된 게시물이 없습니다</Text></View>
      ) : posts.map(post => {
        const thumb = post.media.find(m => m.media_type === "IMAGE");
        const isLiked = likedIds.has(post.id);
        const likeCount = likeCounts[post.id] ?? post.like_count;
        const isExpanded = expandedId === post.id;
        const typeColor = TYPE_COLOR[post.post_type] ?? "#6b7280";

        return (
          <View key={post.id} style={s.card}>
            {/* 헤더 */}
            <View style={s.cardHeader}>
              <View style={[s.typeDot, { backgroundColor: typeColor }]} />
              <Text style={[s.typeTxt, { color: typeColor }]}>
                {POST_TYPE_LABEL[post.post_type] ?? post.post_type}
              </Text>
              <Text style={s.timeAgo}>{timeAgo(post.published_at ?? post.created_at)}</Text>
            </View>

            {/* 이미지 */}
            {thumb && <Image source={{ uri: thumb.url }} style={s.image} resizeMode="cover" />}

            {/* 본문 */}
            <View style={s.body}>
              {post.title ? <Text style={s.title}>{post.title}</Text> : null}
              {post.caption ? <Text style={s.caption}>{post.caption}</Text> : null}

              {/* 좋아요 · 댓글 버튼 */}
              <View style={s.actions}>
                <Pressable style={s.actionBtn} onPress={() => toggleLike(post.id)}>
                  <Text style={[s.heart, isLiked && s.heartLiked]}>{isLiked ? "♥" : "♡"}</Text>
                  <Text style={[s.actionCount, isLiked && s.actionCountLiked]}>{likeCount}</Text>
                </Pressable>
                <Pressable style={s.actionBtn} onPress={() => toggleComments(post.id)}>
                  <Text style={s.commentIcon}>💬</Text>
                  <Text style={s.actionCount}>{post.comment_count}</Text>
                </Pressable>
              </View>
            </View>

            {/* 댓글 섹션 */}
            {isExpanded && (
              <View style={s.commentSection}>
                {loadingComments === post.id ? (
                  <ActivityIndicator size="small" style={{ margin: 16 }} />
                ) : (comments[post.id] ?? []).length === 0 ? (
                  <Text style={s.noComment}>첫 댓글을 남겨보세요</Text>
                ) : (
                  (comments[post.id] ?? []).map(c => (
                    <View key={c.id} style={s.commentRow}>
                      <View style={s.avatar}><Text style={s.avatarTxt}>U</Text></View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.commentContent}>{c.content}</Text>
                        <Text style={s.commentTime}>{timeAgo(c.created_at)}</Text>
                      </View>
                    </View>
                  ))
                )}
                {/* 댓글 입력 */}
                <View style={s.inputRow}>
                  <TextInput
                    style={s.input}
                    placeholder="댓글 달기..."
                    placeholderTextColor="#9ca3af"
                    value={commentText[post.id] ?? ""}
                    onChangeText={t => setCommentText(prev => ({ ...prev, [post.id]: t }))}
                    returnKeyType="send"
                    onSubmitEditing={() => submitComment(post.id)}
                  />
                  <Pressable
                    style={[s.sendBtn, !commentText[post.id]?.trim() && s.sendBtnDisabled]}
                    onPress={() => submitComment(post.id)}
                    disabled={submittingComment === post.id || !commentText[post.id]?.trim()}
                  >
                    <Text style={s.sendTxt}>{submittingComment === post.id ? "..." : "게시"}</Text>
                  </Pressable>
                </View>
              </View>
            )}
          </View>
        );
      })}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0f0f0" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  empty: { margin: 40, alignItems: "center" },
  emptyTxt: { color: "#9ca3af", fontSize: 14 },
  card: { backgroundColor: "#fff", marginBottom: 8 },
  cardHeader: { flexDirection: "row", alignItems: "center", paddingHorizontal: 14, paddingVertical: 10 },
  typeDot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  typeTxt: { fontSize: 12, fontWeight: "700" },
  timeAgo: { fontSize: 12, color: "#9ca3af", marginLeft: "auto" },
  image: { width: "100%", height: 280 },
  body: { paddingHorizontal: 14, paddingTop: 12, paddingBottom: 14 },
  title: { fontSize: 15, fontWeight: "700", color: "#111", marginBottom: 6 },
  caption: { fontSize: 14, color: "#374151", lineHeight: 22 },
  actions: { flexDirection: "row", marginTop: 12, gap: 18 },
  actionBtn: { flexDirection: "row", alignItems: "center", gap: 5 },
  heart: { fontSize: 22, color: "#6b7280" },
  heartLiked: { color: "#ef4444" },
  commentIcon: { fontSize: 20 },
  actionCount: { fontSize: 14, color: "#374151", fontWeight: "600" },
  actionCountLiked: { color: "#ef4444" },
  commentSection: { borderTopWidth: 1, borderTopColor: "#f3f4f6" },
  noComment: { fontSize: 13, color: "#9ca3af", textAlign: "center", paddingVertical: 16 },
  commentRow: { flexDirection: "row", paddingHorizontal: 14, paddingVertical: 10, gap: 10 },
  avatar: { width: 30, height: 30, borderRadius: 15, backgroundColor: "#e5e7eb", alignItems: "center", justifyContent: "center" },
  avatarTxt: { fontSize: 12, fontWeight: "700", color: "#6b7280" },
  commentContent: { fontSize: 14, color: "#111", lineHeight: 20 },
  commentTime: { fontSize: 11, color: "#9ca3af", marginTop: 2 },
  inputRow: { flexDirection: "row", alignItems: "center", borderTopWidth: 1, borderTopColor: "#f3f4f6", paddingHorizontal: 12, paddingVertical: 10 },
  input: { flex: 1, fontSize: 14, color: "#111", paddingVertical: 4 },
  sendBtn: { paddingHorizontal: 14, paddingVertical: 7, backgroundColor: "#1a1a1a", borderRadius: 20 },
  sendBtnDisabled: { backgroundColor: "#e5e7eb" },
  sendTxt: { fontSize: 13, color: "#fff", fontWeight: "600" },
});
