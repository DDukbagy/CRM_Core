import { useState, useCallback, useRef } from "react";
import {
  View, Text, StyleSheet, Pressable, FlatList, Image,
  ActivityIndicator, RefreshControl, Dimensions,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { useVideoPlayer, VideoView } from "expo-video";
import { apiFetch } from "@/lib/api";
import type { InstructorPostRead, MediaItemRead } from "@/types/api";

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

function VideoItem({ uri }: { uri: string }) {
  const player = useVideoPlayer(uri, (p) => { p.loop = false; });
  return <VideoView player={player} style={{ width: MEDIA_W, height: MEDIA_H }} contentFit="cover" nativeControls />;
}

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
          keyExtractor={(item) => String(item.id)}
          horizontal pagingEnabled showsHorizontalScrollIndicator={false}
          snapToInterval={MEDIA_W} decelerationRate="fast"
          onMomentumScrollEnd={(e) => setPage(Math.round(e.nativeEvent.contentOffset.x / MEDIA_W))}
          getItemLayout={(_, index) => ({ length: MEDIA_W, offset: MEDIA_W * index, index })}
          renderItem={({ item }) =>
            item.media_type === "VIDEO"
              ? <VideoItem uri={item.url} />
              : <Image source={{ uri: item.url }} style={{ width: MEDIA_W, height: MEDIA_H }} resizeMode="cover" />
          }
        />
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
  arrow: { position: "absolute", top: 0, bottom: 0, width: 36, justifyContent: "center", alignItems: "center", backgroundColor: "rgba(0,0,0,0.28)" },
  arrowLeft: { left: 0 },
  arrowRight: { right: 0 },
  arrowTxt: { color: "#fff", fontSize: 24, fontWeight: "700", lineHeight: 28 },
  dots: { flexDirection: "row", justifyContent: "center", marginTop: 8, gap: 5 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: "#d1d5db" },
  dotActive: { backgroundColor: "#1a1a1a" },
});

function PostCard({ post }: { post: InstructorPostRead }) {
  return (
    <View style={s.card}>
      <View style={s.cardHeader}>
        <Text style={s.timeAgo}>{timeAgo(post.created_at)}</Text>
      </View>
      {post.content ? <Text style={s.content}>{post.content}</Text> : null}
      {post.media_items.length > 0 && <MediaCarousel items={post.media_items} />}
    </View>
  );
}

function PostsTab() {
  const [posts, setPosts] = useState<InstructorPostRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const initialLoaded = useRef(false);

  async function load() {
    try {
      const data = await apiFetch<InstructorPostRead[]>("/instructor-posts?type=PROMOTION");
      setPosts(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("게시글 로딩 실패:", e);
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

  if (loading) return <View style={s.center}><ActivityIndicator size="large" /></View>;

  return (
    <FlatList
      data={posts}
      keyExtractor={(p) => p.id}
      renderItem={({ item }) => <PostCard post={item} />}
      contentContainerStyle={posts.length === 0 ? s.emptyContainer : { paddingVertical: 12 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
      ListEmptyComponent={
        <View style={s.emptyBox}>
          <Text style={s.emptyText}>게시글이 없습니다</Text>
          <Text style={s.emptySubText}>강사가 게시글을 올리면 여기에 표시됩니다</Text>
        </View>
      }
    />
  );
}

function ChatTab() {
  return (
    <View style={s.center}>
      <Text style={s.icon}>💬</Text>
      <Text style={s.title}>채팅</Text>
      <Text style={s.subText}>준비 중입니다</Text>
    </View>
  );
}

export default function ChatScreen() {
  const [tab, setTab] = useState<"chat" | "posts">("posts");

  return (
    <View style={s.container}>
      <View style={s.topTabs}>
        <Pressable
          style={[s.topTab, tab === "chat" && s.topTabActive]}
          onPress={() => setTab("chat")}
        >
          <Text style={[s.topTabText, tab === "chat" && s.topTabTextActive]}>채팅</Text>
        </Pressable>
        <Pressable
          style={[s.topTab, tab === "posts" && s.topTabActive]}
          onPress={() => setTab("posts")}
        >
          <Text style={[s.topTabText, tab === "posts" && s.topTabTextActive]}>게시글</Text>
        </Pressable>
      </View>

      {tab === "chat" ? <ChatTab /> : <PostsTab />}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  topTabs: {
    flexDirection: "row",
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
  },
  topTab: {
    flex: 1, paddingVertical: 13, alignItems: "center",
    borderBottomWidth: 2, borderBottomColor: "transparent",
  },
  topTabActive: { borderBottomColor: "#16a34a" },
  topTabText: { fontSize: 14, fontWeight: "600", color: "#9ca3af" },
  topTabTextActive: { color: "#16a34a" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 10 },
  icon: { fontSize: 52 },
  title: { fontSize: 20, fontWeight: "700", color: "#111" },
  subText: { fontSize: 14, color: "#9ca3af" },
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
  cardHeader: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  timeAgo: { fontSize: 12, color: "#9ca3af", marginLeft: "auto" },
  content: { fontSize: 14, color: "#374151", lineHeight: 20, marginBottom: 10 },
});
