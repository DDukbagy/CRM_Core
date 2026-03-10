// app/(tabs)/schedule.tsx
import { useCallback, useEffect, useRef, useState } from "react";
import {
  View, Text, ScrollView, Pressable, TextInput, Alert,
  ActivityIndicator, Modal, Animated, Dimensions, StyleSheet,
  KeyboardAvoidingView, Platform,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UserRead, BookingRead, AvailabilityResponse, AvailabilitySlot, BookingCreate } from "@/types/api";

const { height: SCREEN_H, width: SCREEN_W } = Dimensions.get("window");
const CELL_SIZE = Math.floor((SCREEN_W) / 7);
const CELL_H = Math.floor((SCREEN_H - 180) / 6); // 6주 기준으로 화면 꽉 채우기
const PANEL_H = SCREEN_H * 0.44;
const DAYS_KO = ["일", "월", "화", "수", "목", "금", "토"];
const MONTHS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];

// 타임라인 설정
const START_H = 6;
const END_H = 22;
const HOUR_H = 64;
const TIME_LABEL_W = 52;

const STATUS_COLOR: Record<string, string> = {
  REQUESTED: "#f59e0b", CONFIRMED: "#10b981", CANCEL_REQUESTED: "#f97316",
  CANCELLED: "#ef4444", COMPLETED: "#6b7280",
};
const STATUS_LABEL: Record<string, string> = {
  REQUESTED: "신청됨", CONFIRMED: "확정", CANCEL_REQUESTED: "취소 신청중",
  CANCELLED: "취소됨", COMPLETED: "완료",
};
const CHIP_BG: Record<string, string> = {
  REQUESTED: "#fff7ed", CONFIRMED: "#f0fdf4", CANCEL_REQUESTED: "#fff7ed",
  CANCELLED: "#fef2f2", COMPLETED: "#f9fafb",
};

function bookingLabel(b: BookingRead): string {
  if (b.status === "REQUESTED") return "신청 대기중";
  if (b.status === "CANCELLED") return b.cancel_reason ?? "취소됨";
  return b.topic ?? "";
}

function toDateStr(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}
function parseTime(t: string) {
  const [h, m] = t.split(":").map(Number);
  return { h, m };
}
function timeToY(t: string) {
  const { h, m } = parseTime(t);
  return (h - START_H) * HOUR_H + (m / 60) * HOUR_H;
}
function timeDiff(start: string, end: string) {
  const s = parseTime(start), e = parseTime(end);
  return ((e.h - s.h) * 60 + (e.m - s.m)) / 60 * HOUR_H;
}
function fmtTime(t: string) { return t.slice(0, 5); }

// ─── 1. 월간 달력 그리드 ─────────────────────────────────
function MonthGrid({
  year, month, bookings, availability, selectedDate, onSelect,
}: {
  year: number; month: number;
  bookings: BookingRead[];
  availability: Record<string, AvailabilitySlot[]>;
  selectedDate: string;
  onSelect: (d: string) => void;
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
                {bk.slice(0, 2).map(b => (
                  <View key={b.id} style={[mg.chip, { backgroundColor: CHIP_BG[b.status] }]}>
                    <Text style={[mg.chipTxt, { color: STATUS_COLOR[b.status] }]} numberOfLines={1}>
                      {bookingLabel(b)}
                    </Text>
                  </View>
                ))}
                {bk.length > 2 && <Text style={mg.more}>+{bk.length - 2}</Text>}
                {availability[ds] && bk.length === 0 && (
                  <View style={mg.dot} />
                )}
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
  selectedWrap: { backgroundColor: "#3b82f6" },
  num: { fontSize: 12, fontWeight: "500", color: "#111" },
  whiteNum: { color: "#fff", fontWeight: "700" },
  chip: { borderRadius: 3, paddingHorizontal: 3, paddingVertical: 1, marginBottom: 1 },
  chipTxt: { fontSize: 9, fontWeight: "500" },
  more: { fontSize: 9, color: "#9ca3af" },
  dot: { width: 5, height: 5, borderRadius: 3, backgroundColor: "#3b82f6", marginTop: 1 },
});

