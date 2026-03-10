import { useCallback, useRef, useState } from "react";
import {
  View, Text, ScrollView, Pressable, Modal, TextInput,
  Animated, Dimensions, StyleSheet, ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { BookingRead, TimeSlotRead, UsersListResponse } from "@/types/api";

const { height: SCREEN_H, width: SCREEN_W } = Dimensions.get("window");
const CELL_H = Math.floor((SCREEN_H - 200) / 6);
const PANEL_H = SCREEN_H * 0.52;
const DAYS_KO = ["일", "월", "화", "수", "목", "금", "토"];
const MONTHS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];
const START_H = 6, END_H = 22, HOUR_H = 60, TIME_LABEL_W = 52;

const STATUS_COLOR: Record<string, string> = {
  REQUESTED: "#f59e0b", CONFIRMED: "#3b82f6", CANCEL_REQUESTED: "#f97316",
  COMPLETED: "#16a34a", CANCELLED: "#9ca3af", NO_SHOW: "#ef4444",
};
const STATUS_LABEL: Record<string, string> = {
  REQUESTED: "대기", CONFIRMED: "확정", CANCEL_REQUESTED: "취소신청",
  COMPLETED: "완료", CANCELLED: "취소", NO_SHOW: "노쇼",
};

function toDateStr(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}
function fmtTime(t: string) { return t.slice(0, 5); }
function parseTime(t: string) { const [h, m] = t.split(":").map(Number); return { h, m }; }
function timeToY(t: string) { const { h, m } = parseTime(t); return (h - START_H) * HOUR_H + (m / 60) * HOUR_H; }
function timeDiff(s: string, e: string) {
  const sv = parseTime(s), ev = parseTime(e);
  return ((ev.h - sv.h) * 60 + (ev.m - sv.m)) / 60 * HOUR_H;
}

