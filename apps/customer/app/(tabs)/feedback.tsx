import { useState, useCallback, useRef } from "react";
import {
  View, Text, StyleSheet, FlatList, Pressable, Modal,
  ActivityIndicator, RefreshControl, ScrollView, Image, Dimensions,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { useVideoPlayer, VideoView } from "expo-video";
import { apiFetch } from "@/lib/api";
import type { InstructorPostRead, MediaItemRead } from "@/types/api";

const SW = Dimensions.get("window").width;
const SH = Dimensions.get("window").height;

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

// ─── 동영상 ───────────────────────────────────────────────────────────────────
function VideoItem({ uri, w, h }: { uri: string; w: number; h: number }) {
  const player = useVideoPlayer(uri, (p) => { p.loop = false; });
  return <VideoView player={player} style={{ width: w, height: h }} contentFit="cover" nativeControls />;
}

// ─── 미디어 캐러셀 ────────────────────────────────────────────────────────────
function MediaCarousel({ items }: { items: MediaItemRead[] }) {
  const [page, setPage] = useState(0);
  const listRef = useRef<FlatList>(null);
  const MEDIA_W = SW - 48;
  const MEDIA_H = Math.round(MEDIA_W * 0.65);
  if (items.length === 0) return null;

  function goTo(idx: number) {
    const next = Math.max(0, Math.min(idx, items.length - 1));
    listRef.current?.scrollToIndex({ index: next, animated: true });
    setPage(next);
  }

  return (
    <View style={{ marginTop: 14 }}>
      <View style={{ borderRadius: 10, overflow: "hidden" }}>
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
              ? <VideoItem uri={item.url} w={MEDIA_W} h={MEDIA_H} />
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
  arrow: { position: "absolute", top: 0, bottom: 0, width: 36, justifyContent: "center", alignItems: "center", backgroundColor: "rgba(0,0,0,0.28)" },
  arrowLeft: { left: 0 },
  arrowRight: { right: 0 },
  arrowTxt: { color: "#fff", fontSize: 24, fontWeight: "700", lineHeight: 28 },
  dots: { flexDirection: "row", justifyContent: "center", marginTop: 8, gap: 5 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: "#d1d5db" },
  dotActive: { backgroundColor: "#16a34a" },
});

// ─── 피드백 상세 모달 ─────────────────────────────────────────────────────────
function FeedbackDetail({ post, onClose }: { post: InstructorPostRead; onClose: () => void }) {
  return (
    <Modal visible animationType="slide" presentationStyle="pageSheet">
      <View style={dt.container}>
        <View style={dt.header}>
          <Text style={dt.title}>피드백</Text>
          <Pressable onPress={onClose} style={dt.closeBtn}>
            <Text style={dt.closeText}>닫기</Text>
          </Pressable>
        </View>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={dt.body}>
          <Text style={dt.date}>{new Date(post.created_at).toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric" })}</Text>
          {post.content ? (
            <Text style={dt.content}>{post.content}</Text>
          ) : (
            <Text style={dt.noContent}>내용 없음</Text>
          )}
          {post.media_items.length > 0 && <MediaCarousel items={post.media_items} />}
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
});

// ─── 피드백 리스트 아이템 ─────────────────────────────────────────────────────
function FeedbackRow({ post, onPress }: { post: InstructorPostRead; onPress: () => void }) {
  const hasMedia = post.media_items.length > 0;
  const preview = post.content ? post.content.slice(0, 60) + (post.content.length > 60 ? "…" : "") : null;

  return (
    <Pressable style={s.row} onPress={onPress}>
      {hasMedia && (
        <Image
          source={{ uri: post.media_items[0].url }}
          style={s.thumb}
          resizeMode="cover"
        />
      )}
      <View style={s.rowBody}>
        {preview
          ? <Text style={s.preview} numberOfLines={2}>{preview}</Text>
          : <Text style={s.noPreview}>미디어 피드백</Text>
        }
        <Text style={s.rowDate}>{timeAgo(post.created_at)}</Text>
      </View>
      <Text style={s.chevron}>›</Text>
    </Pressable>
  );
}

// ─── 메인 화면 ────────────────────────────────────────────────────────────────
export default function FeedbackScreen() {
  const [posts, setPosts] = useState<InstructorPostRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selected, setSelected] = useState<InstructorPostRead | null>(null);
  const initialLoaded = useRef(false);

  async function load() {
    try {
      const data = await apiFetch<InstructorPostRead[]>("/instructor-posts?type=FEEDBACK");
      setPosts(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("피드백 로딩 실패:", e);
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
        data={posts}
        keyExtractor={(p) => p.id}
        renderItem={({ item }) => (
          <FeedbackRow post={item} onPress={() => setSelected(item)} />
        )}
        contentContainerStyle={posts.length === 0 ? s.emptyContainer : { paddingVertical: 8 }}
        ItemSeparatorComponent={() => <View style={s.separator} />}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={
          <View style={s.emptyBox}>
            <Text style={s.emptyIcon}>📩</Text>
            <Text style={s.emptyText}>아직 피드백이 없습니다</Text>
            <Text style={s.emptySubText}>강사가 피드백을 남기면 여기에 표시됩니다</Text>
          </View>
        }
      />

      {selected && (
        <FeedbackDetail post={selected} onClose={() => setSelected(null)} />
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
  rowBody: { flex: 1, gap: 4 },
  preview: { fontSize: 14, color: "#374151", lineHeight: 20 },
  noPreview: { fontSize: 14, color: "#9ca3af", fontStyle: "italic" },
  rowDate: { fontSize: 12, color: "#9ca3af" },
  chevron: { fontSize: 20, color: "#d1d5db", fontWeight: "300" },
});
