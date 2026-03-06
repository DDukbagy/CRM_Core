// app/(tabs)/bookings.tsx — 게시물 피드
import { useState, useCallback } from "react";
import {
  View, Text, ScrollView, Pressable, ActivityIndicator,
  RefreshControl, StyleSheet, Image,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { PostResponse } from "@/types/api";

const POST_TYPE_LABEL: Record<string, string> = {
  NOTICE: "공지",
  COMMUNITY: "커뮤니티",
  FEEDBACK: "피드백",
};

export default function PostsFeedScreen() {
  const [posts, setPosts] = useState<PostResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      const data = await apiFetch<PostResponse[]>("/feed", { requireAuth: false });
      setPosts(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("게시물 로딩 실패:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useFocusEffect(useCallback(() => { load(); }, []));

  if (loading) {
    return <View style={s.center}><ActivityIndicator size="large" /></View>;
  }

  return (
    <ScrollView
      style={s.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Text style={s.pageTitle}>게시물</Text>

      {posts.length === 0 ? (
        <View style={s.emptyCard}>
          <Text style={s.emptyText}>공개된 게시물이 없습니다</Text>
        </View>
      ) : (
        posts.map((post) => {
          const thumb = post.media.find(m => m.media_type === "IMAGE");
          return (
            <View key={post.id} style={s.card}>
              {/* 미디어 썸네일 */}
              {thumb && (
                <Image
                  source={{ uri: thumb.url }}
                  style={s.thumbnail}
                  resizeMode="cover"
                />
              )}

              <View style={s.body}>
                {/* 유형 배지 */}
                <View style={s.typeRow}>
                  <View style={s.typeBadge}>
                    <Text style={s.typeTxt}>{POST_TYPE_LABEL[post.post_type] ?? post.post_type}</Text>
                  </View>
                  {post.when && <Text style={s.dateTxt}>{post.when}</Text>}
                </View>

                {/* 제목 / 캡션 */}
                {post.title ? (
                  <Text style={s.title} numberOfLines={2}>{post.title}</Text>
                ) : null}
                {post.caption ? (
                  <Text style={s.caption} numberOfLines={3}>{post.caption}</Text>
                ) : null}

                {/* 좋아요 · 댓글 */}
                <View style={s.footer}>
                  <Text style={s.footerTxt}>♡ {post.like_count}</Text>
                  <Text style={[s.footerTxt, { marginLeft: 12 }]}>💬 {post.comment_count}</Text>
                  <Text style={s.publishedAt}>
                    {post.published_at ? post.published_at.slice(0, 10) : post.created_at.slice(0, 10)}
                  </Text>
                </View>
              </View>
            </View>
          );
        })
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  pageTitle: { fontSize: 20, fontWeight: "700", margin: 16, color: "#111" },
  emptyCard: { marginHorizontal: 16, padding: 32, backgroundColor: "#fff", borderRadius: 12, alignItems: "center" },
  emptyText: { color: "#9ca3af", fontSize: 14 },
  card: { marginHorizontal: 16, marginBottom: 12, backgroundColor: "#fff", borderRadius: 12, overflow: "hidden", elevation: 2 },
  thumbnail: { width: "100%", height: 180 },
  body: { padding: 14 },
  typeRow: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  typeBadge: { backgroundColor: "#f3f4f6", borderRadius: 20, paddingHorizontal: 8, paddingVertical: 3 },
  typeTxt: { fontSize: 11, color: "#6b7280", fontWeight: "600" },
  dateTxt: { fontSize: 12, color: "#9ca3af", marginLeft: 8 },
  title: { fontSize: 15, fontWeight: "700", color: "#111", marginBottom: 4 },
  caption: { fontSize: 13, color: "#374151", lineHeight: 20 },
  footer: { flexDirection: "row", alignItems: "center", marginTop: 12 },
  footerTxt: { fontSize: 13, color: "#6b7280" },
  publishedAt: { fontSize: 12, color: "#d1d5db", marginLeft: "auto" },
});