// ─── MonthGrid ──────────────────────────────────────────
function MonthGrid({
  year, month, bookings, selectedDate, onSelect, customerMap,
}: {
  year: number; month: number;
  bookings: BookingRead[];
  selectedDate: string;
  onSelect: (d: string) => void;
  customerMap: Record<string, string>;
}) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date().toISOString().slice(0, 10);
  const cells: (number | null)[] = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  return (
    <View style={mg.wrap}>
      <View style={mg.header}>
        {DAYS_KO.map((d, i) => (
          <Text key={d} style={[mg.dayLabel, i === 0 && mg.sun, i === 6 && mg.sat]}>{d}</Text>
        ))}
      </View>
      {weeks.map((week, wi) => (
        <View key={wi} style={mg.week}>
          {week.map((day, di) => {
            if (!day) return <View key={di} style={mg.cell} />;
            const ds = toDateStr(year, month, day);
            const bk = bookings.filter(b => b.when === ds);
            const isToday = ds === today;
            const isSelected = ds === selectedDate;
            return (
              <Pressable key={di} style={mg.cell} onPress={() => onSelect(ds)}>
                <View style={[mg.numWrap, isToday && mg.todayWrap, isSelected && mg.selectedWrap]}>
                  <Text style={[mg.num, di === 0 && mg.sun, di === 6 && mg.sat, (isToday || isSelected) && mg.whiteNum]}>
                    {day}
                  </Text>
                </View>
                {bk.slice(0, 3).map(b => {
                  const cname = customerMap[b.guest_id] ?? "예약";
                  const shortName = cname.length > 3 ? cname.slice(0, 3) : cname;
                  const isCancelled = b.status === "CANCELLED";
                  const detail = isCancelled
                    ? (b.cancel_reason ? b.cancel_reason.slice(0, 4) : "거절")
                    : (b.topic ? b.topic.slice(0, 4) : null);
                  const label = detail ? `${shortName}·${detail}` : shortName;
                  const color = isCancelled ? "#9ca3af" : (STATUS_COLOR[b.status] ?? "#9ca3af");
                  return (
                    <View key={b.id} style={[mg.chip, { backgroundColor: color + "20", borderLeftColor: color, borderLeftWidth: 2 }]}>
                      <Text style={[mg.chipTxt, { color, textDecorationLine: isCancelled ? "line-through" : "none" }]} numberOfLines={1}>{label}</Text>
                    </View>
                  );
                })}
                {bk.length > 2 && <Text style={mg.more}>+{bk.length - 2}</Text>}
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}

const mg = StyleSheet.create({
  wrap: { backgroundColor: "#fff" },
  header: { flexDirection: "row" },
  dayLabel: { flex: 1, textAlign: "center", fontSize: 12, fontWeight: "600", color: "#9ca3af", paddingVertical: 8 },
  sun: { color: "#ef4444" },
  sat: { color: "#3b82f6" },
  week: { flexDirection: "row", height: CELL_H },
  cell: { flex: 1, borderWidth: 0.5, borderColor: "#f3f4f6", padding: 4, overflow: "hidden" },
  numWrap: { width: 22, height: 22, borderRadius: 11, alignItems: "center", justifyContent: "center", marginBottom: 2 },
  todayWrap: { backgroundColor: "#1a1a1a" },
  selectedWrap: { backgroundColor: "#16a34a" },
  num: { fontSize: 12, fontWeight: "500", color: "#111" },
  whiteNum: { color: "#fff", fontWeight: "700" },
  chip: { borderRadius: 3, paddingHorizontal: 4, paddingVertical: 1, marginBottom: 2 },
  chipTxt: { fontSize: 9, fontWeight: "700" },
  more: { fontSize: 9, color: "#9ca3af" },
});

// ─── DayPanel ───────────────────────────────────────────
function DayPanel({
  date, bookings, slots, customerMap,
  onAction, onBlockDate, onDeactivateSlots, onClose, onTimeline, onSelectBooking,
}: {
  date: string;
  bookings: BookingRead[];
  slots: TimeSlotRead[];
  customerMap: Record<string, string>;
  onAction: (id: number, action: "confirm" | "complete" | "no-show" | "decline" | "cancel" | "approve-cancel" | "reject-cancel") => void;
  onBlockDate: () => void;
  onDeactivateSlots: (ids: number[]) => void;
  onClose: () => void;
  onTimeline: () => void;
  onSelectBooking: (b: BookingRead) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const jsDay = new Date(date + "T00:00:00").getDay();
  // JS getDay(): 0=일,1=월,...,6=토 / Python weekday(): 0=월,1=화,...,6=일
  const pyDay = (jsDay + 6) % 7;

  // 중복 시간대 제거 + 시간순 정렬
  const seen = new Set<string>();
  const daySlots = slots
    .filter(s => {
      if (!s.weekdays.includes(pyDay)) return false;
      const key = `${s.start_time}-${s.end_time}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => a.start_time.localeCompare(b.start_time));

  const [slotSelectMode, setSlotSelectMode] = useState(false);
  const [selectedSlotIds, setSelectedSlotIds] = useState<Set<number>>(new Set());

  function toggleSelect(id: number) {
    setSelectedSlotIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function exitSelectMode() {
    setSlotSelectMode(false);
    setSelectedSlotIds(new Set());
  }

  function handleComplete() {
    if (selectedSlotIds.size > 0) onDeactivateSlots(Array.from(selectedSlotIds));
    exitSelectMode();
  }

  return (
    <View style={dp.wrap}>
      <View style={dp.handle} />
      <View style={dp.header}>
        <Text style={dp.dateTitle}>{date} ({DAYS_KO[jsDay]})</Text>
        <View style={dp.headerRight}>
          <Pressable style={dp.timelineBtn} onPress={onTimeline}>
            <Text style={dp.timelineTxt}>타임라인 →</Text>
          </Pressable>
          <Pressable onPress={onClose} style={{ marginLeft: 12 }}>
            <Text style={dp.closeTxt}>✕</Text>
          </Pressable>
        </View>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        {/* 예약 목록 */}
        <Text style={dp.sectionTitle}>예약 ({bookings.length}건)</Text>
        {bookings.length === 0 ? (
          <Text style={dp.empty}>이 날 예약 없음</Text>
        ) : bookings.map(b => (
          <View key={b.id} style={[dp.bookCard, { borderLeftColor: STATUS_COLOR[b.status] ?? "#9ca3af" }]}>
            <View style={dp.bookTop}>
              <View style={[dp.badge, { backgroundColor: (STATUS_COLOR[b.status] ?? "#9ca3af") + "20" }]}>
                <Text style={[dp.badgeTxt, { color: STATUS_COLOR[b.status] ?? "#9ca3af" }]}>
                  {STATUS_LABEL[b.status] ?? b.status}
                </Text>
              </View>
              <Text style={dp.customerName}>{customerMap[b.guest_id] ?? b.guest_id.slice(0, 8)}</Text>
            </View>
            <Text style={dp.topic}>{b.topic ?? "-"}</Text>
            {b.status === "REQUESTED" && (
              <View style={dp.actions}>
                <Pressable style={[dp.actionBtn, { backgroundColor: "#3b82f6" }]} onPress={() => onAction(b.id, "confirm")}>
                  <Text style={dp.actionTxt}>확정</Text>
                </Pressable>
                <Pressable style={[dp.actionBtn, { backgroundColor: "#9ca3af" }]} onPress={() => onAction(b.id, "decline")}>
                  <Text style={dp.actionTxt}>거절</Text>
                </Pressable>
              </View>
            )}
            {b.status === "CANCEL_REQUESTED" && (
              <View>
                <Text style={dp.cancelReqTxt}>고객이 취소를 신청했습니다</Text>
                <View style={dp.actions}>
                  <Pressable style={[dp.actionBtn, { backgroundColor: "#ef4444" }]} onPress={() => onAction(b.id, "approve-cancel")}>
                    <Text style={dp.actionTxt}>취소 승인</Text>
                  </Pressable>
                  <Pressable style={[dp.actionBtn, { backgroundColor: "#3b82f6" }]} onPress={() => onAction(b.id, "reject-cancel")}>
                    <Text style={dp.actionTxt}>취소 거절</Text>
                  </Pressable>
                </View>
              </View>
            )}
            {b.status === "CONFIRMED" && date <= today && (
              <View style={dp.actions}>
                <Pressable style={[dp.actionBtn, { backgroundColor: "#16a34a" }]} onPress={() => onAction(b.id, "complete")}>
                  <Text style={dp.actionTxt}>완료</Text>
                </Pressable>
                <Pressable style={[dp.actionBtn, { backgroundColor: "#ef4444" }]} onPress={() => onAction(b.id, "no-show")}>
                  <Text style={dp.actionTxt}>노쇼</Text>
                </Pressable>
              </View>
            )}
            <Pressable style={dp.detailBtn} onPress={() => onSelectBooking(b)}>
              <Text style={dp.detailBtnTxt}>상세 보기</Text>
            </Pressable>
          </View>
        ))}

        {/* 타임슬롯 */}
        <View style={dp.slotHeader}>
          <Text style={dp.sectionTitle}>타임슬롯</Text>
          <View style={{ flexDirection: "row", gap: 8 }}>
            <Pressable style={dp.blockBtn} onPress={onBlockDate}>
              <Text style={dp.blockTxt}>휴일전환</Text>
            </Pressable>
            <Pressable style={dp.timeSelectBtn} onPress={() => setSlotSelectMode(true)}>
              <Text style={dp.timeSelectTxt}>시간 휴무 선택</Text>
            </Pressable>
          </View>
        </View>

        {daySlots.length === 0 ? (
          <Text style={dp.empty}>이 요일 슬롯 없음</Text>
        ) : daySlots.map(slot => (
          <View key={slot.id} style={dp.slotRow}>
            <Text style={dp.slotTime}>{fmtTime(slot.start_time)} ~ {fmtTime(slot.end_time)}</Text>
          </View>
        ))}
        <View style={{ height: 24 }} />
      </ScrollView>

      {/* 시간 휴무 선택 모달 - 배경 전체 차단 */}
      <Modal visible={slotSelectMode} transparent animationType="fade">
        <View style={dp.selectOverlay}>
          <View style={dp.selectSheet}>
            <View style={dp.selectHeader}>
              <Text style={dp.selectTitle}>시간 휴무 선택</Text>
              <View style={{ flexDirection: "row", gap: 8 }}>
                <Pressable style={dp.cancelSelectBtn} onPress={exitSelectMode}>
                  <Text style={dp.cancelSelectTxt}>취소</Text>
                </Pressable>
                <Pressable style={dp.completeBtn} onPress={handleComplete}>
                  <Text style={dp.completeBtnTxt}>완료{selectedSlotIds.size > 0 ? ` (${selectedSlotIds.size})` : ""}</Text>
                </Pressable>
              </View>
            </View>
            {daySlots.map(slot => (
              <Pressable
                key={slot.id}
                style={[dp.slotRow, selectedSlotIds.has(slot.id) && dp.slotRowSelected]}
                onPress={() => toggleSelect(slot.id)}
              >
                <View style={[dp.checkbox, selectedSlotIds.has(slot.id) && dp.checkboxOn]}>
                  {selectedSlotIds.has(slot.id) && <Text style={dp.checkmark}>✓</Text>}
                </View>
                <Text style={dp.slotTime}>{fmtTime(slot.start_time)} ~ {fmtTime(slot.end_time)}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      </Modal>
    </View>
  );
}

const dp = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20, paddingHorizontal: 20, paddingTop: 12, borderTopWidth: 1, borderTopColor: "#e5e7eb" },
  handle: { width: 36, height: 4, backgroundColor: "#d1d5db", borderRadius: 2, alignSelf: "center", marginBottom: 14 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  headerRight: { flexDirection: "row", alignItems: "center" },
  dateTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  timelineBtn: { backgroundColor: "#f0fdf4", paddingHorizontal: 10, paddingVertical: 5, borderRadius: 20 },
  timelineTxt: { fontSize: 12, color: "#16a34a", fontWeight: "600" },
  closeTxt: { fontSize: 16, color: "#9ca3af" },
  sectionTitle: { fontSize: 13, fontWeight: "600", color: "#6b7280", marginBottom: 8, marginTop: 4 },
  empty: { textAlign: "center", color: "#9ca3af", fontSize: 13, marginVertical: 12 },
  bookCard: { borderLeftWidth: 3, backgroundColor: "#f9fafb", borderRadius: 8, padding: 12, marginBottom: 8 },
  bookTop: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 4 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 20 },
  badgeTxt: { fontSize: 11, fontWeight: "600" },
  customerName: { fontSize: 14, fontWeight: "600", color: "#111" },
  topic: { fontSize: 13, color: "#6b7280", marginBottom: 6 },
  actions: { flexDirection: "row", gap: 8 },
  actionBtn: { flex: 1, padding: 8, borderRadius: 8, alignItems: "center" },
  actionTxt: { color: "#fff", fontSize: 13, fontWeight: "600" },
  cancelReqTxt: { fontSize: 12, color: "#c2410c", fontWeight: "600", marginBottom: 6, marginTop: 2 },
  detailBtn: { marginTop: 8, padding: 7, borderRadius: 8, borderWidth: 1, borderColor: "#e5e7eb", alignItems: "center" },
  detailBtnTxt: { fontSize: 12, color: "#6b7280", fontWeight: "600" },
  selectOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" },
  selectSheet: { backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, paddingBottom: 40 },
  selectHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  selectTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  slotHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 12, marginBottom: 8 },
  blockBtn: { backgroundColor: "#fef3c7", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  blockTxt: { fontSize: 12, color: "#92400e", fontWeight: "600" },
  timeSelectBtn: { backgroundColor: "#eff6ff", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  timeSelectTxt: { fontSize: 12, color: "#1d4ed8", fontWeight: "600" },
  cancelSelectBtn: { backgroundColor: "#e5e7eb", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  cancelSelectTxt: { fontSize: 12, color: "#374151", fontWeight: "600" },
  completeBtn: { backgroundColor: "#16a34a", paddingHorizontal: 12, paddingVertical: 4, borderRadius: 8 },
  completeBtnTxt: { fontSize: 12, color: "#fff", fontWeight: "700" },
  slotRow: { flexDirection: "row", alignItems: "center", backgroundColor: "#f9fafb", borderRadius: 8, padding: 12, marginBottom: 8 },
  slotRowSelected: { backgroundColor: "#dbeafe", borderWidth: 1.5, borderColor: "#3b82f6" },
  slotTime: { fontSize: 14, fontWeight: "600", color: "#111" },
  checkbox: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: "#d1d5db", backgroundColor: "#fff", alignItems: "center", justifyContent: "center", marginRight: 12 },
  checkboxOn: { borderColor: "#3b82f6", backgroundColor: "#3b82f6" },
  checkmark: { color: "#fff", fontSize: 14, fontWeight: "700", lineHeight: 17 },
});

// ─── TimelineView ───────────────────────────────────────
function TimelineView({
  date, bookings, slots, customerMap, onAction, onBack,
}: {
  date: string;
  bookings: BookingRead[];
  slots: TimeSlotRead[];
  customerMap: Record<string, string>;
  onAction: (id: number, action: "confirm" | "complete" | "no-show" | "decline" | "cancel") => void;
  onBack: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const dow = new Date(date + "T00:00:00").getDay();
  const daySlots = slots.filter(s => s.weekdays.includes(dow));
  const dayBookings = bookings.filter(b => b.when === date && b.status !== "CANCELLED");
  const timelineH = (END_H - START_H) * HOUR_H;

  type TlEvent = { id: string; top: number; height: number; label: string; color: string; bg: string };
  const events: TlEvent[] = [];

  dayBookings.forEach(b => {
    const slot = daySlots.find(s => s.id === b.time_slot_id);
    if (slot) {
      events.push({
        id: `b-${b.id}`,
        top: timeToY(slot.start_time),
        height: Math.max(timeDiff(slot.start_time, slot.end_time), HOUR_H * 0.5),
        label: `${fmtTime(slot.start_time)}~${fmtTime(slot.end_time)}  ${customerMap[b.guest_id] ?? ""} · ${b.topic ?? ""}`,
        color: STATUS_COLOR[b.status] ?? "#9ca3af",
        bg: (STATUS_COLOR[b.status] ?? "#9ca3af") + "18",
      });
    }
  });

  daySlots.forEach(slot => {
    const hasBk = dayBookings.some(b => b.time_slot_id === slot.id);
    if (!hasBk) {
      events.push({
        id: `s-${slot.id}`,
        top: timeToY(slot.start_time),
        height: Math.max(timeDiff(slot.start_time, slot.end_time), HOUR_H * 0.5),
        label: `${fmtTime(slot.start_time)}~${fmtTime(slot.end_time)}  ${slot.is_active ? "가용" : "비활성"}`,
        color: slot.is_active ? "#16a34a" : "#9ca3af",
        bg: slot.is_active ? "#f0fdf4" : "#f9fafb",
      });
    }
  });

  return (
    <View style={{ flex: 1, backgroundColor: "#fff" }}>
      <View style={tl.header}>
        <Pressable onPress={onBack} style={tl.backBtn}>
          <Text style={tl.backTxt}>‹ 달력</Text>
        </Pressable>
        <Text style={tl.headerTitle}>{date}</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView>
        {/* 예약 카드 목록 */}
        {dayBookings.length > 0 && (
          <View style={{ paddingHorizontal: 16, paddingTop: 12 }}>
            <Text style={tl.sectionTitle}>예약 목록</Text>
            {dayBookings.map(b => {
              const slot = daySlots.find(s => s.id === b.time_slot_id);
              return (
                <View key={b.id} style={[tl.bkCard, { borderLeftColor: STATUS_COLOR[b.status] ?? "#9ca3af" }]}>
                  <View style={tl.bkTop}>
                    <Text style={tl.bkName}>{customerMap[b.guest_id] ?? b.guest_id.slice(0, 8)}</Text>
                    <View style={[tl.badge, { backgroundColor: (STATUS_COLOR[b.status] ?? "#9ca3af") + "20" }]}>
                      <Text style={[tl.badgeTxt, { color: STATUS_COLOR[b.status] ?? "#9ca3af" }]}>
                        {STATUS_LABEL[b.status] ?? b.status}
                      </Text>
                    </View>
                  </View>
                  {slot && <Text style={tl.bkTime}>{fmtTime(slot.start_time)} ~ {fmtTime(slot.end_time)}</Text>}
                  <Text style={tl.bkTopic}>{b.topic ?? "-"}</Text>
                  {b.status === "REQUESTED" && (
                    <View style={tl.actions}>
                      <Pressable style={[tl.btn, { backgroundColor: "#3b82f6" }]} onPress={() => onAction(b.id, "confirm")}>
                        <Text style={tl.btnTxt}>확정</Text>
                      </Pressable>
                      <Pressable style={[tl.btn, { backgroundColor: "#9ca3af" }]} onPress={() => onAction(b.id, "decline")}>
                        <Text style={tl.btnTxt}>거절</Text>
                      </Pressable>
                    </View>
                  )}
                  {b.status === "CONFIRMED" && date <= today && (
                    <View style={tl.actions}>
                      <Pressable style={[tl.btn, { backgroundColor: "#16a34a" }]} onPress={() => onAction(b.id, "complete")}>
                        <Text style={tl.btnTxt}>완료</Text>
                      </Pressable>
                      <Pressable style={[tl.btn, { backgroundColor: "#ef4444" }]} onPress={() => onAction(b.id, "no-show")}>
                        <Text style={tl.btnTxt}>노쇼</Text>
                      </Pressable>
                    </View>
                  )}
                </View>
              );
            })}
          </View>
        )}

        {/* 타임라인 */}
        <Text style={[tl.sectionTitle, { paddingHorizontal: 16, paddingTop: 16 }]}>타임라인</Text>
        <View style={{ flexDirection: "row", paddingBottom: 20 }}>
          <View style={{ width: TIME_LABEL_W }}>
            {Array.from({ length: END_H - START_H }, (_, i) => (
              <View key={i} style={{ height: HOUR_H, justifyContent: "flex-start", paddingTop: 4, alignItems: "flex-end", paddingRight: 8 }}>
                <Text style={tl.timeLabel}>{String(START_H + i).padStart(2, "0")}:00</Text>
              </View>
            ))}
          </View>
          <View style={{ flex: 1, height: timelineH, position: "relative" }}>
            {Array.from({ length: END_H - START_H }, (_, i) => (
              <View key={i} style={[tl.hourLine, { top: i * HOUR_H }]} />
            ))}
            {events.map(ev => (
              <View key={ev.id} style={[tl.event, { top: ev.top, height: ev.height, backgroundColor: ev.bg, borderLeftColor: ev.color }]}>
                <Text style={[tl.eventLabel, { color: ev.color }]} numberOfLines={2}>{ev.label}</Text>
              </View>
            ))}
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const tl = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  backBtn: { width: 60 },
  backTxt: { fontSize: 15, color: "#16a34a", fontWeight: "600" },
  headerTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  sectionTitle: { fontSize: 13, fontWeight: "600", color: "#6b7280", marginBottom: 8 },
  bkCard: { borderLeftWidth: 3, backgroundColor: "#f9fafb", borderRadius: 8, padding: 12, marginBottom: 8 },
  bkTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 4 },
  bkName: { fontSize: 15, fontWeight: "700", color: "#111" },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 20 },
  badgeTxt: { fontSize: 11, fontWeight: "600" },
  bkTime: { fontSize: 12, color: "#6b7280", marginBottom: 2 },
  bkTopic: { fontSize: 13, color: "#374151" },
  actions: { flexDirection: "row", gap: 8, marginTop: 8 },
  btn: { flex: 1, padding: 8, borderRadius: 8, alignItems: "center" },
  btnTxt: { color: "#fff", fontSize: 13, fontWeight: "600" },
  timeLabel: { fontSize: 11, color: "#9ca3af" },
  hourLine: { position: "absolute", left: 0, right: 0, height: 1, backgroundColor: "#f3f4f6" },
  event: { position: "absolute", left: 4, right: 4, borderLeftWidth: 3, borderRadius: 6, padding: 6, overflow: "hidden" },
  eventLabel: { fontSize: 12, fontWeight: "500" },
});

// ─── Main ───────────────────────────────────────────────
type ConfirmState = { title: string; body: string; isDecline?: boolean; onConfirm: (reason?: string) => Promise<void> } | null;

export default function ScheduleScreen() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [selectedDate, setSelectedDate] = useState("");
  const [panelVisible, setPanelVisible] = useState(false);
  const [viewMode, setViewMode] = useState<"month" | "timeline">("month");
  const panelAnim = useRef(new Animated.Value(0)).current;
  const [loading, setLoading] = useState(true);
  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);
  const [declineReason, setDeclineReason] = useState("");

  const [bookings, setBookings] = useState<BookingRead[]>([]);
  const [slots, setSlots] = useState<TimeSlotRead[]>([]);
  const [customerMap, setCustomerMap] = useState<Record<string, string>>({});
  const [detailBooking, setDetailBooking] = useState<BookingRead | null>(null);
  const initialLoaded = useRef(false);
  const currentYear = useRef(year);
  const currentMonth = useRef(month);

  async function load(y = currentYear.current, m = currentMonth.current) {
    const start = new Date(y, m, 1).toISOString().slice(0, 10);
    const end = new Date(y, m + 1, 0).toISOString().slice(0, 10);
    const [bkRes, slRes, cuRes] = await Promise.allSettled([
      apiFetch<BookingRead[]>(`/calendars/me/bookings?start=${start}&end=${end}`),
      apiFetch<TimeSlotRead[]>("/calendars/me/time-slots"),
      apiFetch<UsersListResponse>("/users?limit=200"),
    ]);
    if (bkRes.status === "fulfilled") setBookings(Array.isArray(bkRes.value) ? bkRes.value : []);
    if (slRes.status === "fulfilled") setSlots(Array.isArray(slRes.value) ? slRes.value : []);
    if (cuRes.status === "fulfilled") {
      const map: Record<string, string> = {};
      cuRes.value.items.forEach(u => { map[u.id] = u.display_name; });
      setCustomerMap(map);
    }
    setLoading(false);
    initialLoaded.current = true;
  }

  useFocusEffect(useCallback(() => {
    if (!initialLoaded.current) setLoading(true);
    load();
  }, []));

  function prevMonth() {
    const nm = month === 0 ? 11 : month - 1;
    const ny = month === 0 ? year - 1 : year;
    setYear(ny); setMonth(nm);
    currentYear.current = ny; currentMonth.current = nm;
    load(ny, nm);
  }
  function nextMonth() {
    const nm = month === 11 ? 0 : month + 1;
    const ny = month === 11 ? year + 1 : year;
    setYear(ny); setMonth(nm);
    currentYear.current = ny; currentMonth.current = nm;
    load(ny, nm);
  }

  function openPanel(date: string) {
    setSelectedDate(date);
    setPanelVisible(true);
    panelAnim.setValue(PANEL_H);
    Animated.spring(panelAnim, { toValue: 0, useNativeDriver: true, tension: 65, friction: 11 }).start();
  }
  function closePanel() {
    Animated.timing(panelAnim, { toValue: PANEL_H, duration: 240, useNativeDriver: true }).start(() => setPanelVisible(false));
  }

  function doAction(bookingId: number, action: "confirm" | "complete" | "no-show" | "decline" | "cancel" | "approve-cancel" | "reject-cancel") {
    const labels: Record<string, string> = {
      confirm: "확정", complete: "완료 처리", "no-show": "노쇼 처리",
      decline: "거절", cancel: "취소", "approve-cancel": "취소 승인", "reject-cancel": "취소 거절",
    };
    setDeclineReason("");
    setConfirm({
      title: labels[action],
      body: "진행하시겠습니까?",
      isDecline: action === "decline",
      onConfirm: async (reason?: string) => {
        await apiFetch(`/calendars/me/bookings/${bookingId}/${action}`, {
          method: "PATCH",
          body: action === "decline" ? { reason: reason || null } : undefined,
        });
        await load();
      },
    });
  }

  function deactivateSlots(ids: number[]) {
    setConfirm({
      title: "시간 휴무 처리",
      body: `선택한 ${ids.length}개 슬롯을 비활성화하시겠습니까?`,
      onConfirm: async () => {
        await Promise.all(ids.map(id =>
          apiFetch(`/calendars/me/time-slots/${id}`, { method: "PATCH", body: { is_active: false } })
        ));
        await load();
      },
    });
  }

  function blockDate() {
    const activeSlot = slots.find(s => s.is_active);
    if (!activeSlot) { setInfoMsg("활성화된 타임슬롯이 없습니다."); return; }
    setConfirm({
      title: "휴무 등록",
      body: `${selectedDate}을 휴무로 등록하시겠습니까?`,
      onConfirm: async () => {
        await apiFetch("/bookings", { method: "POST", body: { time_slot_id: activeSlot.id, when: selectedDate, topic: "휴무", type: "HOLIDAY" } });
        await load();
      },
    });
  }

  const dayBookings = bookings.filter(b => b.when === selectedDate && b.status !== "CANCELLED");

  if (loading) {
    return <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}><ActivityIndicator size="large" color="#16a34a" /></View>;
  }

  if (viewMode === "timeline") {
    return (
      <TimelineView
        date={selectedDate}
        bookings={bookings}
        slots={slots}
        customerMap={customerMap}
        onAction={doAction}
        onBack={() => { setViewMode("month"); openPanel(selectedDate); }}
      />
    );
  }

  async function runConfirm() {
    if (!confirm) return;
    setConfirmLoading(true);
    try {
      await confirm.onConfirm(declineReason || undefined);
    } catch (e: unknown) {
      setInfoMsg(e instanceof Error ? e.message : "처리 실패");
    } finally {
      setConfirm(null);
      setDeclineReason("");
      setConfirmLoading(false);
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: "#fff" }}>
      {/* 확인 모달 */}
      <Modal visible={confirm !== null} transparent animationType="fade">
        <View style={cm.backdrop}>
          <View style={cm.sheet}>
            <Text style={cm.title}>{confirm?.title}</Text>
            {confirm?.isDecline ? (
              <>
                <Text style={cm.reasonLabel}>거절 사유 (선택)</Text>
                <TextInput
                  style={cm.reasonInput}
                  placeholder="사유를 입력하세요..."
                  value={declineReason}
                  onChangeText={setDeclineReason}
                  multiline
                  numberOfLines={3}
                />
              </>
            ) : (
              <Text style={cm.body}>{confirm?.body}</Text>
            )}
            <View style={cm.btnRow}>
              <Pressable style={[cm.btn, cm.cancelBtn]} onPress={() => { setConfirm(null); setDeclineReason(""); }} disabled={confirmLoading}>
                <Text style={cm.cancelTxt}>취소</Text>
              </Pressable>
              <Pressable style={[cm.btn, confirm?.isDecline ? cm.declineOkBtn : cm.okBtn]} onPress={runConfirm} disabled={confirmLoading}>
                {confirmLoading ? <ActivityIndicator color="#fff" size="small" /> : <Text style={cm.okTxt}>{confirm?.isDecline ? "거절 확정" : "확인"}</Text>}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
      {/* 안내 모달 */}
      <Modal visible={infoMsg !== null} transparent animationType="fade">
        <View style={cm.backdrop}>
          <View style={cm.sheet}>
            <Text style={cm.body}>{infoMsg}</Text>
            <Pressable style={[cm.btn, cm.okBtn, { alignSelf: "stretch" }]} onPress={() => setInfoMsg(null)}>
              <Text style={cm.okTxt}>확인</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingBottom: panelVisible ? PANEL_H + 16 : 0 }}
        scrollEnabled={panelVisible}
        showsVerticalScrollIndicator={false}
      >
        <View style={s.monthNav}>
          <Pressable onPress={prevMonth} style={s.navBtn}><Text style={s.navArrow}>‹</Text></Pressable>
          <Text style={s.monthTitle}>{year}년 {MONTHS[month]}</Text>
          <Pressable onPress={nextMonth} style={s.navBtn}><Text style={s.navArrow}>›</Text></Pressable>
        </View>
        <MonthGrid
          year={year} month={month}
          bookings={bookings}
          selectedDate={selectedDate}
          onSelect={openPanel}
          customerMap={customerMap}
        />
      </ScrollView>

      <BookingDetailModal
        visible={detailBooking !== null}
        booking={detailBooking}
        slots={slots}
        customerMap={customerMap}
        onClose={() => setDetailBooking(null)}
        onAction={(id, action) => { setDetailBooking(null); doAction(id, action); }}
      />

      {panelVisible && (
        <Animated.View style={[s.panelOverlay, { transform: [{ translateY: panelAnim }] }]}>
          <DayPanel
            date={selectedDate}
            bookings={dayBookings}
            slots={slots}
            customerMap={customerMap}
            onAction={doAction}
            onBlockDate={blockDate}
            onDeactivateSlots={deactivateSlots}
            onClose={closePanel}
            onTimeline={() => { closePanel(); setTimeout(() => setViewMode("timeline"), 260); }}
            onSelectBooking={(b) => { closePanel(); setTimeout(() => setDetailBooking(b), 260); }}
          />
        </Animated.View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  monthNav: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 20, paddingVertical: 14 },
  monthTitle: { fontSize: 18, fontWeight: "700", color: "#111" },
  navBtn: { padding: 8 },
  navArrow: { fontSize: 26, color: "#374151", lineHeight: 30 },
  panelOverlay: { position: "absolute", bottom: 0, left: 0, right: 0, height: PANEL_H },
});

// ─── 예약 상세 모달 ──────────────────────────────────────
function BookingDetailModal({ visible, booking, slots, customerMap, onClose, onAction }: {
  visible: boolean;
  booking: BookingRead | null;
  slots: TimeSlotRead[];
  customerMap: Record<string, string>;
  onClose: () => void;
  onAction: (id: number, action: "confirm" | "complete" | "no-show" | "decline" | "cancel" | "approve-cancel" | "reject-cancel") => void;
}) {
  if (!booking) return null;
  const today = new Date().toISOString().slice(0, 10);
  const jsDay = new Date(booking.when + "T00:00:00").getDay();
  const pyDay = (jsDay + 6) % 7;
  const slot = slots.find(s => s.id === booking.time_slot_id && s.weekdays.includes(pyDay));
  const customerName = customerMap[booking.guest_id] ?? booking.guest_id.slice(0, 8);
  const sc = STATUS_COLOR[booking.status] ?? "#9ca3af";

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet">
      <View style={bd.container}>
        <View style={bd.header}>
          <Text style={bd.title}>예약 상세</Text>
          <Pressable onPress={onClose} style={bd.closeBtn}>
            <Text style={bd.closeTxt}>✕</Text>
          </Pressable>
        </View>

        <ScrollView>
          <View style={bd.card}>
            <BdRow label="고객" value={customerName} />
            <BdRow label="날짜" value={booking.when} />
            {slot && <BdRow label="시간" value={`${fmtTime(slot.start_time)} ~ ${fmtTime(slot.end_time)}`} />}
            <BdRow label="수업 주제" value={booking.topic ?? "-"} />
            <BdRow label="종류" value={booking.type === "LESSON" ? "레슨" : booking.type} />
            <BdRow label="상태" value={STATUS_LABEL[booking.status] ?? booking.status} valueColor={sc} />
            {booking.description ? <BdRow label="메모" value={booking.description} /> : null}
            {booking.cancel_reason ? <BdRow label="취소 사유" value={booking.cancel_reason} valueColor="#ef4444" /> : null}
          </View>

          {booking.status === "REQUESTED" && (
            <View style={bd.actions}>
              <Pressable style={[bd.btn, { backgroundColor: "#3b82f6" }]} onPress={() => onAction(booking.id, "confirm")}>
                <Text style={bd.btnTxt}>확정</Text>
              </Pressable>
              <Pressable style={[bd.btn, { backgroundColor: "#9ca3af" }]} onPress={() => onAction(booking.id, "decline")}>
                <Text style={bd.btnTxt}>거절</Text>
              </Pressable>
            </View>
          )}
          {booking.status === "CANCEL_REQUESTED" && (
            <View>
              <Text style={bd.cancelReqTxt}>고객이 취소를 신청했습니다</Text>
              <View style={bd.actions}>
                <Pressable style={[bd.btn, { backgroundColor: "#ef4444" }]} onPress={() => onAction(booking.id, "approve-cancel")}>
                  <Text style={bd.btnTxt}>취소 승인</Text>
                </Pressable>
                <Pressable style={[bd.btn, { backgroundColor: "#3b82f6" }]} onPress={() => onAction(booking.id, "reject-cancel")}>
                  <Text style={bd.btnTxt}>취소 거절</Text>
                </Pressable>
              </View>
            </View>
          )}
          {booking.status === "CONFIRMED" && booking.when <= today && (
            <View style={bd.actions}>
              <Pressable style={[bd.btn, { backgroundColor: "#16a34a" }]} onPress={() => onAction(booking.id, "complete")}>
                <Text style={bd.btnTxt}>완료 처리</Text>
              </Pressable>
              <Pressable style={[bd.btn, { backgroundColor: "#ef4444" }]} onPress={() => onAction(booking.id, "no-show")}>
                <Text style={bd.btnTxt}>노쇼</Text>
              </Pressable>
            </View>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

function BdRow({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={bd.row}>
      <Text style={bd.rowLabel}>{label}</Text>
      <Text style={[bd.rowValue, valueColor ? { color: valueColor } : null]}>{value}</Text>
    </View>
  );
}

const bd = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", padding: 24 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 20 },
  title: { fontSize: 20, fontWeight: "700", color: "#111" },
  closeBtn: { padding: 4 },
  closeTxt: { fontSize: 18, color: "#9ca3af" },
  card: { backgroundColor: "#f9fafb", borderRadius: 12, paddingHorizontal: 16, marginBottom: 16 },
  row: { flexDirection: "row", paddingVertical: 13, borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  rowLabel: { width: 80, fontSize: 13, color: "#6b7280" },
  rowValue: { flex: 1, fontSize: 14, fontWeight: "500", color: "#111" },
  actions: { flexDirection: "row", gap: 10, marginBottom: 12 },
  btn: { flex: 1, padding: 14, borderRadius: 12, alignItems: "center" },
  btnTxt: { color: "#fff", fontWeight: "700", fontSize: 15 },
  cancelReqTxt: { fontSize: 13, color: "#c2410c", fontWeight: "600", marginBottom: 8, textAlign: "center" },
});

const cm = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.45)", alignItems: "center", justifyContent: "center" },
  sheet: { backgroundColor: "#fff", borderRadius: 16, padding: 24, width: 320, gap: 12 },
  title: { fontSize: 17, fontWeight: "700", color: "#111", textAlign: "center" },
  body: { fontSize: 14, color: "#374151", textAlign: "center", lineHeight: 21 },
  reasonLabel: { fontSize: 13, fontWeight: "600", color: "#374151" },
  reasonInput: { borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 10, padding: 12, fontSize: 14, color: "#111", minHeight: 80, textAlignVertical: "top" },
  btnRow: { flexDirection: "row", gap: 10, marginTop: 4 },
  btn: { flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: "center" },
  cancelBtn: { backgroundColor: "#f3f4f6" },
  cancelTxt: { color: "#374151", fontWeight: "600", fontSize: 14 },
  okBtn: { backgroundColor: "#2563eb" },
  declineOkBtn: { backgroundColor: "#ef4444" },
  okTxt: { color: "#fff", fontWeight: "700", fontSize: 14 },
});
