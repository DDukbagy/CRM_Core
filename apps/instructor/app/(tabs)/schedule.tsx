import { useEffect, useState, useCallback } from "react";
import { View, Text, ScrollView, Pressable, Alert, StyleSheet } from "react-native";
import { apiFetch } from "@/lib/api";
import type { BookingRead, TimeSlotRead } from "@/types/api";

const WEEKDAY = ["일", "월", "화", "수", "목", "금", "토"];

function getWeekDates(base: Date): Date[] {
  const day = base.getDay();
  const dates: Date[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(base);
    d.setDate(base.getDate() - day + i);
    dates.push(d);
  }
  return dates;
}

function fmt(d: Date) { return d.toISOString().slice(0, 10); }

export default function ScheduleScreen() {
  const [baseDate, setBaseDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(fmt(new Date()));
  const [bookings, setBookings] = useState<BookingRead[]>([]);
  const [slots, setSlots] = useState<TimeSlotRead[]>([]);

  const weekDates = getWeekDates(baseDate);
  const weekStart = fmt(weekDates[0]);
  const weekEnd = fmt(weekDates[6]);

  const load = useCallback(async () => {
    try {
      const [b, s] = await Promise.all([
        apiFetch<BookingRead[]>(`/calendars/me/bookings?start=${weekStart}&end=${weekEnd}`),
        apiFetch<TimeSlotRead[]>("/calendars/me/time-slots"),
      ]);
      setBookings(b);
      setSlots(s);
    } catch { /* ignore */ }
  }, [weekStart, weekEnd]);

  useEffect(() => { load(); }, [load]);

  const dayBookings = bookings.filter(b => b.when === selectedDate);

  async function doAction(bookingId: number, action: "confirm" | "complete" | "no-show" | "cancel") {
    const labels: Record<string, string> = { confirm: "확정", complete: "완료", "no-show": "노쇼 처리", cancel: "취소" };
    Alert.alert(`${labels[action]} 처리`, "진행하시겠습니까?", [
      { text: "취소", style: "cancel" },
      {
        text: "확인", onPress: async () => {
          try {
            await apiFetch(`/calendars/me/bookings/${bookingId}/${action}`, { method: "PATCH" });
            await load();
          } catch (e: unknown) {
            Alert.alert("오류", e instanceof Error ? e.message : "처리 실패");
          }
        },
      },
    ]);
  }

  async function toggleSlot(slot: TimeSlotRead) {
    const next = !slot.is_active;
    Alert.alert(
      next ? "슬롯 활성화" : "슬롯 비활성화",
      `${slot.start_time}~${slot.end_time} 슬롯을 ${next ? "활성화" : "비활성화"}하시겠습니까?`,
      [
        { text: "취소", style: "cancel" },
        {
          text: "확인", onPress: async () => {
            try {
              await apiFetch(`/calendars/me/time-slots/${slot.id}`, { method: "PATCH", body: { is_active: next } });
              await load();
            } catch { Alert.alert("오류", "변경 실패"); }
          },
        },
      ]
    );
  }

  async function blockDate() {
    const tsId = slots.find(s => s.is_active);
    if (!tsId) { Alert.alert("슬롯 없음", "활성화된 타임슬롯이 없습니다."); return; }
    Alert.alert("날짜 차단", `${selectedDate}을 휴무로 등록하시겠습니까?`, [
      { text: "취소", style: "cancel" },
      {
        text: "확인", onPress: async () => {
          try {
            await apiFetch("/bookings", { method: "POST", body: { time_slot_id: tsId.id, when: selectedDate, topic: "휴무", type: "HOLIDAY" } });
            await load();
          } catch (e: unknown) {
            Alert.alert("오류", e instanceof Error ? e.message : "등록 실패");
          }
        },
      },
    ]);
  }

  const statusColor: Record<string, string> = {
    REQUESTED: "#f59e0b", CONFIRMED: "#3b82f6", COMPLETED: "#16a34a", CANCELLED: "#9ca3af", NO_SHOW: "#ef4444",
  };
  const statusLabel: Record<string, string> = {
    REQUESTED: "대기", CONFIRMED: "확정", COMPLETED: "완료", CANCELLED: "취소", NO_SHOW: "노쇼",
  };

  return (
    <View style={s.container}>
      {/* 주간 네비게이션 */}
      <View style={s.weekNav}>
        <Pressable onPress={() => setBaseDate(d => { const n = new Date(d); n.setDate(n.getDate() - 7); return n; })} style={s.navBtn}>
          <Text style={s.navBtnText}>‹</Text>
        </Pressable>
        <Text style={s.weekLabel}>{weekStart} ~ {weekEnd}</Text>
        <Pressable onPress={() => setBaseDate(d => { const n = new Date(d); n.setDate(n.getDate() + 7); return n; })} style={s.navBtn}>
          <Text style={s.navBtnText}>›</Text>
        </Pressable>
      </View>

      {/* 요일 선택 */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.dayRow}>
        {weekDates.map(d => {
          const ds = fmt(d);
          const hasBk = bookings.some(b => b.when === ds);
          const isSelected = ds === selectedDate;
          return (
            <Pressable key={ds} onPress={() => setSelectedDate(ds)} style={[s.dayBtn, isSelected && s.dayBtnSel]}>
              <Text style={[s.dayLabel, isSelected && s.dayLabelSel]}>{WEEKDAY[d.getDay()]}</Text>
              <Text style={[s.dayNum, isSelected && s.dayNumSel]}>{d.getDate()}</Text>
              {hasBk && <View style={[s.dot, isSelected && s.dotSel]} />}
            </Pressable>
          );
        })}
      </ScrollView>

      <ScrollView style={s.content}>
        {/* 예약 목록 */}
        <View style={s.sectionHeader}>
          <Text style={s.sectionTitle}>{selectedDate} 예약 ({dayBookings.length}건)</Text>
          <Pressable onPress={blockDate} style={s.blockBtn}>
            <Text style={s.blockBtnText}>+ 휴무 등록</Text>
          </Pressable>
        </View>

        {dayBookings.length === 0
          ? <View style={s.emptyBox}><Text style={s.emptyText}>예약 없음</Text></View>
          : dayBookings.map(b => (
            <View key={b.id} style={s.bkCard}>
              <View style={[s.badge, { backgroundColor: statusColor[b.status] ?? "#9ca3af" }]}>
                <Text style={s.badgeText}>{statusLabel[b.status] ?? b.status}</Text>
              </View>
              <Text style={s.bkTopic}>{b.topic ?? "제목 없음"}</Text>
              {b.status === "REQUESTED" && (
                <View style={s.actions}>
                  <Pressable style={[s.actionBtn, { backgroundColor: "#3b82f6" }]} onPress={() => doAction(b.id, "confirm")}>
                    <Text style={s.actionText}>확정</Text>
                  </Pressable>
                  <Pressable style={[s.actionBtn, { backgroundColor: "#9ca3af" }]} onPress={() => doAction(b.id, "cancel")}>
                    <Text style={s.actionText}>거절</Text>
                  </Pressable>
                </View>
              )}
              {b.status === "CONFIRMED" && (
                <View style={s.actions}>
                  <Pressable style={[s.actionBtn, { backgroundColor: "#16a34a" }]} onPress={() => doAction(b.id, "complete")}>
                    <Text style={s.actionText}>완료</Text>
                  </Pressable>
                  <Pressable style={[s.actionBtn, { backgroundColor: "#ef4444" }]} onPress={() => doAction(b.id, "no-show")}>
                    <Text style={s.actionText}>노쇼</Text>
                  </Pressable>
                </View>
              )}
            </View>
          ))
        }

        {/* 타임슬롯 관리 */}
        <Text style={s.sectionTitle2}>타임슬롯 관리</Text>
        {slots.length === 0
          ? <View style={s.emptyBox}><Text style={s.emptyText}>등록된 슬롯 없음</Text></View>
          : slots.map(slot => (
            <View key={slot.id} style={s.slotCard}>
              <View style={s.slotInfo}>
                <Text style={s.slotTime}>{slot.start_time} ~ {slot.end_time}</Text>
                <Text style={s.slotDays}>{slot.weekdays.map(d => WEEKDAY[d]).join(", ")}</Text>
              </View>
              <Pressable
                onPress={() => toggleSlot(slot)}
                style={[s.toggle, slot.is_active ? s.toggleOn : s.toggleOff]}
              >
                <Text style={s.toggleText}>{slot.is_active ? "활성" : "비활성"}</Text>
              </Pressable>
            </View>
          ))
        }
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  weekNav: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingVertical: 12, backgroundColor: "#fff" },
  navBtn: { padding: 8 },
  navBtnText: { fontSize: 22, color: "#374151" },
  weekLabel: { fontSize: 13, color: "#6b7280" },
  dayRow: { backgroundColor: "#fff", borderBottomWidth: 1, borderColor: "#e5e7eb", flexGrow: 0 },
  dayBtn: { alignItems: "center", paddingVertical: 10, paddingHorizontal: 12, minWidth: 44 },
  dayBtnSel: { borderBottomWidth: 2, borderColor: "#16a34a" },
  dayLabel: { fontSize: 11, color: "#9ca3af" },
  dayLabelSel: { color: "#16a34a", fontWeight: "600" },
  dayNum: { fontSize: 17, fontWeight: "600", color: "#374151", marginTop: 2 },
  dayNumSel: { color: "#16a34a" },
  dot: { width: 4, height: 4, borderRadius: 2, backgroundColor: "#9ca3af", marginTop: 2 },
  dotSel: { backgroundColor: "#16a34a" },
  content: { flex: 1 },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, paddingTop: 14, paddingBottom: 6 },
  sectionTitle: { fontSize: 15, fontWeight: "600" },
  sectionTitle2: { fontSize: 15, fontWeight: "600", paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 },
  blockBtn: { backgroundColor: "#fef3c7", paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8 },
  blockBtnText: { fontSize: 12, color: "#92400e", fontWeight: "600" },
  emptyBox: { margin: 16, padding: 20, backgroundColor: "#fff", borderRadius: 12, alignItems: "center" },
  emptyText: { color: "#9ca3af" },
  bkCard: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8, borderRadius: 10, padding: 14, elevation: 1 },
  badge: { alignSelf: "flex-start", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, marginBottom: 6 },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "600" },
  bkTopic: { fontSize: 15, fontWeight: "500", marginBottom: 8 },
  actions: { flexDirection: "row", gap: 8 },
  actionBtn: { flex: 1, padding: 8, borderRadius: 8, alignItems: "center" },
  actionText: { color: "#fff", fontSize: 13, fontWeight: "600" },
  slotCard: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8, borderRadius: 10, padding: 14, flexDirection: "row", alignItems: "center", justifyContent: "space-between", elevation: 1 },
  slotInfo: { flex: 1 },
  slotTime: { fontSize: 15, fontWeight: "600", color: "#111" },
  slotDays: { fontSize: 12, color: "#6b7280", marginTop: 2 },
  toggle: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20 },
  toggleOn: { backgroundColor: "#16a34a" },
  toggleOff: { backgroundColor: "#e5e7eb" },
  toggleText: { fontSize: 13, fontWeight: "600", color: "#fff" },
});
