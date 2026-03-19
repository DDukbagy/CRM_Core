// app/(tabs)/bookings.tsx — 예약 목록
import { useState, useCallback, useRef } from "react";
import {
  View, Text, FlatList, Pressable, Alert, ActivityIndicator,
  RefreshControl, StyleSheet,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { BookingRead, BookingStatus } from "@/types/api";

const STATUS_LABEL: Record<BookingStatus, string> = {
  REQUESTED: "신청됨",
  CONFIRMED: "확정",
  CANCEL_REQUESTED: "취소 신청중",
  CANCELLED: "취소됨",
  COMPLETED: "완료",
  NO_SHOW: "노쇼",
};

const STATUS_COLOR: Record<BookingStatus, string> = {
  REQUESTED: "#f59e0b",
  CONFIRMED: "#10b981",
  CANCEL_REQUESTED: "#f97316",
  CANCELLED: "#ef4444",
  COMPLETED: "#6b7280",
  NO_SHOW: "#dc2626",
};

type TabType = "upcoming" | "past";

export default function BookingsScreen() {
  const router = useRouter();
  const [bookings, setBookings] = useState<BookingRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<TabType>("upcoming");
  const initialLoaded = useRef(false);

  async function load() {
    try {
      const data = await apiFetch<BookingRead[]>("/bookings/me");
      setBookings(Array.isArray(data) ? data : []);
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

  function handleBookingAction(id: number, isWithdraw: boolean) {
    const title = isWithdraw ? "신청 철회" : "예약 취소";
    const confirmText = isWithdraw ? "철회" : "취소 신청";
    const endpoint = isWithdraw ? `/bookings/${id}/withdraw` : `/bookings/${id}/cancel`;
    const errorMsg = isWithdraw ? "철회에 실패했습니다." : "취소 신청에 실패했습니다.";
    Alert.alert(title, isWithdraw ? "예약 신청을 철회하시겠습니까?" : "취소를 신청하시겠습니까?", [
      { text: "아니오", style: "cancel" },
      {
        text: confirmText, style: "destructive",
        onPress: async () => {
          try {
            await apiFetch(endpoint, { method: "PATCH" });
            load();
          } catch {
            Alert.alert("오류", errorMsg);
          }
        },
      },
    ]);
  }

  const TERMINAL = ["CANCELLED", "COMPLETED", "NO_SHOW"];
  const upcoming = bookings
    .filter(b => !TERMINAL.includes(b.status))
    .sort((a, b) => a.when.localeCompare(b.when));
  const past = bookings
    .filter(b => TERMINAL.includes(b.status))
    .sort((a, b) => b.when.localeCompare(a.when));

  const list = tab === "upcoming" ? upcoming : past;

  if (loading) return <View style={s.center}><ActivityIndicator size="large" /></View>;

  return (
    <View style={{ flex: 1, backgroundColor: "#f9fafb" }}>
      {/* 헤더 */}
      <View style={s.header}>
        <Pressable onPress={() => router.back()} style={s.backBtn}>
          <Text style={s.backTxt}>‹ 뒤로</Text>
        </Pressable>
        <Text style={s.headerTitle}>예약 목록</Text>
        <View style={{ width: 60 }} />
      </View>
      {/* 탭 */}
      <View style={s.tabs}>
        <Pressable style={[s.tabBtn, tab === "upcoming" && s.tabBtnActive]} onPress={() => setTab("upcoming")}>
          <Text style={[s.tabTxt, tab === "upcoming" && s.tabTxtActive]}>
            예정 ({upcoming.length})
          </Text>
        </Pressable>
        <Pressable style={[s.tabBtn, tab === "past" && s.tabBtnActive]} onPress={() => setTab("past")}>
          <Text style={[s.tabTxt, tab === "past" && s.tabTxtActive]}>
            지난 예약 ({past.length})
          </Text>
        </Pressable>
      </View>

      <FlatList
        data={list}
        keyExtractor={b => String(b.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        contentContainerStyle={list.length === 0 ? s.emptyContainer : { padding: 16, gap: 10 }}
        ListEmptyComponent={
          <View style={s.emptyBox}>
            <Text style={s.emptyText}>{tab === "upcoming" ? "예정된 예약이 없습니다" : "지난 예약이 없습니다"}</Text>
          </View>
        }
        renderItem={({ item: b }) => {
          const color = STATUS_COLOR[b.status] ?? "#6b7280";
          const canCancel = b.status === "CONFIRMED";
          const canWithdraw = b.status === "REQUESTED";

          return (
            <View style={s.card}>
              <View style={s.cardTop}>
                <View>
                  <Text style={s.when}>{b.when}</Text>
                  <Text style={s.topic}>{b.topic ?? "레슨"}</Text>
                </View>
                <View style={[s.badge, { backgroundColor: color + "20" }]}>
                  <Text style={[s.badgeText, { color }]}>{STATUS_LABEL[b.status] ?? b.status}</Text>
                </View>
              </View>

              {b.description ? <Text style={s.desc}>{b.description}</Text> : null}
              {b.cancel_reason ? (
                <Text style={s.cancelReason}>취소 사유: {b.cancel_reason}</Text>
              ) : null}

              {(canCancel || canWithdraw) && (
                <Pressable
                  style={s.cancelBtn}
                  onPress={() => handleBookingAction(b.id, canWithdraw)}
                >
                  <Text style={s.cancelBtnText}>{canWithdraw ? "신청 철회" : "취소 신청"}</Text>
                </Pressable>
              )}
            </View>
          );
        }}
      />
    </View>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingVertical: 12, backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  backBtn: { width: 60 },
  backTxt: { fontSize: 15, color: "#3b82f6", fontWeight: "600" },
  headerTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  tabs: { flexDirection: "row", backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#e5e7eb" },
  tabBtn: { flex: 1, paddingVertical: 14, alignItems: "center" },
  tabBtnActive: { borderBottomWidth: 2, borderBottomColor: "#1a1a1a" },
  tabTxt: { fontSize: 14, fontWeight: "600", color: "#9ca3af" },
  tabTxtActive: { color: "#111" },
  emptyContainer: { flex: 1 },
  emptyBox: { flex: 1, alignItems: "center", justifyContent: "center", paddingTop: 80 },
  emptyText: { fontSize: 14, color: "#9ca3af" },
  card: {
    backgroundColor: "#fff", borderRadius: 14, padding: 16,
    elevation: 1, shadowColor: "#000", shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06, shadowRadius: 3,
  },
  cardTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 },
  when: { fontSize: 13, color: "#6b7280", marginBottom: 2 },
  topic: { fontSize: 16, fontWeight: "700", color: "#111" },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  badgeText: { fontSize: 12, fontWeight: "700" },
  desc: { fontSize: 13, color: "#6b7280", marginTop: 4 },
  cancelReason: { fontSize: 12, color: "#ef4444", marginTop: 4 },
  cancelBtn: {
    marginTop: 12, paddingVertical: 8, borderRadius: 8,
    borderWidth: 1, borderColor: "#ef4444", alignItems: "center",
  },
  cancelBtnText: { fontSize: 13, fontWeight: "600", color: "#ef4444" },
});
