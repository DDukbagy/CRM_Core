import { useEffect, useState, useCallback } from "react";
import { View, Text, ScrollView, RefreshControl, StyleSheet } from "react-native";
import { apiFetch } from "@/lib/api";
import type { InstructorStats, BookingRead } from "@/types/api";

export default function DashboardScreen() {
  const [stats, setStats] = useState<InstructorStats | null>(null);
  const [todayBookings, setTodayBookings] = useState<BookingRead[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const today = new Date().toISOString().slice(0, 10);

  const load = useCallback(async () => {
    try {
      const [s, b] = await Promise.all([
        apiFetch<InstructorStats>("/instructors/me/stats"),
        apiFetch<BookingRead[]>(`/calendars/me/bookings?start=${today}&end=${today}`),
      ]);
      setStats(s);
      setTodayBookings(b);
    } catch { /* ignore */ }
  }, [today]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const statusLabel: Record<string, string> = {
    REQUESTED: "대기", CONFIRMED: "확정", COMPLETED: "완료",
    CANCELLED: "취소", NO_SHOW: "노쇼",
  };
  const statusColor: Record<string, string> = {
    REQUESTED: "#f59e0b", CONFIRMED: "#3b82f6", COMPLETED: "#16a34a",
    CANCELLED: "#9ca3af", NO_SHOW: "#ef4444",
  };

  return (
    <ScrollView style={s.container} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
      <Text style={s.heading}>대시보드</Text>

      {stats && (
        <>
          <View style={s.card}>
            <Text style={s.cardTitle}>담당 고객</Text>
            <Text style={s.bigNum}>{stats.customer_count}명</Text>
          </View>

          <View style={s.card}>
            <Text style={s.cardTitle}>예약 현황</Text>
            <View style={s.row}>
              {[
                ["대기", stats.booking_counts.requested, "#f59e0b"],
                ["확정", stats.booking_counts.confirmed, "#3b82f6"],
                ["완료", stats.booking_counts.completed, "#16a34a"],
                ["노쇼", stats.booking_counts.no_show, "#ef4444"],
              ].map(([label, count, color]) => (
                <View key={String(label)} style={s.statItem}>
                  <Text style={[s.statNum, { color: String(color) }]}>{count}</Text>
                  <Text style={s.statLabel}>{label}</Text>
                </View>
              ))}
            </View>
          </View>

          {stats.attendance_rate !== null && (
            <View style={s.card}>
              <Text style={s.cardTitle}>출석률</Text>
              <Text style={s.bigNum}>{stats.attendance_rate}%</Text>
            </View>
          )}
        </>
      )}

      <Text style={s.sectionTitle}>오늘 예약 ({todayBookings.length}건)</Text>
      {todayBookings.length === 0 ? (
        <View style={s.emptyBox}><Text style={s.emptyText}>오늘 예약이 없습니다.</Text></View>
      ) : todayBookings.map(b => (
        <View key={b.id} style={s.bookingCard}>
          <View style={[s.statusBadge, { backgroundColor: statusColor[b.status] ?? "#9ca3af" }]}>
            <Text style={s.statusText}>{statusLabel[b.status] ?? b.status}</Text>
          </View>
          <Text style={s.bookingTopic}>{b.topic ?? "제목 없음"}</Text>
          <Text style={s.bookingTime}>예약번호 #{b.id}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  heading: { fontSize: 22, fontWeight: "700", padding: 20, paddingBottom: 12 },
  card: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 12, borderRadius: 12, padding: 16, shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 },
  cardTitle: { fontSize: 13, color: "#6b7280", marginBottom: 8 },
  bigNum: { fontSize: 32, fontWeight: "700", color: "#111" },
  row: { flexDirection: "row", justifyContent: "space-around" },
  statItem: { alignItems: "center" },
  statNum: { fontSize: 24, fontWeight: "700" },
  statLabel: { fontSize: 12, color: "#6b7280", marginTop: 2 },
  sectionTitle: { fontSize: 16, fontWeight: "600", paddingHorizontal: 16, paddingVertical: 12 },
  emptyBox: { margin: 16, padding: 20, backgroundColor: "#fff", borderRadius: 12, alignItems: "center" },
  emptyText: { color: "#9ca3af" },
  bookingCard: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8, borderRadius: 10, padding: 14, flexDirection: "row", alignItems: "center", gap: 10 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  statusText: { color: "#fff", fontSize: 12, fontWeight: "600" },
  bookingTopic: { flex: 1, fontSize: 15, fontWeight: "500" },
  bookingTime: { fontSize: 12, color: "#9ca3af" },
});
