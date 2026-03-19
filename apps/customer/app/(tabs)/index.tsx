// app/(tabs)/index.tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
  Animated,
  Dimensions,
  Pressable,
} from "react-native";
import { useFocusEffect, useNavigation } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UserRead, BookingRead } from "@/types/api";

const SCREEN_W = Dimensions.get("window").width;
const PANEL_W = Math.min(SCREEN_W * 0.82, 340);

const statusColor: Record<string, string> = {
  REQUESTED: "#f59e0b", CONFIRMED: "#10b981", CANCEL_REQUESTED: "#f97316",
  CANCELLED: "#ef4444", COMPLETED: "#6b7280",
};
const statusLabel: Record<string, string> = {
  REQUESTED: "신청됨", CONFIRMED: "확정", CANCEL_REQUESTED: "취소 신청중",
  CANCELLED: "취소됨", COMPLETED: "완료",
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

type NotifEntry = {
  key: string;
  icon: string;
  message: string;
  sub: string;
  timeKey: string; // for sorting
  color: string;
};

function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "방금";
  if (mins < 60) return `${mins}분 전`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}시간 전`;
  return `${Math.floor(hrs / 24)}일 전`;
}

function daysUntil(dateStr: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(dateStr);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function BookingCard({ b }: { b: BookingRead }) {
  const days = daysUntil(b.when);
  const isUrgent = days >= 0 && days <= 3;
  const dLabel = days === 0 ? "D-DAY" : `D-${days}`;

  return (
    <View style={[s.card, isUrgent && s.urgentCard]}>
      <View style={s.cardHeader}>
        <Text style={[s.cardTopic, isUrgent && s.urgentTopic]}>{b.topic}</Text>
        <View style={[s.badge, { backgroundColor: statusColor[b.status] ?? "#6b7280" }]}>
          <Text style={s.badgeText}>{statusLabel[b.status] ?? b.status}</Text>
        </View>
      </View>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <Text style={s.cardMeta}>{b.type === "LESSON" ? "레슨" : "상담"} · {b.when}</Text>
        {isUrgent && (
          <View style={s.urgentBadge}>
            <Text style={s.urgentBadgeTxt}>{dLabel}</Text>
          </View>
        )}
      </View>
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
  const [allBookings, setAllBookings] = useState<BookingRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const initialLoaded = useRef(false);

  // 알림: CONFIRMED(확정/취소거절) + 3일 이내 일정
  const notifItems = useMemo((): NotifEntry[] => {
    const todayDate = new Date();
    todayDate.setHours(0, 0, 0, 0);
    const result: NotifEntry[] = [];

    allBookings.forEach(b => {
      if (b.status === "CONFIRMED") {
        // 예약 확정 알림 (updated_at 기준 최근)
        result.push({
          key: `confirmed-${b.id}`,
          icon: "✅",
          message: "예약이 확정되었습니다",
          sub: `${b.when} · ${b.topic ?? "레슨"}`,
          timeKey: b.updated_at,
          color: "#10b981",
        });

        // 3일 이내 일정 알림
        const whenDate = new Date(b.when + "T00:00:00");
        const diffDays = Math.round((whenDate.getTime() - todayDate.getTime()) / 86400000);
        if (diffDays >= 0 && diffDays <= 3) {
          const label = diffDays === 0 ? "오늘" : diffDays === 1 ? "내일" : `${diffDays}일 후`;
          result.push({
            key: `upcoming-${b.id}`,
            icon: "📅",
            message: `${label} 레슨 일정이 있습니다`,
            sub: `${b.when} · ${b.topic ?? "레슨"}`,
            timeKey: b.when,
            color: "#3b82f6",
          });
        }
      }
    });

    // 임박 일정 우선, 그 다음 최신 업데이트 순
    return result.sort((a, b) => {
      const aUp = a.key.startsWith("upcoming");
      const bUp = b.key.startsWith("upcoming");
      if (aUp && !bUp) return -1;
      if (!aUp && bUp) return 1;
      return new Date(b.timeKey).getTime() - new Date(a.timeKey).getTime();
    });
  }, [allBookings]);

  // 알림 패널
  const [notifVisible, setNotifVisible] = useState(false);
  const notifAnim = useRef(new Animated.Value(PANEL_W)).current;
  const navigation = useNavigation();

  const openNotif = useCallback(() => {
    setNotifVisible(true);
    Animated.timing(notifAnim, { toValue: 0, duration: 260, useNativeDriver: true }).start();
  }, [notifAnim]);

  const closeNotif = useCallback(() => {
    Animated.timing(notifAnim, { toValue: PANEL_W, duration: 220, useNativeDriver: true })
      .start(() => setNotifVisible(false));
  }, [notifAnim]);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <Pressable onPress={openNotif} style={{ marginRight: 16, padding: 4 }}>
          <Text style={{ fontSize: 20 }}>🔔</Text>
        </Pressable>
      ),
    });
  }, [openNotif]);

  async function load() {
    try {
      const [me, data] = await Promise.all([
        apiFetch<UserRead>("/users/me"),
        apiFetch<BookingRead[]>("/bookings/me"),
      ]);
      setUser(me);

      const rawList = Array.isArray(data) ? data : [];
      // 알림용: 전체 보관 (최신 업데이트 순)
      setAllBookings([...rawList].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()));

      const list = rawList.filter((b) => b.status !== "CANCELLED");

      const today = new Date().toISOString().slice(0, 10);
      const { start: wStart, end: wEnd } = getWeekRange();
      const { start: mStart, end: mEnd } = getMonthRange();

      setTodayBookings(list.filter((b) => b.when === today));
      setWeekBookings(list.filter((b) => b.when >= wStart && b.when <= wEnd && b.when !== today));
      setMonthBookings(list.filter((b) => b.when >= mStart && b.when <= mEnd && b.when > wEnd));
    } catch {
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
    <View style={{ flex: 1 }}>
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
        <View style={{ height: 20 }} />
      </ScrollView>

      {/* 알림 패널 */}
      {notifVisible && (
        <>
          <Pressable style={ns.backdrop} onPress={closeNotif} />
          <Animated.View style={[ns.panel, { transform: [{ translateX: notifAnim }] }]}>
            <View style={ns.header}>
              <Text style={ns.headerTitle}>알림</Text>
              <Pressable onPress={closeNotif} style={ns.closeBtn}>
                <Text style={ns.closeTxt}>✕</Text>
              </Pressable>
            </View>
            <ScrollView showsVerticalScrollIndicator={false}>
              {notifItems.length === 0 ? (
                <View style={ns.empty}>
                  <Text style={ns.emptyTxt}>새로운 알림이 없습니다</Text>
                </View>
              ) : (
                notifItems.map(n => (
                  <View key={n.key} style={ns.item}>
                    <Text style={ns.itemIcon}>{n.icon}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={[ns.itemTitle, { color: n.color }]}>{n.message}</Text>
                      <Text style={ns.itemMeta}>{n.sub}</Text>
                    </View>
                    <Text style={ns.itemTime}>{relTime(n.timeKey)}</Text>
                  </View>
                ))
              )}
            </ScrollView>
          </Animated.View>
        </>
      )}
    </View>
  );
}

const ns = StyleSheet.create({
  backdrop: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  panel: {
    position: "absolute", top: 0, right: 0, bottom: 0,
    width: PANEL_W, backgroundColor: "#fff",
    shadowColor: "#000", shadowOffset: { width: -2, height: 0 },
    shadowOpacity: 0.18, shadowRadius: 12, elevation: 20,
  },
  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 20, paddingTop: 56, paddingBottom: 16,
    borderBottomWidth: 1, borderBottomColor: "#f3f4f6",
  },
  headerTitle: { fontSize: 18, fontWeight: "700", color: "#111" },
  closeBtn: { padding: 6 },
  closeTxt: { fontSize: 18, color: "#9ca3af" },
  empty: { alignItems: "center", paddingTop: 60 },
  emptyTxt: { color: "#9ca3af", fontSize: 14 },
  item: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingHorizontal: 20, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: "#f9fafb",
  },
  itemIcon: { fontSize: 18, flexShrink: 0 },
  itemTitle: { fontSize: 13, fontWeight: "700", marginBottom: 2 },
  itemMeta: { fontSize: 12, color: "#6b7280" },
  itemTime: { fontSize: 11, color: "#9ca3af", flexShrink: 0 },
});

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
  urgentCard: { backgroundColor: "#fff7ed", borderWidth: 1.5, borderColor: "#f97316" },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  cardTopic: { fontSize: 14, fontWeight: "600", flex: 1 },
  urgentTopic: { color: "#c2410c" },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "600" },
  cardMeta: { fontSize: 12, color: "#6b7280" },
  urgentBadge: { backgroundColor: "#f97316", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 20 },
  urgentBadgeTxt: { color: "#fff", fontSize: 11, fontWeight: "700" },
});
