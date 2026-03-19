// app/(tabs)/schedule.tsx
import { useCallback, useEffect, useRef, useState } from "react";
import {
  View, Text, ScrollView, Pressable, TextInput, Alert,
  ActivityIndicator, Modal, Animated, Dimensions, StyleSheet,
  KeyboardAvoidingView, Platform, AppState, PanResponder,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UserRead, BookingRead, AvailabilityResponse, AvailabilitySlot, BookingCreate, CustomerPassRead } from "@/types/api";
import {
  STATUS_COLOR, STATUS_LABEL, CHIP_BG,
  toDateStr, fmtTime, parseTime, timeToY as _timeToY, timeDiff as _timeDiff,
  jsWeekdayToPy, isEffectiveOffDay, makeBookingGroups,
} from "@/lib/bookingUtils";

const { height: SCREEN_H, width: SCREEN_W } = Dimensions.get("window");
const CELL_SIZE = Math.floor((SCREEN_W) / 7);
const CELL_H = Math.floor((SCREEN_H - 250) / 6); // 살짝 작게
const GRID_H = CELL_H * 6 + 48; // 6주 + 헤더 충분히 포함
const DAYS_KO = ["일", "월", "화", "수", "목", "금", "토"];
const MONTHS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];

// 타임라인 설정
const START_H = 6;
const END_H = 22;
const HOUR_H = 64;
const TIME_LABEL_W = 52;

// bookingUtils에서 import: STATUS_COLOR, STATUS_LABEL, CHIP_BG, toDateStr, fmtTime, parseTime, makeBookingGroups

function bookingLabel(b: BookingRead): string {
  if (b.status === "REQUESTED") return "신청 대기중";
  if (b.status === "CANCELLED") return b.cancel_reason ?? "취소됨";
  return b.topic ?? "";
}

// START_H, HOUR_H를 사용하는 로컬 래퍼
const timeToY = (t: string) => _timeToY(t, START_H, HOUR_H);
const timeDiff = (start: string, end: string) => _timeDiff(start, end, HOUR_H);

// ─── 1. 월간 달력 그리드 ─────────────────────────────────
function MonthGrid({
  year, month, bookings, availability, selectedDate, onSelect, recurringOffDays, slotTimeMap, holidayDates,
}: {
  year: number; month: number;
  bookings: BookingRead[];
  availability: Record<string, AvailabilitySlot[]>;
  selectedDate: string;
  onSelect: (d: string) => void;
  recurringOffDays: number[];
  slotTimeMap: Record<number, { start_time: string; end_time: string }>;
  holidayDates: Set<string>;
}) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date().toISOString().slice(0, 10);

  const cells: (number | null)[] = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  while (cells.length < 42) cells.push(null); // 항상 6행
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
            const jsDay = new Date(ds + "T00:00:00").getDay();
            const pyDay = jsWeekdayToPy(jsDay);
            const isRecurringOff = recurringOffDays.includes(pyDay);
            const isHoliday = holidayDates.has(ds);
            const isEffectiveOff = isEffectiveOffDay({
              pyWeekday: pyDay,
              recurringOffDays,
              hasAvailability: !!availability[ds],
              hasBookings: bk.length > 0,
              isHoliday,
            });
            const sessions = makeBookingGroups(bk, slotTimeMap, false);
            return (
              <Pressable key={di} style={[mg.cell, isEffectiveOff && mg.offCell]} onPress={() => onSelect(ds)}>
                <View style={[mg.numWrap, isToday && mg.todayWrap, isSelected && mg.selectedWrap]}>
                  <Text style={[mg.num, di === 0 && mg.sun, di === 6 && mg.sat, (isToday || isSelected) && mg.whiteNum, isEffectiveOff && !isSelected && mg.offNum]}>
                    {day}
                  </Text>
                </View>
                {sessions.slice(0, 2).map((sess, si) => {
                  const b = sess.bookings[0];
                  return (
                    <View key={si} style={[mg.chip, { backgroundColor: CHIP_BG[b.status] }]}>
                      <Text style={[mg.chipTxt, { color: STATUS_COLOR[b.status] }]} numberOfLines={1}>
                        {bookingLabel(b)}
                      </Text>
                    </View>
                  );
                })}
                {sessions.length > 2 && <Text style={mg.more}>+{sessions.length - 2}</Text>}
                {bk.length === 0 && isEffectiveOff && (
                  <View style={mg.noLessonWrap}>
                    <Text style={mg.noLessonTxt}>{isHoliday ? "휴무" : "레슨없는날"}</Text>
                  </View>
                )}
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
  wrap: { flex: 1, backgroundColor: "#fff" },
  header: { flexDirection: "row" },
  dayLabel: { flex: 1, textAlign: "center", fontSize: 12, fontWeight: "600", color: "#9ca3af", paddingVertical: 8 },
  sun: { color: "#ef4444" },
  sat: { color: "#3b82f6" },
  week: { flex: 1, flexDirection: "row" },
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
  offCell: { backgroundColor: "#fff7ed" },
  offNum: { color: "#9ca3af" },
  noLessonWrap: { flex: 1, alignItems: "center", justifyContent: "center" },
  noLessonTxt: { fontSize: 9, fontWeight: "700", color: "#9ca3af", textAlign: "center" },
});