// ─── 2. 날짜별 이벤트 목록 패널 ──────────────────────────
function DayPanel({
  date, bookings, slots, managerId, onAddSlot, onExpand, onClose, onSelectBooking,
}: {
  date: string;
  bookings: BookingRead[];
  slots: AvailabilitySlot[];
  managerId: string | null;
  onAddSlot: (slot: AvailabilitySlot) => void;
  onExpand: () => void;
  onClose: () => void;
  onSelectBooking: (b: BookingRead) => void;
}) {
  const [slotPickerVisible, setSlotPickerVisible] = useState(false);
  const today = new Date().toISOString().slice(0, 10);
  const isToday = date === today;
  const isPast = date < today;

  // 중복 시간대 제거 + 시간순 정렬
  const seen = new Set<string>();
  const uniqueSlots = slots
    .filter(s => {
      const key = `${s.start_time}-${s.end_time}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => a.start_time.localeCompare(b.start_time));

  function handleBookingPress() {
    if (uniqueSlots.length === 1) {
      onAddSlot(uniqueSlots[0]);
    } else {
      setSlotPickerVisible(v => !v);
    }
  }

  return (
    <View style={dp.wrap}>
      <View style={dp.handle} />
      <View style={dp.header}>
        <Text style={dp.dateTitle}>{date}</Text>
        <View style={dp.headerRight}>
          <Pressable style={dp.expandBtn} onPress={onExpand}>
            <Text style={dp.expandTxt}>타임라인 →</Text>
          </Pressable>
          <Pressable onPress={onClose} style={{ marginLeft: 12 }}>
            <Text style={dp.closeTxt}>✕</Text>
          </Pressable>
        </View>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} style={{ flex: 1 }}>
        {bookings.length === 0 && uniqueSlots.length === 0 ? (
          <Text style={dp.empty}>이 날은 예약 내역이 없습니다</Text>
        ) : null}

        {bookings.map(b => (
          <Pressable key={b.id} style={[dp.row, { borderLeftColor: STATUS_COLOR[b.status] }]} onPress={() => onSelectBooking(b)}>
            <View style={{ flex: 1 }}>
              <Text style={dp.topic}>{bookingLabel(b)}</Text>
              <Text style={dp.meta}>{b.type === "LESSON" ? "레슨" : "상담"}</Text>
            </View>
            <View style={[dp.badge, { backgroundColor: STATUS_COLOR[b.status] + "20" }]}>
              <Text style={[dp.badgeTxt, { color: STATUS_COLOR[b.status] }]}>
                {STATUS_LABEL[b.status]}
              </Text>
            </View>
          </Pressable>
        ))}

        {/* 시간대 선택 (슬롯 여러 개일 때 펼침) */}
        {slotPickerVisible && uniqueSlots.length > 1 && (
          <>
            <Text style={dp.slotTitle}>시간대 선택</Text>
            <View style={dp.slotsRow}>
              {uniqueSlots.map(slot => (
                <Pressable key={slot.time_slot_id} style={dp.slotChip} onPress={() => { setSlotPickerVisible(false); onAddSlot(slot); }}>
                  <Text style={dp.slotTime}>{fmtTime(slot.start_time)}</Text>
                  <Text style={dp.slotSub}>~ {fmtTime(slot.end_time)}</Text>
                </Pressable>
              ))}
            </View>
          </>
        )}
      </ScrollView>

      {/* 예약 신청 버튼 */}
      {isPast ? (
        <View style={dp.bookBtnDisabled}>
          <Text style={dp.bookBtnTxtDisabled}>지난 날짜입니다</Text>
        </View>
      ) : isToday ? (
        <View style={dp.bookBtnDisabled}>
          <Text style={dp.bookBtnTxtDisabled}>당일 예약은 불가능합니다</Text>
        </View>
      ) : !managerId ? (
        <View style={dp.bookBtnDisabled}>
          <Text style={dp.bookBtnTxtDisabled}>담당 강사가 지정되지 않았습니다</Text>
        </View>
      ) : uniqueSlots.length === 0 ? (
        <View style={dp.bookBtnDisabled}>
          <Text style={dp.bookBtnTxtDisabled}>강사의 레슨 없는 날입니다</Text>
        </View>
      ) : (
        <Pressable style={dp.bookBtn} onPress={handleBookingPress}>
          <Text style={dp.bookBtnTxt}>예약 신청</Text>
        </Pressable>
      )}
    </View>
  );
}

const dp = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20,
    paddingHorizontal: 20, paddingTop: 12,
    borderTopWidth: 1, borderTopColor: "#e5e7eb",
    elevation: 10,
  },
  handle: { width: 36, height: 4, backgroundColor: "#d1d5db", borderRadius: 2, alignSelf: "center", marginBottom: 14 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 14 },
  headerRight: { flexDirection: "row", alignItems: "center" },
  dateTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  expandBtn: { backgroundColor: "#f3f4f6", paddingHorizontal: 10, paddingVertical: 5, borderRadius: 20 },
  expandTxt: { fontSize: 12, color: "#374151", fontWeight: "600" },
  closeTxt: { fontSize: 16, color: "#9ca3af" },
  empty: { textAlign: "center", color: "#9ca3af", fontSize: 14, marginTop: 24 },
  row: {
    flexDirection: "row", alignItems: "center",
    borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 10,
    backgroundColor: "#f9fafb", borderRadius: 6, marginBottom: 8,
  },
  topic: { fontSize: 14, fontWeight: "600", color: "#111" },
  meta: { fontSize: 12, color: "#9ca3af", marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
  badgeTxt: { fontSize: 11, fontWeight: "600" },
  slotTitle: { fontSize: 12, fontWeight: "600", color: "#9ca3af", marginTop: 12, marginBottom: 8 },
  slotsRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  slotChip: { backgroundColor: "#eff6ff", borderWidth: 1, borderColor: "#bfdbfe", borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, alignItems: "center" },
  slotTime: { color: "#1d4ed8", fontSize: 13, fontWeight: "700" },
  slotSub: { color: "#3b82f6", fontSize: 10, marginTop: 1 },
  bookBtn: { marginTop: 12, marginBottom: 4, backgroundColor: "#1a1a1a", borderRadius: 12, paddingVertical: 14, alignItems: "center" },
  bookBtnDisabled: { marginTop: 12, marginBottom: 4, backgroundColor: "#f3f4f6", borderRadius: 12, paddingVertical: 14, alignItems: "center" },
  bookBtnTxt: { color: "#fff", fontSize: 15, fontWeight: "700" },
  bookBtnTxtDisabled: { color: "#9ca3af", fontSize: 14 },
});

// ─── 3. 타임라인 뷰 ─────────────────────────────────────
function TimelineView({
  year, month, selectedDate,
  bookings, availability, slotTimeMap,
  onSelectDate, onBack, onAddSlot, onSelectBooking,
}: {
  year: number; month: number; selectedDate: string;
  bookings: BookingRead[];
  availability: Record<string, AvailabilitySlot[]>;
  slotTimeMap: Record<number, { start_time: string; end_time: string }>;
  onSelectDate: (d: string) => void;
  onBack: () => void;
  onAddSlot: (slot: AvailabilitySlot) => void;
  onSelectBooking: (b: BookingRead) => void;
}) {
  // 해당 월의 모든 날짜
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const monthDates = Array.from({ length: daysInMonth }, (_, i) => {
    const d = new Date(year, month, i + 1);
    return d.toISOString().slice(0, 10);
  });

  const stripScrollRef = useRef<ScrollView>(null);
  const DAY_CELL_W = Math.floor(SCREEN_W / 7);

  // 선택 날짜로 자동 스크롤
  const selDay = new Date(selectedDate).getDate() - 1;
  const scrollToX = Math.max(0, selDay * DAY_CELL_W - SCREEN_W / 2 + DAY_CELL_W / 2);

  const today = new Date().toISOString().slice(0, 10);
  const dayBookings = bookings.filter(b => b.when === selectedDate && b.status !== "CANCELLED");
  const daySlots = availability[selectedDate] ?? [];
  const timelineH = (END_H - START_H) * HOUR_H;

  // 타임라인에 배치할 이벤트 (시간 알 수 있는 것만)
  type TlEvent = { id: string; top: number; height: number; label: string; color: string; bg: string };
  const events: TlEvent[] = [];

  // 내 예약
  dayBookings.forEach(b => {
    const st = slotTimeMap[b.time_slot_id];
    if (st) {
      events.push({
        id: `b-${b.id}`,
        top: timeToY(st.start_time),
        height: Math.max(timeDiff(st.start_time, st.end_time), HOUR_H * 0.5),
        label: `${fmtTime(st.start_time)}~${fmtTime(st.end_time)}  ${b.topic}`,
        color: STATUS_COLOR[b.status],
        bg: CHIP_BG[b.status],
      });
    }
  });

  // 가용 슬롯
  daySlots.forEach(slot => {
    events.push({
      id: `s-${slot.time_slot_id}`,
      top: timeToY(slot.start_time),
      height: Math.max(timeDiff(slot.start_time, slot.end_time), HOUR_H * 0.5),
      label: `${fmtTime(slot.start_time)}~${fmtTime(slot.end_time)}  예약 가능`,
      color: "#3b82f6",
      bg: "#eff6ff",
    });
  });

  return (
    <View style={{ flex: 1, backgroundColor: "#fff" }}>
      {/* 헤더 */}
      <View style={tl.header}>
        <Pressable onPress={onBack} style={tl.backBtn}>
          <Text style={tl.backTxt}>‹ 달력</Text>
        </Pressable>
        <Text style={tl.headerTitle}>
          {year}년 {MONTHS[month]}
        </Text>
        <View style={{ width: 60 }} />
      </View>

      {/* 월간 날짜 스트립 (가로 스크롤) */}
      <View style={tl.weekStrip}>
        <ScrollView
          ref={stripScrollRef}
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ paddingHorizontal: 8, alignItems: "center" }}
          onLayout={() => {
            stripScrollRef.current?.scrollTo({ x: scrollToX, animated: false });
          }}
        >
          {monthDates.map((ds) => {
            const d = new Date(ds);
            const dayNum = d.getDate();
            const dow = d.getDay();
            const isSelected = ds === selectedDate;
            const isToday = ds === today;
            const hasBk = bookings.some(b => b.when === ds && b.status !== "CANCELLED");
            return (
              <Pressable key={ds} style={[tl.weekCell, { width: DAY_CELL_W }]} onPress={() => onSelectDate(ds)}>
                <Text style={[tl.weekDay, dow === 0 && tl.sun, dow === 6 && tl.sat]}>{DAYS_KO[dow]}</Text>
                <View style={[tl.weekNumWrap, isSelected && tl.weekSelected, isToday && !isSelected && tl.weekToday]}>
                  <Text style={[tl.weekNum, (isSelected || isToday) && tl.weekNumW, dow === 0 && !isSelected && tl.sun, dow === 6 && !isSelected && tl.sat]}>
                    {dayNum}
                  </Text>
                </View>
                {hasBk && <View style={tl.weekDot} />}
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {/* 타임라인 */}
      <ScrollView style={{ flex: 1 }}>
        <View style={{ flexDirection: "row", paddingBottom: 20 }}>
          {/* 시간 레이블 */}
          <View style={{ width: TIME_LABEL_W }}>
            {Array.from({ length: END_H - START_H }, (_, i) => (
              <View key={i} style={{ height: HOUR_H, justifyContent: "flex-start", paddingTop: 4, alignItems: "flex-end", paddingRight: 8 }}>
                <Text style={tl.timeLabel}>{String(START_H + i).padStart(2, "0")}:00</Text>
              </View>
            ))}
          </View>

          {/* 이벤트 영역 */}
          <View style={{ flex: 1, height: timelineH, position: "relative" }}>
            {/* 시간선 */}
            {Array.from({ length: END_H - START_H }, (_, i) => (
              <View key={i} style={[tl.hourLine, { top: i * HOUR_H }]} />
            ))}

            {/* 이벤트 블록 */}
            {events.map(ev => (
              <Pressable
                key={ev.id}
                onPress={() => {
                  if (ev.id.startsWith("s-")) {
                    const slot = daySlots.find(s => ev.id === `s-${s.time_slot_id}`);
                    if (slot) onAddSlot(slot);
                  } else {
                    const bookingId = Number(ev.id.replace("b-", ""));
                    const booking = dayBookings.find(b => b.id === bookingId);
                    if (booking) onSelectBooking(booking);
                  }
                }}
                style={[tl.event, { top: ev.top, height: ev.height, backgroundColor: ev.bg, borderLeftColor: ev.color }]}
              >
                <Text style={[tl.eventLabel, { color: ev.color }]} numberOfLines={2}>{ev.label}</Text>
              </Pressable>
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
  backTxt: { fontSize: 15, color: "#3b82f6", fontWeight: "600" },
  headerTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  weekStrip: { flexDirection: "row", height: 58, borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  weekCell: { flex: 1, alignItems: "center", justifyContent: "center", gap: 2 },
  weekDay: { fontSize: 11, color: "#9ca3af", fontWeight: "600" },
  sun: { color: "#ef4444" },
  sat: { color: "#3b82f6" },
  weekNumWrap: { width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  weekSelected: { backgroundColor: "#3b82f6" },
  weekToday: { backgroundColor: "#1a1a1a" },
  weekNum: { fontSize: 14, fontWeight: "600", color: "#111" },
  weekNumW: { color: "#fff" },
  weekDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: "#3b82f6" },
  timeLabel: { fontSize: 11, color: "#9ca3af" },
  hourLine: { position: "absolute", left: 0, right: 0, height: 1, backgroundColor: "#f3f4f6" },
  event: {
    position: "absolute", left: 4, right: 4,
    borderLeftWidth: 3, borderRadius: 6,
    padding: 6, overflow: "hidden",
  },
  eventLabel: { fontSize: 12, fontWeight: "500" },
});

// ─── 메인 화면 ───────────────────────────────────────────
export default function ScheduleScreen() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [viewMode, setViewMode] = useState<"month" | "timeline">("month");

  const [managerId, setManagerId] = useState<string | null>(null);
  const [instructorName, setInstructorName] = useState<string | null>(null);
  const [availability, setAvailability] = useState<Record<string, AvailabilitySlot[]>>({});
  const [slotTimeMap, setSlotTimeMap] = useState<Record<number, { start_time: string; end_time: string }>>({});
  const [myBookings, setMyBookings] = useState<BookingRead[]>([]);
  const [loading, setLoading] = useState(true);
  const initialLoaded = useRef(false);
  const [detailBooking, setDetailBooking] = useState<BookingRead | null>(null);

  // 누적 슬롯 시간 정보 (월 이동해도 유지)
  const slotTimeAccum = useRef<Record<number, { start_time: string; end_time: string }>>({});
  const managerIdRef = useRef<string | null>(null);

  const [selectedDate, setSelectedDate] = useState("");
  const [panelVisible, setPanelVisible] = useState(false);
  const panelAnim = useRef(new Animated.Value(0)).current;

  // 예약 신청 모달
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<AvailabilitySlot | null>(null);
  const [descText, setDescText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 특정 월의 가용 슬롯 로드 (슬롯 시간 누적)
  async function loadAvailability(mgId: string, y: number, m: number) {
    const start = new Date(y, m, 1).toISOString().slice(0, 10);
    const end   = new Date(y, m + 1, 0).toISOString().slice(0, 10);
    try {
      const avail = await apiFetch<AvailabilityResponse>(
        `/calendars/${mgId}/availability?start=${start}&end=${end}`
      );
      const slotMap: Record<string, AvailabilitySlot[]> = {};
      avail.days.forEach((d: any) => {
        if (d.slots.length > 0) {
          slotMap[d.date] = d.slots;
          d.slots.forEach((s: AvailabilitySlot) => {
            slotTimeAccum.current[s.time_slot_id] = { start_time: s.start_time, end_time: s.end_time };
          });
        }
      });
      setAvailability(slotMap);
      setSlotTimeMap({ ...slotTimeAccum.current });
    } catch (e) { console.error("가용 슬롯 로딩 실패:", e); }
  }

  async function load() {
    try {
      const [me, bookings] = await Promise.all([
        apiFetch<UserRead>("/users/me"),
        apiFetch<BookingRead[]>("/bookings/me"),
      ]);
      setManagerId(me.manager_id ?? null);
      managerIdRef.current = me.manager_id ?? null;
      setMyBookings(Array.isArray(bookings) ? bookings : []);

      if (me.manager_id) {
        apiFetch<UserRead>(`/users/${me.manager_id}`)
          .then(i => { if (i?.display_name) setInstructorName(i.display_name); })
          .catch(() => {});
        await loadAvailability(me.manager_id, year, month);
      }
    } catch (e) { console.error("스케줄 로딩 실패:", e); }
    finally { setLoading(false); initialLoaded.current = true; }
  }

  useFocusEffect(useCallback(() => {
    if (!initialLoaded.current) setLoading(true);
    load();
  }, []));

  // 월 변경 시 해당 월 availability 재요청
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return; }
    if (managerIdRef.current) {
      loadAvailability(managerIdRef.current, year, month);
    }
  }, [year, month]);

  function openPanel(date: string) {
    setSelectedDate(date);
    setPanelVisible(true);
    panelAnim.setValue(PANEL_H);
    Animated.spring(panelAnim, { toValue: 0, useNativeDriver: true, tension: 65, friction: 11 }).start();
  }
  function closePanel() {
    Animated.timing(panelAnim, { toValue: PANEL_H, duration: 240, useNativeDriver: true })
      .start(() => setPanelVisible(false));
  }

  function openBookingModal(slot: AvailabilitySlot) {
    const today = new Date().toISOString().slice(0, 10);
    if (selectedDate <= today) {
      Alert.alert("알림", "당일 및 지난 날짜는 예약 신청이 불가합니다.");
      return;
    }
    setSelectedSlot(slot);
    setDescText("");
    setModalVisible(true);
  }

  async function submitBooking() {
    if (!selectedSlot || !selectedDate) return;
    setSubmitting(true);
    try {
      const body: BookingCreate = {
        time_slot_id: selectedSlot.time_slot_id,
        when: selectedDate,
        description: descText.trim() || undefined, type: "LESSON",
      };
      await apiFetch("/bookings", { method: "POST", body });
      Alert.alert("완료", "예약이 신청되었습니다.\n강사 수락 후 확정됩니다.");
      setModalVisible(false);
      load();
    } catch (e: any) {
      const detail = (e?.body as any)?.detail ?? e?.message ?? "예약 실패";
      Alert.alert("오류", typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally { setSubmitting(false); }
  }

  function prevMonth() { if (month === 0) { setYear(y => y - 1); setMonth(11); } else setMonth(m => m - 1); }
  function nextMonth() { if (month === 11) { setYear(y => y + 1); setMonth(0); } else setMonth(m => m + 1); }


  if (loading) return <View style={s.center}><ActivityIndicator size="large" /></View>;

  // ── 타임라인 뷰 (3번째 화면) ──
  if (viewMode === "timeline") {
    return (
      <>
        <TimelineView
          year={year} month={month} selectedDate={selectedDate}
          bookings={myBookings} availability={availability} slotTimeMap={slotTimeMap}
          onSelectDate={(d) => setSelectedDate(d)}
          onBack={() => { setViewMode("month"); openPanel(selectedDate); }}
          onAddSlot={(slot) => openBookingModal(slot)}
          onSelectBooking={(b) => setDetailBooking(b)}
        />
        <BookingModal
          visible={modalVisible} slot={selectedSlot} date={selectedDate}
          desc={descText} submitting={submitting}
          onDesc={setDescText}
          onClose={() => setModalVisible(false)} onSubmit={submitBooking}
        />
        <BookingDetailModal
          visible={detailBooking !== null}
          booking={detailBooking}
          slotTimeMap={slotTimeMap}
          instructorName={instructorName}
          onClose={() => setDetailBooking(null)}
          onCancelled={(id) => {
            setMyBookings(prev => prev.map(b => b.id === id ? { ...b, status: "CANCELLED" } : b));
            setDetailBooking(null);
          }}
          onUpdated={(updated) => {
            setMyBookings(prev => prev.map(b => b.id === updated.id ? updated : b));
            setDetailBooking(updated);
          }}
        />
      </>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: "#fff" }}>
      {/* 달력 영역 */}
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingBottom: panelVisible ? PANEL_H + 16 : 0 }}
        scrollEnabled={panelVisible}
        showsVerticalScrollIndicator={false}
      >
        {/* 월 네비 */}
        <View style={s.monthNav}>
          <Pressable onPress={prevMonth} style={s.navBtn}><Text style={s.navArrow}>‹</Text></Pressable>
          <Text style={s.monthTitle}>{year}년 {MONTHS[month]}</Text>
          <Pressable onPress={nextMonth} style={s.navBtn}><Text style={s.navArrow}>›</Text></Pressable>
        </View>

        <MonthGrid
          year={year} month={month}
          bookings={myBookings} availability={availability}
          selectedDate={selectedDate}
          onSelect={openPanel}
        />
      </ScrollView>

      {/* 날짜 패널 - 아래서 올라오는 오버레이 */}
      {panelVisible && (
        <Animated.View style={[s.panelOverlay, { transform: [{ translateY: panelAnim }] }]}>
          <DayPanel
            date={selectedDate}
            bookings={myBookings.filter(b => b.when === selectedDate)}
            slots={availability[selectedDate] ?? []}
            managerId={managerId}
            onAddSlot={(slot) => openBookingModal(slot)}
            onExpand={() => { closePanel(); setTimeout(() => setViewMode("timeline"), 260); }}
            onClose={closePanel}
            onSelectBooking={(b) => { closePanel(); setTimeout(() => setDetailBooking(b), 260); }}
          />
        </Animated.View>
      )}

      <BookingModal
        visible={modalVisible} slot={selectedSlot} date={selectedDate}
        desc={descText} submitting={submitting}
        onDesc={setDescText}
        onClose={() => setModalVisible(false)} onSubmit={submitBooking}
      />
      <BookingDetailModal
        visible={detailBooking !== null}
        booking={detailBooking}
        slotTimeMap={slotTimeMap}
        instructorName={instructorName}
        onClose={() => setDetailBooking(null)}
        onCancelled={(id) => {
          setMyBookings(prev => prev.map(b => b.id === id ? { ...b, status: "CANCELLED" } : b));
          setDetailBooking(null);
        }}
        onUpdated={(updated) => {
          setMyBookings(prev => prev.map(b => b.id === updated.id ? updated : b));
          setDetailBooking(updated);
        }}
      />
    </View>
  );
}

// ─── 예약 신청 모달 (공통) ───────────────────────────────
function BookingModal({ visible, slot, date, desc, submitting, onDesc, onClose, onSubmit }: {
  visible: boolean; slot: AvailabilitySlot | null; date: string;
  desc: string; submitting: boolean;
  onDesc: (v: string) => void;
  onClose: () => void; onSubmit: () => void;
}) {
  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet">
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={bm.wrap}>
          <Text style={bm.title}>예약 신청</Text>
          {date && slot && (
            <Text style={bm.meta}>
              {date} · {fmtTime(slot.start_time)} ~ {fmtTime(slot.end_time)}
            </Text>
          )}
          <Text style={bm.label}>강사에게 메모</Text>
          <TextInput
            value={desc} onChangeText={onDesc}
            placeholder="전달할 내용을 자유롭게 입력하세요" multiline numberOfLines={4}
            style={[bm.input, { height: 100, textAlignVertical: "top" }]}
          />
          <View style={bm.btns}>
            <Pressable style={bm.cancelBtn} onPress={onClose}>
              <Text style={bm.cancelTxt}>취소</Text>
            </Pressable>
            <Pressable style={[bm.submitBtn, submitting && { opacity: 0.6 }]} onPress={onSubmit} disabled={submitting}>
              <Text style={bm.submitTxt}>{submitting ? "신청 중..." : "예약 신청"}</Text>
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const bm = StyleSheet.create({
  wrap: { padding: 24, backgroundColor: "#fff" },
  title: { fontSize: 20, fontWeight: "700", color: "#111", marginBottom: 4 },
  meta: { fontSize: 14, color: "#6b7280", marginBottom: 20 },
  label: { fontSize: 13, fontWeight: "600", color: "#374151", marginBottom: 6, marginTop: 16 },
  input: { borderWidth: 1, borderColor: "#d1d5db", borderRadius: 10, padding: 12, fontSize: 15, backgroundColor: "#fff" },
  btns: { flexDirection: "row", gap: 12, marginTop: 32 },
  cancelBtn: { flex: 1, padding: 14, borderRadius: 10, borderWidth: 1, borderColor: "#d1d5db" },
  cancelTxt: { textAlign: "center", color: "#374151", fontWeight: "600" },
  submitBtn: { flex: 1, padding: 14, backgroundColor: "#1a1a1a", borderRadius: 10 },
  submitTxt: { textAlign: "center", color: "#fff", fontWeight: "600" },
});

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  monthNav: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 20, paddingVertical: 14 },
  monthTitle: { fontSize: 18, fontWeight: "700", color: "#111" },
  navBtn: { padding: 8 },
  navArrow: { fontSize: 26, color: "#374151", lineHeight: 30 },
  bookingBtn: {
    marginHorizontal: 16, marginBottom: 8,
    backgroundColor: "#1a1a1a", borderRadius: 10,
    paddingVertical: 10, alignItems: "center",
  },
  bookingBtnTxt: { color: "#fff", fontSize: 14, fontWeight: "700" },
  panelOverlay: { position: "absolute", bottom: 0, left: 0, right: 0, height: PANEL_H },
});

// ─── 예약 상세 모달 ──────────────────────────────────────
function BookingDetailModal({ visible, booking, slotTimeMap, instructorName, onClose, onCancelled, onUpdated }: {
  visible: boolean;
  booking: BookingRead | null;
  slotTimeMap: Record<number, { start_time: string; end_time: string }>;
  instructorName: string | null;
  onClose: () => void;
  onCancelled: (id: number) => void;
  onUpdated: (b: BookingRead) => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editTopic, setEditTopic] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [saving, setSaving] = useState(false);

  if (!booking) return null;

  const slot = slotTimeMap[booking.time_slot_id];
  const canWithdraw = booking.status === "REQUESTED";
  const canCancel = booking.status === "CONFIRMED";
  const canCancelRequest = booking.status === "CANCEL_REQUESTED";
  const canEdit = booking.status === "REQUESTED";

  function startEdit() {
    setEditTopic(booking!.topic);
    setEditDesc(booking!.description ?? "");
    setEditing(true);
  }

  async function saveEdit() {
    if (!editTopic.trim()) { Alert.alert("확인", "수업 주제를 입력해주세요."); return; }
    setSaving(true);
    try {
      const updated = await apiFetch<BookingRead>(`/bookings/${booking!.id}`, {
        method: "PATCH",
        body: { topic: editTopic.trim(), description: editDesc.trim() || null },
      });
      onUpdated(updated);
      setEditing(false);
    } catch (e: any) {
      Alert.alert("오류", e?.message ?? "수정에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  }

  async function handleAction() {
    const endpoint = canWithdraw
      ? `/bookings/${booking!.id}/withdraw`
      : `/bookings/${booking!.id}/cancel`;
    setSubmitting(true);
    try {
      const res = await apiFetch<{ id: number; status: string; updated_at: string }>(endpoint, { method: "PATCH" });
      if (res.status === "CANCELLED") {
        // 철회(withdraw) → 완전 취소
        onCancelled(res.id);
      } else {
        // 취소 신청(cancel) → CANCEL_REQUESTED 상태로 UI 갱신
        Alert.alert("알림", "취소 신청이 완료되었습니다.\n강사 승인 후 취소됩니다.");
        onUpdated({ ...booking!, status: res.status as BookingRead["status"], updated_at: res.updated_at });
      }
    } catch (e: any) {
      const msg = (e as any)?.body?.error?.message ?? (e as any)?.body?.detail ?? e?.message ?? "처리에 실패했습니다.";
      Alert.alert("오류", typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleWithdrawCancel() {
    setSubmitting(true);
    try {
      const res = await apiFetch<BookingRead>(`/bookings/${booking!.id}/withdraw-cancel`, { method: "PATCH" });
      onUpdated(res);
    } catch (e: any) {
      const msg = (e as any)?.body?.error?.message ?? (e as any)?.body?.detail ?? e?.message ?? "처리에 실패했습니다.";
      Alert.alert("오류", typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet">
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={dm.container}>
          <View style={dm.header}>
            <Text style={dm.title}>{editing ? "예약 수정" : "예약 상세"}</Text>
            <Pressable onPress={() => { setEditing(false); onClose(); }} style={dm.closeBtn}>
              <Text style={dm.closeTxt}>✕</Text>
            </Pressable>
          </View>

          {editing ? (
            /* ── 수정 폼 ── */
            <View style={dm.editForm}>
              <View style={dm.card}>
                <DetailRow label="날짜" value={booking.when} />
                {slot && (
                  <DetailRow label="시간" value={`${fmtTime(slot.start_time)} ~ ${fmtTime(slot.end_time)}`} />
                )}
              </View>
              <Text style={dm.editLabel}>수업 주제 *</Text>
              <TextInput
                value={editTopic}
                onChangeText={setEditTopic}
                placeholder="예: 드라이버 자세 교정"
                style={dm.editInput}
              />
              <Text style={dm.editLabel}>메모 (선택)</Text>
              <TextInput
                value={editDesc}
                onChangeText={setEditDesc}
                placeholder="강사에게 전달할 내용"
                multiline
                numberOfLines={3}
                style={[dm.editInput, { height: 80, textAlignVertical: "top" }]}
              />
              <View style={dm.editBtns}>
                <Pressable style={dm.editCancelBtn} onPress={() => setEditing(false)}>
                  <Text style={dm.editCancelTxt}>취소</Text>
                </Pressable>
                <Pressable
                  style={[dm.editSaveBtn, saving && { opacity: 0.6 }]}
                  onPress={saveEdit}
                  disabled={saving}
                >
                  <Text style={dm.editSaveTxt}>{saving ? "저장 중..." : "저장"}</Text>
                </Pressable>
              </View>
            </View>
          ) : (
            /* ── 상세 뷰 ── */
            <>
              <View style={dm.card}>
                <DetailRow label="주제" value={booking.topic} />
                <DetailRow label="날짜" value={booking.when} />
                {slot && (
                  <DetailRow label="시간" value={`${fmtTime(slot.start_time)} ~ ${fmtTime(slot.end_time)}`} />
                )}
                <DetailRow label="종류" value={booking.type === "LESSON" ? "레슨" : "상담"} />
                <DetailRow
                  label="상태"
                  value={STATUS_LABEL[booking.status] ?? booking.status}
                  valueColor={STATUS_COLOR[booking.status]}
                />
                {instructorName && <DetailRow label="담당 강사" value={instructorName} />}
                {booking.description ? <DetailRow label="메모" value={booking.description} /> : null}
                {booking.cancel_reason ? (
                  <DetailRow label="취소 사유" value={booking.cancel_reason} valueColor="#ef4444" />
                ) : null}
              </View>

              {canEdit && (
                <Pressable style={dm.editBtn} onPress={startEdit}>
                  <Text style={dm.editBtnTxt}>내용 수정</Text>
                </Pressable>
              )}

              {canCancelRequest && (
                <>
                  <View style={dm.cancelRequestedBox}>
                    <Text style={dm.cancelRequestedTxt}>취소 신청 중입니다 — 강사 승인 대기</Text>
                  </View>
                  <Pressable
                    style={[dm.withdrawCancelBtn, submitting && { opacity: 0.6 }]}
                    onPress={handleWithdrawCancel}
                    disabled={submitting}
                  >
                    <Text style={dm.withdrawCancelTxt}>{submitting ? "처리 중..." : "취소 신청 철회"}</Text>
                  </Pressable>
                </>
              )}
              {(canCancel || canWithdraw) && (
                <Pressable
                  style={[dm.actionBtn, submitting && { opacity: 0.6 }]}
                  onPress={handleAction}
                  disabled={submitting}
                >
                  <Text style={dm.actionTxt}>
                    {submitting ? "처리 중..." : canWithdraw ? "신청 철회" : "취소 신청"}
                  </Text>
                </Pressable>
              )}
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function DetailRow({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={dm.row}>
      <Text style={dm.rowLabel}>{label}</Text>
      <Text style={[dm.rowValue, valueColor ? { color: valueColor } : null]}>{value}</Text>
    </View>
  );
}

const dm = StyleSheet.create({
  container: { flexGrow: 1, backgroundColor: "#fff", padding: 24 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 24 },
  title: { fontSize: 20, fontWeight: "700", color: "#111" },
  closeBtn: { padding: 4 },
  closeTxt: { fontSize: 18, color: "#9ca3af" },
  card: { backgroundColor: "#f9fafb", borderRadius: 12, paddingHorizontal: 16, marginBottom: 16 },
  row: { flexDirection: "row", paddingVertical: 13, borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  rowLabel: { width: 80, fontSize: 13, color: "#6b7280" },
  rowValue: { flex: 1, fontSize: 14, fontWeight: "500", color: "#111" },
  editBtn: { backgroundColor: "#eff6ff", padding: 14, borderRadius: 12, marginBottom: 10 },
  editBtnTxt: { textAlign: "center", color: "#1d4ed8", fontWeight: "700", fontSize: 15 },
  actionBtn: { backgroundColor: "#fee2e2", padding: 14, borderRadius: 12 },
  actionTxt: { textAlign: "center", color: "#ef4444", fontWeight: "700", fontSize: 15 },
  cancelRequestedBox: { backgroundColor: "#fff7ed", borderWidth: 1, borderColor: "#f97316", borderRadius: 12, padding: 14, marginBottom: 8 },
  cancelRequestedTxt: { textAlign: "center", color: "#c2410c", fontWeight: "600", fontSize: 14 },
  withdrawCancelBtn: { backgroundColor: "#f3f4f6", padding: 14, borderRadius: 12, marginBottom: 10 },
  withdrawCancelTxt: { textAlign: "center", color: "#374151", fontWeight: "700", fontSize: 15 },
  editForm: { gap: 0 },
  editLabel: { fontSize: 13, fontWeight: "600", color: "#374151", marginBottom: 6, marginTop: 16 },
  editInput: { borderWidth: 1, borderColor: "#d1d5db", borderRadius: 10, padding: 12, fontSize: 15, backgroundColor: "#fff" },
  editBtns: { flexDirection: "row", gap: 10, marginTop: 24 },
  editCancelBtn: { flex: 1, padding: 14, borderRadius: 10, borderWidth: 1, borderColor: "#d1d5db" },
  editCancelTxt: { textAlign: "center", color: "#374151", fontWeight: "600" },
  editSaveBtn: { flex: 1, padding: 14, backgroundColor: "#1a1a1a", borderRadius: 10 },
  editSaveTxt: { textAlign: "center", color: "#fff", fontWeight: "600" },
});
