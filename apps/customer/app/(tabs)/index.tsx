// app/(tabs)/index.tsx
import { useCallback, useRef, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UserRead, BookingRead } from "@/types/api";

const statusColor: Record<string, string> = {
  REQUESTED: "#f59e0b", CONFIRMED: "#10b981", CANCELLED: "#ef4444", COMPLETED: "#6b7280",
};
const statusLabel: Record<string, string> = {
  REQUESTED: "신청됨", CONFIRMED: "확정", CANCELLED: "취소됨", COMPLETED: "완료",
};

function getWeekRange() {
  const now = new Date();
  const day = now.getDay(); // 0=일
  const mon = new Date(now);
  mon.setDate(now.getDate() - ((day + 6) % 7));
  const sun = new Date(mon);
  sun.setDate(mon.getDate() + 6);
  return {
    start: mon.toISOString().slice(0, 10),
    end: sun.toISOString().slice(0, 10),
  };
}

function getMonthRange() {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().slice(0, 10);
  return { start, end };
}

function BookingCard({ b }: { b: BookingRead }) {
  return (
    <View style={s.card}>
      <View style={s.cardHeader}>
        <Text style={s.cardTopic}>{b.topic}</Text>
        <View style={[s.badge, { backgroundColor: statusColor[b.status] ?? "#6b7280" }]}>
          <Text style={s.badgeText}>{statusLabel[b.status] ?? b.status}</Text>
        </View>
      </View>
      <Text style={s.cardMeta}>{b.type === "LESSON" ? "레슨" : "상담"} · {b.when}</Text>
    </View>
  );
}

function Section({ title, items }: { title: string; items: BookingRead[] }) {
  return (
    <>
      <Text style={s.section}>{title}</Text>
      {items.length === 0 ? (
        <View style={s.emptyCard}>
          <Text style={s.emptyText}>예정된 예약이 없습니다</Text>
        </View>
      ) : (
        items.map((b) => <BookingCard key={b.id} b={b} />)
      )}
    </>
  );
}

export default function HomeScreen() {
  const [user, setUser] = useState<UserRead | null>(null);
  const [todayBookings, setTodayBookings] = useState<BookingRead[]>([]);
  const [weekBookings, setWeekBookings] = useState<BookingRead[]>([]);
  const [monthBookings, setMonthBookings] = useState<BookingRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const initialLoaded = useRef(false);

  async function load() {
    try {
      const [me, data] = await Promise.all([
        apiFetch<UserRead>("/users/me"),
        apiFetch<BookingRead[]>("/bookings/me"),
      ]);
      setUser(me);

      const list = (Array.isArray(data) ? data : []).filter(
        (b) => b.status !== "CANCELLED"
      );

      const today = new Date().toISOString().slice(0, 10);
      const { start: wStart, end: wEnd } = getWeekRange();
      const { start: mStart, end: mEnd } = getMonthRange();

      setTodayBookings(list.filter((b) => b.when === today));
      setWeekBookings(list.filter((b) => b.when >= wStart && b.when <= wEnd && b.when !== today));
      setMonthBookings(list.filter((b) => b.when >= mStart && b.when <= mEnd && b.when > wEnd));
    } catch (e) {
      console.error("홈 로딩 실패:", e);
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

  const today = new Date().toISOString().slice(0, 10);
  const { start: wStart, end: wEnd } = getWeekRange();
  const { start: mStart, end: mEnd } = getMonthRange();

  return (
    <ScrollView
      style={s.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <View style={s.welcomeCard}>
        <Text style={s.welcomeGreet}>안녕하세요 👋</Text>
        <Text style={s.welcomeName}>{user?.display_name ?? "고객"} 님</Text>
        <Text style={s.welcomeEmail}>{user?.email}</Text>
      </View>

      <Section title={`오늘 (${today})`} items={todayBookings} />
      <Section title={`이번 주 (${wStart} ~ ${wEnd})`} items={weekBookings} />
      <Section title={`이번 달 나머지 (~ ${mEnd})`} items={monthBookings} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  welcomeCard: { margin: 16, padding: 20, backgroundColor: "#1a1a1a", borderRadius: 16 },
  welcomeGreet: { color: "#9ca3af", fontSize: 14, marginBottom: 4 },
  welcomeName: { color: "#fff", fontSize: 22, fontWeight: "700" },
  welcomeEmail: { color: "#6b7280", fontSize: 13, marginTop: 4 },
  section: { fontSize: 15, fontWeight: "700", marginHorizontal: 16, marginTop: 16, marginBottom: 8, color: "#374151" },
  emptyCard: { marginHorizontal: 16, padding: 16, backgroundColor: "#fff", borderRadius: 12, alignItems: "center" },
  emptyText: { color: "#9ca3af", fontSize: 13 },
  card: { marginHorizontal: 16, marginBottom: 8, padding: 14, backgroundColor: "#fff", borderRadius: 12, elevation: 2 },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  cardTopic: { fontSize: 14, fontWeight: "600", flex: 1 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "600" },
  cardMeta: { fontSize: 12, color: "#6b7280" },
});