// ─── 2. 날짜별 패널 (타임라인 미리보기 + 수강권 기반 자동 슬롯 선택) ──────
function DayPanel({
  date, bookings, slots, managerId, activePass, slotTimeMap, onAddSlots, onClose, onSelectBooking,
}: {
  date: string;
  bookings: BookingRead[];
  slots: AvailabilitySlot[];
  managerId: string | null;
  activePass: CustomerPassRead | null;
  slotTimeMap: Record<number, { start_time: string; end_time: string }>;
  onAddSlots: (slots: AvailabilitySlot[]) => void;
  onClose: () => void;
  onSelectBooking: (b: BookingRead) => void;
}) {
  const [selectedSlotIds, setSelectedSlotIds] = useState<Set<number>>(new Set());
  const today = new Date().toISOString().slice(0, 10);
  const isToday = date === today;
  const isPast = date < today;
  const canBook = !isPast && !isToday && !!managerId;

  // 하루에 하나만 예약 가능 (취소된 예약 제외)
  const hasActiveBooking = bookings.some(
    b => b.status !== "CANCELLED"
  );

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

  // 날짜가 바뀌면 선택 초기화
  const prevDate = useRef(date);
  if (prevDate.current !== date) {
    prevDate.current = date;
    selectedSlotIds.clear();
  }

  // 수강권 기반 자동 슬롯 선택: 탭한 슬롯부터 duration_hours개 연속 선택
  const slotsPerLesson = activePass?.duration_hours ?? 1;

  function selectSlot(tappedId: number) {
    const idx = uniqueSlots.findIndex(s => s.time_slot_id === tappedId);
    if (idx === -1) return;
    // 이미 선택된 슬롯을 탭하면 해제
    if (selectedSlotIds.has(tappedId)) {
      setSelectedSlotIds(new Set());
      return;
    }
    // 앞으로 연속 슬롯 수집
    const forward: AvailabilitySlot[] = [uniqueSlots[idx]];
    for (let i = idx + 1; i < uniqueSlots.length && forward.length < slotsPerLesson; i++) {
      if (forward[forward.length - 1].end_time === uniqueSlots[i].start_time) {
        forward.push(uniqueSlots[i]);
      } else break;
    }
    // 앞이 부족하면 뒤로 채우기
    const backward: AvailabilitySlot[] = [];
    const needed = slotsPerLesson - forward.length;
    for (let i = idx - 1; i >= 0 && backward.length < needed; i--) {
      const anchor = backward.length === 0 ? uniqueSlots[idx] : backward[0];
      if (uniqueSlots[i].end_time === anchor.start_time) {
        backward.unshift(uniqueSlots[i]);
      } else break;
    }
    setSelectedSlotIds(new Set([...backward, ...forward].map(s => s.time_slot_id)));
  }

  function handleBook() {
    const toBook = uniqueSlots.filter(s => selectedSlotIds.has(s.time_slot_id));
    if (toBook.length === 0) return;
    onAddSlots(toBook);
  }

  // Group consecutive bookings into session rows
  const bkSorted = [...bookings].sort((a, b) =>
    (slotTimeMap[a.time_slot_id]?.start_time ?? "").localeCompare(slotTimeMap[b.time_slot_id]?.start_time ?? "")
  );
  type BkGroup = { bookings: BookingRead[]; startTime: string | null; endTime: string | null };
  const bookingGroups: BkGroup[] = [];
  let bgi = 0;
  while (bgi < bkSorted.length) {
    const cur = bkSorted[bgi];
    const curTimes = slotTimeMap[cur.time_slot_id];
    const group: BookingRead[] = [cur];
    let endT: string | null = curTimes?.end_time ?? null;
    let j = bgi + 1;
    while (j < bkSorted.length && endT) {
      const next = bkSorted[j];
      const nextTimes = slotTimeMap[next.time_slot_id];
      if (nextTimes?.start_time === endT) {
        group.push(next);
        endT = nextTimes?.end_time ?? null;
        j++;
      } else break;
    }
    bookingGroups.push({ bookings: group, startTime: curTimes?.start_time ?? null, endTime: endT });
    bgi = j;
  }

  const DAYS_KO_PANEL = ["일", "월", "화", "수", "목", "금", "토"];
  const jsDay = new Date(date + "T00:00:00").getDay();

  return (
    <View style={dp.wrap}>
      <View style={dp.header}>
        <View>
          <Text style={dp.dateTitle}>{date}</Text>
          <Text style={dp.dateSub}>{DAYS_KO_PANEL[jsDay]}요일</Text>
        </View>
        <Pressable onPress={onClose}>
          <Text style={dp.closeTxt}>✕</Text>
        </Pressable>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} style={{ flex: 1 }}>
        {/* 수강권 정보 카드 */}
        {activePass && (
          <View style={dp.passCard}>
            <View style={dp.passLeft}>
              <Text style={dp.passName}>{activePass.pass_name}</Text>
              <Text style={dp.passMeta}>
                회당 {activePass.duration_hours}시간 · 남은 {activePass.sessions_remaining}회
              </Text>
            </View>
            <View style={dp.passProgress}>
              <Text style={dp.passProgressTxt}>
                {activePass.sessions_used}/{activePass.sessions_total}회
              </Text>
            </View>
          </View>
        )}

        {/* 내 예약 현황 */}
        {bookingGroups.length > 0 && (
          <>
            <Text style={dp.sectionLabel}>내 예약</Text>
            {bookingGroups.map((group, gi) => {
              const b = group.bookings[0];
              const color = STATUS_COLOR[b.status];
              const timeLabel = group.startTime && group.endTime
                ? `${fmtTime(group.startTime)} ~ ${fmtTime(group.endTime)}${group.bookings.length > 1 ? ` · ${group.bookings.length}슬롯` : ""}`
                : (b.type === "LESSON" ? "레슨" : "상담");
              return (
                <Pressable key={`g-${gi}`} style={[dp.row, { borderLeftColor: color }]} onPress={() => onSelectBooking(b)}>
                  <View style={{ flex: 1 }}>
                    <Text style={dp.topic}>{bookingLabel(b)}</Text>
                    <Text style={dp.meta}>{timeLabel}</Text>
                  </View>
                  <View style={[dp.badge, { backgroundColor: color + "20" }]}>
                    <Text style={[dp.badgeTxt, { color }]}>
                      {STATUS_LABEL[b.status]}
                    </Text>
                  </View>
                </Pressable>
              );
            })}
          </>
        )}

        {/* 강사 스케줄 타임라인 미리보기 */}
        {uniqueSlots.length > 0 ? (
          <>
            <Text style={dp.sectionLabel}>
              {canBook && !hasActiveBooking
                ? `시간 선택 (${slotsPerLesson > 1 ? `${slotsPerLesson}개 자동 선택` : "1개 선택"})`
                : "강사 스케줄"}
            </Text>
            {uniqueSlots.map(slot => {
              const isSelected = selectedSlotIds.has(slot.time_slot_id);
              const interactive = canBook && !hasActiveBooking;
              return (
                <Pressable
                  key={slot.time_slot_id}
                  style={[dp.slotBlock, isSelected && dp.slotBlockSelected, !interactive && dp.slotBlockReadonly]}
                  onPress={() => interactive && selectSlot(slot.time_slot_id)}
                >
                  <View style={[dp.slotIndicator, isSelected && dp.slotIndicatorOn]} />
                  <View style={{ flex: 1 }}>
                    <Text style={[dp.slotTimeMain, isSelected && dp.slotTimeMainOn]}>
                      {fmtTime(slot.start_time)} ~ {fmtTime(slot.end_time)}
                    </Text>
                    <Text style={dp.slotAvail}>예약 가능</Text>
                  </View>
                  {interactive && (
                    <View style={[dp.slotCheck, isSelected && dp.slotCheckOn]}>
                      {isSelected && <Text style={dp.slotCheckTxt}>✓</Text>}
                    </View>
                  )}
                </Pressable>
              );
            })}
          </>
        ) : (
          <Text style={dp.empty}>
            {!managerId ? "담당 강사가 지정되지 않았습니다" : "강사의 레슨 없는 날입니다"}
          </Text>
        )}
        <View style={{ height: 8 }} />
      </ScrollView>

      {/* 예약 신청 버튼 */}
      {isPast ? (
        <View style={dp.bookBtnDisabled}><Text style={dp.bookBtnTxtDisabled}>지난 날짜입니다</Text></View>
      ) : isToday ? (
        <View style={dp.bookBtnDisabled}><Text style={dp.bookBtnTxtDisabled}>당일 예약은 불가능합니다</Text></View>
      ) : !managerId ? (
        <View style={dp.bookBtnDisabled}><Text style={dp.bookBtnTxtDisabled}>담당 강사가 지정되지 않았습니다</Text></View>
      ) : uniqueSlots.length === 0 ? (
        <View style={dp.bookBtnDisabled}><Text style={dp.bookBtnTxtDisabled}>강사의 레슨 없는 날입니다</Text></View>
      ) : hasActiveBooking ? (
        <View style={dp.bookBtnDisabled}><Text style={dp.bookBtnTxtDisabled}>이미 예약이 있습니다</Text></View>
      ) : selectedSlotIds.size === 0 ? (
        <View style={dp.bookBtnDisabled}><Text style={dp.bookBtnTxtDisabled}>시간을 선택해주세요</Text></View>
      ) : (
        <Pressable style={dp.bookBtn} onPress={handleBook}>
          <Text style={dp.bookBtnTxt}>
            {selectedSlotIds.size > 1
              ? `예약 신청 (${selectedSlotIds.size}시간 연속)`
              : "예약 신청"}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

const dp = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: "#fff",
    paddingHorizontal: 20, paddingTop: 10,
    borderTopWidth: 1, borderTopColor: "#e5e7eb",
  },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  dateTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  dateSub: { fontSize: 12, color: "#9ca3af", marginTop: 1 },
  closeTxt: { fontSize: 16, color: "#9ca3af" },
  empty: { textAlign: "center", color: "#9ca3af", fontSize: 14, marginTop: 24 },
  sectionLabel: { fontSize: 12, fontWeight: "600", color: "#6b7280", marginBottom: 8, marginTop: 4 },
  row: {
    flexDirection: "row", alignItems: "center",
    borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 10,
    backgroundColor: "#f9fafb", borderRadius: 6, marginBottom: 8,
  },
  topic: { fontSize: 14, fontWeight: "600", color: "#111" },
  meta: { fontSize: 12, color: "#9ca3af", marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
  badgeTxt: { fontSize: 11, fontWeight: "600" },
  slotBlock: {
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: "#eff6ff", borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1.5, borderColor: "#bfdbfe",
  },
  slotBlockSelected: { backgroundColor: "#dbeafe", borderColor: "#3b82f6" },
  slotBlockReadonly: { backgroundColor: "#f9fafb", borderColor: "#e5e7eb" },
  slotIndicator: { width: 4, height: 32, borderRadius: 2, backgroundColor: "#bfdbfe" },
  slotIndicatorOn: { backgroundColor: "#3b82f6" },
  slotTimeMain: { fontSize: 15, fontWeight: "700", color: "#1d4ed8" },
  slotTimeMainOn: { color: "#1e40af" },
  slotAvail: { fontSize: 11, color: "#3b82f6", marginTop: 2 },
  slotCheck: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: "#bfdbfe", alignItems: "center", justifyContent: "center" },
  slotCheckOn: { backgroundColor: "#3b82f6", borderColor: "#3b82f6" },
  slotCheckTxt: { color: "#fff", fontSize: 14, fontWeight: "700" },
  bookBtn: { marginTop: 8, marginBottom: 4, backgroundColor: "#1a1a1a", borderRadius: 12, paddingVertical: 14, alignItems: "center" },
  bookBtnDisabled: { marginTop: 8, marginBottom: 4, backgroundColor: "#f3f4f6", borderRadius: 12, paddingVertical: 14, alignItems: "center" },
  bookBtnTxt: { color: "#fff", fontSize: 15, fontWeight: "700" },
  bookBtnTxtDisabled: { color: "#9ca3af", fontSize: 14 },
  passCard: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: "#f0fdf4", borderRadius: 10, padding: 10, marginBottom: 10,
    borderWidth: 1, borderColor: "#bbf7d0",
  },
  passLeft: { flex: 1 },
  passName: { fontSize: 13, fontWeight: "700", color: "#15803d" },
  passMeta: { fontSize: 11, color: "#16a34a", marginTop: 2 },
  passProgress: { paddingHorizontal: 10, paddingVertical: 4, backgroundColor: "#dcfce7", borderRadius: 8 },
  passProgressTxt: { fontSize: 12, fontWeight: "700", color: "#15803d" },
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
  const router = useRouter();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  const [managerId, setManagerId] = useState<string | null>(null);
  const [instructorName, setInstructorName] = useState<string | null>(null);
  const [instructorRecurringOffDays, setInstructorRecurringOffDays] = useState<number[]>([]);
  const [availability, setAvailability] = useState<Record<string, AvailabilitySlot[]>>({});
  const [holidayDates, setHolidayDates] = useState<Set<string>>(new Set());
  const [slotTimeMap, setSlotTimeMap] = useState<Record<number, { start_time: string; end_time: string }>>({});
  const [myBookings, setMyBookings] = useState<BookingRead[]>([]);
  const [activePass, setActivePass] = useState<CustomerPassRead | null>(null);
  const [loading, setLoading] = useState(true);
  const initialLoaded = useRef(false);
  const [detailBooking, setDetailBooking] = useState<BookingRead | null>(null);

  // 누적 슬롯 시간 정보 (월 이동해도 유지)
  const slotTimeAccum = useRef<Record<number, { start_time: string; end_time: string }>>({});
  const managerIdRef = useRef<string | null>(null);
  const yearRef = useRef(year);
  const monthRef = useRef(month);
  yearRef.current = year;
  monthRef.current = month;

  const [noPassModalVisible, setNoPassModalVisible] = useState(false);

  const [selectedDate, setSelectedDate] = useState("");
  const [panelVisible, setPanelVisible] = useState(false);
  const calGridAnimH = useRef(new Animated.Value(GRID_H)).current;
  const gridAvailH = useRef(GRID_H);
  const weekStripScrollRef = useRef<ScrollView>(null);
  const DAY_CELL_W = Math.floor(SCREEN_W / 7);
  const isSwipingRef = useRef(false);

  // 예약 신청 모달
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedSlots, setSelectedSlots] = useState<AvailabilitySlot[]>([]);
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
      const holidays = new Set<string>();
      avail.days.forEach((d: any) => {
        if (d.slots.length > 0) {
          slotMap[d.date] = d.slots;
          d.slots.forEach((s: AvailabilitySlot) => {
            slotTimeAccum.current[s.time_slot_id] = { start_time: s.start_time, end_time: s.end_time };
          });
        }
        if (d.is_holiday) holidays.add(d.date);
      });
      setAvailability(slotMap);
      setHolidayDates(holidays);
      setSlotTimeMap({ ...slotTimeAccum.current });
    } catch { }
  }

  async function load() {
    try {
      const [me, bookings, passes] = await Promise.all([
        apiFetch<UserRead>("/users/me"),
        apiFetch<BookingRead[]>("/bookings/me"),
        apiFetch<CustomerPassRead[]>("/passes/me").catch(() => [] as CustomerPassRead[]),
      ]);
      setManagerId(me.manager_id ?? null);
      managerIdRef.current = me.manager_id ?? null;
      setMyBookings(Array.isArray(bookings) ? bookings : []);
      const p = Array.isArray(passes) ? passes.find(p => p.status === "ACTIVE") ?? null : null;
      setActivePass(p);

      if (me.manager_id) {
        apiFetch<UserRead>(`/users/${me.manager_id}`)
          .then(i => {
            if (i?.display_name) setInstructorName(i.display_name);
            setInstructorRecurringOffDays(i?.recurring_off_days ?? []);
          })
          .catch(() => {});
        // 강사 전체 슬롯을 미리 불러 slotTimeMap에 등록 (과거 예약 시간 표시용)
        apiFetch<{ id: number; start_time: string; end_time: string }[]>(
          `/calendars/${me.manager_id}/time-slots`
        )
          .then(instructorSlots => {
            instructorSlots.forEach(s => {
              slotTimeAccum.current[s.id] = { start_time: s.start_time, end_time: s.end_time };
            });
            setSlotTimeMap({ ...slotTimeAccum.current });
          })
          .catch(() => {});
        await loadAvailability(me.manager_id, yearRef.current, monthRef.current);
      }
    } catch { }
    finally { setLoading(false); initialLoaded.current = true; }
  }

  useFocusEffect(useCallback(() => {
    if (!initialLoaded.current) setLoading(true);
    load();
  }, []));

  // loadAvailability를 ref로 유지 — 클로저 stale 방지
  const loadAvailabilityRef = useRef(loadAvailability);
  loadAvailabilityRef.current = loadAvailability;

  // 탭 전환 or 앱 foreground 복귀 시 availability 재조회
  useEffect(() => {
    const refresh = () => {
      if (managerIdRef.current) {
        loadAvailabilityRef.current(managerIdRef.current, yearRef.current, monthRef.current);
      }
    };
    // Web: 브라우저 탭 전환
    if (typeof document !== "undefined") {
      const handler = () => { if (document.visibilityState === "visible") refresh(); };
      document.addEventListener("visibilitychange", handler);
      // Native fallback: AppState
      const sub = AppState.addEventListener("change", (s) => { if (s === "active") refresh(); });
      return () => {
        document.removeEventListener("visibilitychange", handler);
        sub.remove();
      };
    } else {
      const sub = AppState.addEventListener("change", (s) => { if (s === "active") refresh(); });
      return () => sub.remove();
    }
  }, []);

  // 월 변경 시 해당 월 availability 재요청
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return; }
    if (managerIdRef.current) {
      loadAvailability(managerIdRef.current, year, month);
    }
  }, [year, month]);

  // 날짜 변경 시 스트립 자동 스크롤
  useEffect(() => {
    if (!panelVisible || !selectedDate) return;
    const selDay = new Date(selectedDate + "T00:00:00").getDate() - 1;
    const scrollX = Math.max(0, selDay * DAY_CELL_W - SCREEN_W / 2 + DAY_CELL_W / 2);
    weekStripScrollRef.current?.scrollTo({ x: scrollX, animated: true });
  }, [selectedDate]);

  function openPanel(date: string) {
    const today = new Date().toISOString().slice(0, 10);
    // 미래 날짜이고, 강사 있고, 수강권 없으면 → 수강권 없음 모달
    if (date > today && managerIdRef.current && !activePass) {
      setNoPassModalVisible(true);
      return;
    }
    setSelectedDate(date);
    setPanelVisible(true);
    calGridAnimH.setValue(gridAvailH.current);
    Animated.timing(calGridAnimH, { toValue: 0, duration: 220, useNativeDriver: false }).start();
    if (managerIdRef.current) {
      loadAvailability(managerIdRef.current, yearRef.current, monthRef.current);
    }
  }
  function closePanel(onDone?: () => void) {
    Animated.timing(calGridAnimH, { toValue: gridAvailH.current, duration: 220, useNativeDriver: false }).start(() => {
      setPanelVisible(false);
      onDone?.();
    });
  }
  function prevMonthHandler() {
    if (panelVisible) {
      const newY = month === 0 ? year - 1 : year;
      const newM = month === 0 ? 11 : month - 1;
      setYear(newY); setMonth(newM);
      setSelectedDate(toDateStr(newY, newM, 1));
    } else { prevMonth(); }
  }
  function nextMonthHandler() {
    if (panelVisible) {
      const newY = month === 11 ? year + 1 : year;
      const newM = month === 11 ? 0 : month + 1;
      setYear(newY); setMonth(newM);
      setSelectedDate(toDateStr(newY, newM, 1));
    } else { nextMonth(); }
  }

  function openBookingModal(slots: AvailabilitySlot[]) {
    const today = new Date().toISOString().slice(0, 10);
    if (selectedDate <= today) {
      Alert.alert("알림", "당일 및 지난 날짜는 예약 신청이 불가합니다.");
      return;
    }
    if (slots.length === 0) return;
    setSelectedSlots(slots);
    setDescText("");
    setModalVisible(true);
  }

  async function submitBooking() {
    if (selectedSlots.length === 0 || !selectedDate) return;
    setSubmitting(true);
    try {
      await Promise.all(selectedSlots.map(slot => {
        const body: BookingCreate = {
          time_slot_id: slot.time_slot_id,
          when: selectedDate,
          description: descText.trim() || undefined,
          type: "LESSON",
        };
        return apiFetch("/bookings", { method: "POST", body });
      }));
      const msg = selectedSlots.length > 1
        ? `${selectedSlots.length}개 시간 예약이 신청되었습니다.\n강사 수락 후 확정됩니다.`
        : "예약이 신청되었습니다.\n강사 수락 후 확정됩니다.";
      Alert.alert("완료", msg);
      setModalVisible(false);
      load();
    } catch (e: any) {
      const detail = (e?.body as any)?.detail ?? e?.message ?? "예약 실패";
      Alert.alert("오류", typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally { setSubmitting(false); }
  }

  function prevMonth() { if (month === 0) { setYear(y => y - 1); setMonth(11); } else setMonth(m => m - 1); }
  function nextMonth() { if (month === 11) { setYear(y => y + 1); setMonth(0); } else setMonth(m => m + 1); }

  // 달력 스와이프 (이전달/다음달) — ref로 stale closure 방지
  const prevMonthRef = useRef(prevMonth);
  const nextMonthRef = useRef(nextMonth);
  const panelVisibleRef = useRef(panelVisible);
  prevMonthRef.current = prevMonth;
  nextMonthRef.current = nextMonth;
  panelVisibleRef.current = panelVisible;

  // 달력 슬라이드 애니메이션
  const calSlideX = useRef(new Animated.Value(0)).current;
  const prevGhostX = useRef(Animated.add(calSlideX, new Animated.Value(-SCREEN_W))).current;
  const nextGhostX = useRef(Animated.add(calSlideX, new Animated.Value(SCREEN_W))).current;
  // 이전달/다음달 계산
  const prevY = month === 0 ? year - 1 : year;
  const prevM = month === 0 ? 11 : month - 1;
  const nextY = month === 11 ? year + 1 : year;
  const nextM = month === 11 ? 0 : month + 1;

  const calendarPan = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, gs) =>
        !panelVisibleRef.current &&
        !isSwipingRef.current &&
        Math.abs(gs.dx) > 12 &&
        Math.abs(gs.dx) > Math.abs(gs.dy) * 1.5,
      onPanResponderMove: (_, gs) => {
        calSlideX.setValue(gs.dx * 0.92);
      },
      onPanResponderRelease: (_, gs) => {
        if (gs.dx > 60) {
          isSwipingRef.current = true;
          Animated.timing(calSlideX, { toValue: SCREEN_W, duration: 180, useNativeDriver: true })
            .start(() => { prevMonthRef.current(); calSlideX.setValue(0); isSwipingRef.current = false; });
        } else if (gs.dx < -60) {
          isSwipingRef.current = true;
          Animated.timing(calSlideX, { toValue: -SCREEN_W, duration: 180, useNativeDriver: true })
            .start(() => { nextMonthRef.current(); calSlideX.setValue(0); isSwipingRef.current = false; });
        } else {
          Animated.spring(calSlideX, { toValue: 0, useNativeDriver: true }).start();
        }
      },
    })
  ).current;


  if (loading) return <View style={s.center}><ActivityIndicator size="large" /></View>;

  const daysInMon = new Date(year, month + 1, 0).getDate();
  const todayStr = new Date().toISOString().slice(0, 10);

  return (
    <View style={{ flex: 1, backgroundColor: "#fff" }} {...calendarPan.panHandlers}>
      {/* 월 네비 */}
      <View style={s.monthNav}>
        <Pressable onPress={prevMonthHandler} style={s.navBtn}>
          <Text style={s.navArrow}>‹</Text>
        </Pressable>
        <Text style={s.monthTitle}>{year}년 {MONTHS[month]}</Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <Pressable onPress={nextMonthHandler} style={s.navBtn}><Text style={s.navArrow}>›</Text></Pressable>
          <Pressable onPress={() => router.push("/(tabs)/bookings")} style={s.bookingsBtn}>
            <Text style={s.bookingsBtnTxt}>예약목록</Text>
          </Pressable>
        </View>
      </View>

      {/* 달력 그리드 (날짜 선택 시 애니메이션으로 축소) */}
      <View
        style={{ flex: panelVisible ? 0 : 1 }}
        onLayout={(e) => {
          const h = e.nativeEvent.layout.height;
          if (h > 0 && !panelVisible) {
            gridAvailH.current = h;
            calGridAnimH.setValue(h);
          }
        }}
      >
      <Animated.View style={{ height: calGridAnimH, overflow: "hidden" }}>
        <View style={{ flex: 1, overflow: "hidden" }}>
          {/* 이전 달 ghost */}
          <Animated.View style={[StyleSheet.absoluteFill, { transform: [{ translateX: prevGhostX }] }]} pointerEvents="none">
            <MonthGrid
              year={prevY} month={prevM}
              bookings={myBookings} availability={availability}
              selectedDate={selectedDate}
              onSelect={openPanel}
              recurringOffDays={instructorRecurringOffDays}
              slotTimeMap={slotTimeMap}
              holidayDates={holidayDates}
            />
          </Animated.View>
          {/* 다음 달 ghost */}
          <Animated.View style={[StyleSheet.absoluteFill, { transform: [{ translateX: nextGhostX }] }]} pointerEvents="none">
            <MonthGrid
              year={nextY} month={nextM}
              bookings={myBookings} availability={availability}
              selectedDate={selectedDate}
              onSelect={openPanel}
              recurringOffDays={instructorRecurringOffDays}
              slotTimeMap={slotTimeMap}
              holidayDates={holidayDates}
            />
          </Animated.View>
          {/* 현재 달 */}
          <Animated.View style={{ flex: 1, transform: [{ translateX: calSlideX }] }}>
            <MonthGrid
              year={year} month={month}
              bookings={myBookings} availability={availability}
              selectedDate={selectedDate}
              onSelect={openPanel}
              recurringOffDays={instructorRecurringOffDays}
              slotTimeMap={slotTimeMap}
              holidayDates={holidayDates}
            />
          </Animated.View>
        </View>
      </Animated.View>
      </View>

      {/* 1열 날짜 스트립 + 상세 패널 */}
      {panelVisible && (
        <>
          {/* 날짜 스트립 */}
          <View style={s.weekStripWrap}>
            <ScrollView
              ref={weekStripScrollRef}
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={{ alignItems: "center" }}
              onLayout={() => {
                const selDay = new Date(selectedDate + "T00:00:00").getDate() - 1;
                const scrollX = Math.max(0, selDay * DAY_CELL_W - SCREEN_W / 2 + DAY_CELL_W / 2);
                weekStripScrollRef.current?.scrollTo({ x: scrollX, animated: false });
              }}
            >
              {Array.from({ length: daysInMon }, (_, i) => {
                const ds = toDateStr(year, month, i + 1);
                const dow = new Date(ds + "T00:00:00").getDay();
                const isSelected = ds === selectedDate;
                const isToday = ds === todayStr;
                const hasBk = myBookings.some(b => b.when === ds && b.status !== "CANCELLED");
                return (
                  <Pressable key={ds} style={[s.weekStripCell, { width: DAY_CELL_W }]} onPress={() => ds === selectedDate ? closePanel() : setSelectedDate(ds)}>
                    <Text style={[s.weekStripDayLabel, dow === 0 && { color: "#ef4444" }, dow === 6 && { color: "#3b82f6" }]}>
                      {DAYS_KO[dow]}
                    </Text>
                    <View style={[s.weekStripNumWrap, isSelected && s.weekStripSelected, isToday && !isSelected && s.weekStripToday]}>
                      <Text style={[s.weekStripNum, (isSelected || isToday) && { color: "#fff" }, dow === 0 && !isSelected && { color: "#ef4444" }, dow === 6 && !isSelected && { color: "#3b82f6" }]}>
                        {i + 1}
                      </Text>
                    </View>
                    {hasBk && <View style={s.weekStripDot} />}
                  </Pressable>
                );
              })}
            </ScrollView>
          </View>

          {/* 날짜 상세 패널 */}
          <DayPanel
            date={selectedDate}
            bookings={myBookings.filter(b => b.when === selectedDate)}
            slots={availability[selectedDate] ?? []}
            managerId={managerId}
            activePass={activePass}
            slotTimeMap={slotTimeMap}
            onAddSlots={(slots) => openBookingModal(slots)}
            onClose={() => closePanel()}
            onSelectBooking={(b) => closePanel(() => setDetailBooking(b))}
          />
        </>
      )}

      <BookingModal
        visible={modalVisible} slots={selectedSlots} date={selectedDate}
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

      {/* 수강권 없음 모달 */}
      <Modal
        visible={noPassModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setNoPassModalVisible(false)}
      >
        <View style={nm.overlay}>
          <View style={nm.card}>
            <Text style={nm.icon}>🎫</Text>
            <Text style={nm.title}>수강권이 없습니다</Text>
            <Text style={nm.desc}>예약을 신청하려면 먼저 수강권을 구매해주세요.</Text>
            <Pressable
              style={nm.payBtn}
              onPress={() => {
                setNoPassModalVisible(false);
                router.push("/(tabs)/passes");
              }}
            >
              <Text style={nm.payBtnTxt}>수강권 결제</Text>
            </Pressable>
            <Pressable style={nm.closeBtn} onPress={() => setNoPassModalVisible(false)}>
              <Text style={nm.closeBtnTxt}>닫기</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

// ─── 예약 신청 모달 (공통) ───────────────────────────────
function BookingModal({ visible, slots, date, desc, submitting, onDesc, onClose, onSubmit }: {
  visible: boolean; slots: AvailabilitySlot[]; date: string;
  desc: string; submitting: boolean;
  onDesc: (v: string) => void;
  onClose: () => void; onSubmit: () => void;
}) {
  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet">
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={bm.wrap}>
          <Text style={bm.title}>예약 신청</Text>
          {date && slots.length > 0 && (
            <Text style={bm.meta}>
              {date} · {slots.length === 1
                ? `${fmtTime(slots[0].start_time)} ~ ${fmtTime(slots[0].end_time)}`
                : `${fmtTime(slots[0].start_time)} ~ ${fmtTime(slots[slots.length - 1].end_time)} (${slots.length}개 시간)`}
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

const nm = StyleSheet.create({
  overlay: {
    flex: 1, backgroundColor: "rgba(0,0,0,0.5)",
    alignItems: "center", justifyContent: "center",
  },
  card: {
    backgroundColor: "#fff", borderRadius: 20, padding: 28,
    width: "80%", alignItems: "center", gap: 8,
    shadowColor: "#000", shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15, shadowRadius: 20, elevation: 10,
  },
  icon: { fontSize: 44, marginBottom: 4 },
  title: { fontSize: 20, fontWeight: "800", color: "#111" },
  desc: { fontSize: 14, color: "#6b7280", textAlign: "center", lineHeight: 20, marginBottom: 8 },
  payBtn: {
    width: "100%", backgroundColor: "#1a1a1a",
    borderRadius: 12, paddingVertical: 14, alignItems: "center",
  },
  payBtnTxt: { color: "#fff", fontSize: 15, fontWeight: "700" },
  closeBtn: { width: "100%", paddingVertical: 10, alignItems: "center" },
  closeBtnTxt: { fontSize: 14, color: "#9ca3af" },
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
  bookingsBtn: {
    backgroundColor: "#f3f4f6", paddingHorizontal: 9, paddingVertical: 5, borderRadius: 8,
  },
  bookingsBtnTxt: { fontSize: 11, color: "#374151", fontWeight: "600" },
  weekStripWrap: { borderBottomWidth: 1, borderBottomColor: "#e5e7eb", backgroundColor: "#fff" },
  weekStripCell: { alignItems: "center", paddingVertical: 6, gap: 3 },
  weekStripDayLabel: { fontSize: 10, color: "#9ca3af", fontWeight: "600" },
  weekStripNumWrap: { width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  weekStripSelected: { backgroundColor: "#3b82f6" },
  weekStripToday: { backgroundColor: "#1a1a1a" },
  weekStripNum: { fontSize: 14, fontWeight: "600", color: "#111" },
  weekStripDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: "#3b82f6" },
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
    setEditTopic(booking!.topic ?? "");
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
                <DetailRow label="주제" value={booking.topic ?? "-"} />
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
