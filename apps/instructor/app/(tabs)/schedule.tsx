import { useCallback, useRef, useState } from "react";
import {
  View, Text, ScrollView, Pressable, Modal, TextInput,
  Animated, Dimensions, StyleSheet, ActivityIndicator, PanResponder,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { BookingRead, TimeSlotRead, UserRead, UsersListResponse } from "@/types/api";
import {
  STATUS_COLOR, STATUS_LABEL,
  toDateStr, fmtTime, parseTime, timeToY as _timeToY, timeDiff as _timeDiff,
  jsWeekdayToPy, makeBookingGroups,
} from "@/lib/bookingUtils";

const { height: SCREEN_H, width: SCREEN_W } = Dimensions.get("window");
const CELL_H = Math.floor((SCREEN_H - 200) / 6);
const PANEL_H = SCREEN_H * 0.52;
const DAYS_KO = ["일", "월", "화", "수", "목", "금", "토"];
const MONTHS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];
const START_H = 6, END_H = 22, HOUR_H = 60, TIME_LABEL_W = 52;

// bookingUtils에서 import: STATUS_COLOR, STATUS_LABEL, toDateStr, fmtTime, parseTime, makeBookingGroups

// START_H, HOUR_H를 사용하는 로컬 래퍼
const timeToY = (t: string) => _timeToY(t, START_H, HOUR_H);
const timeDiff = (s: string, e: string) => _timeDiff(s, e, HOUR_H);

// ─── MonthGrid ──────────────────────────────────────────
function MonthGrid({
  year, month, bookings, selectedDate, onSelect, customerMap, recurringOffDays, slots,
}: {
  year: number; month: number;
  bookings: BookingRead[];
  selectedDate: string;
  onSelect: (d: string) => void;
  customerMap: Record<string, string>;
  recurringOffDays: number[];
  slots: { id: number; start_time: string; end_time: string }[];
}) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date().toISOString().slice(0, 10);
  const slotMap = Object.fromEntries(slots.map(s => [s.id, s])) as Record<number, { start_time: string; end_time: string }>;
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
            const jsDay = new Date(ds + "T00:00:00").getDay();
            const pyDay = jsWeekdayToPy(jsDay);
            const isRecurringOff = recurringOffDays.includes(pyDay);
            const bk = bookings.filter(b => b.when === ds);
            const isHoliday = !isRecurringOff && bk.some(b => b.type === "HOLIDAY" && b.status !== "CANCELLED");
            const hasWorkOverride = isRecurringOff && bk.some(b => b.type === "WORK_OVERRIDE" && b.status !== "CANCELLED");
            const regularBk = bk.filter(b => b.type !== "HOLIDAY" && b.type !== "WORK_OVERRIDE");
            const sessionGroups = makeBookingGroups(regularBk, slotMap);
            const isToday = ds === today;
            const isSelected = ds === selectedDate;
            return (
              <Pressable key={di} style={[mg.cell, (isHoliday || (isRecurringOff && !hasWorkOverride)) && mg.holidayCell]} onPress={() => onSelect(ds)}>
                <View style={[mg.numWrap, isToday && mg.todayWrap, isSelected && mg.selectedWrap]}>
                  <Text style={[mg.num, di === 0 && mg.sun, di === 6 && mg.sat, (isToday || isSelected) && mg.whiteNum]}>
                    {day}
                  </Text>
                </View>
                {isRecurringOff && !hasWorkOverride ? (
                  <View style={mg.noLessonWrap}>
                    <Text style={mg.noLessonTxt}>레슨없는날</Text>
                  </View>
                ) : isHoliday ? (
                  <View style={mg.holidayChip}>
                    <Text style={mg.holidayTxt}>휴무</Text>
                  </View>
                ) : null}
                {!isHoliday && !(isRecurringOff && !hasWorkOverride) && sessionGroups.slice(0, 2).map((g, gi) => {
                  const b = g.bookings[0];
                  const cname = customerMap[b.guest_id] ?? "예약";
                  const shortName = cname.length > 3 ? cname.slice(0, 3) : cname;
                  const isCancelled = g.bookings.every(bk => bk.status === "CANCELLED");
                  const rep = g.bookings.find(bk => bk.status !== "CANCELLED") ?? b;
                  const detail = isCancelled
                    ? (rep.cancel_reason ? rep.cancel_reason.slice(0, 4) : "거절")
                    : (rep.topic ? rep.topic.slice(0, 4) : null);
                  const label = detail ? `${shortName}·${detail}` : shortName;
                  const color = isCancelled ? "#9ca3af" : (STATUS_COLOR[rep.status] ?? "#9ca3af");
                  return (
                    <View key={gi} style={[mg.chip, { backgroundColor: color + "20", borderLeftColor: color, borderLeftWidth: 2 }]}>
                      <Text style={[mg.chipTxt, { color }]} numberOfLines={1}>{label}</Text>
                    </View>
                  );
                })}
                {!isHoliday && !(isRecurringOff && !hasWorkOverride) && sessionGroups.length > 2 && <Text style={mg.more}>+{sessionGroups.length - 2}</Text>}
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
  selectedWrap: { backgroundColor: "#16a34a" },
  num: { fontSize: 12, fontWeight: "500", color: "#111" },
  whiteNum: { color: "#fff", fontWeight: "700" },
  chip: { borderRadius: 3, paddingHorizontal: 4, paddingVertical: 1, marginBottom: 2 },
  chipTxt: { fontSize: 9, fontWeight: "700" },
  more: { fontSize: 9, color: "#9ca3af" },
  holidayCell: { backgroundColor: "#fff7ed" },
  holidayChip: { backgroundColor: "#fee2e2", borderRadius: 3, paddingHorizontal: 4, paddingVertical: 1, marginBottom: 2, alignSelf: "flex-start" },
  holidayTxt: { fontSize: 9, fontWeight: "700", color: "#dc2626" },
  noLessonWrap: { flex: 1, alignItems: "center", justifyContent: "center" },
  noLessonTxt: { fontSize: 9, fontWeight: "700", color: "#9ca3af", textAlign: "center" },
});

// ─── DayPanel ───────────────────────────────────────────
function DayPanel({
  date, bookings, slots, customerMap, isHoliday, isRecurringOff,
  workOverrideSlotIds,
  onAction, onBlockDate, onUnblockDate, onOverrideDay, onRestoreRecurring,
  onDeactivateSlots, onSaveActivation, onClose, onTimeline, onSelectBooking,
}: {
  date: string;
  bookings: BookingRead[];
  slots: TimeSlotRead[];
  customerMap: Record<string, string>;
  isHoliday: boolean;
  isRecurringOff: boolean;
  workOverrideSlotIds: Set<number>;
  onAction: (id: number, action: "confirm" | "complete" | "no-show" | "decline" | "cancel" | "approve-cancel" | "reject-cancel") => void;
  onBlockDate: () => void;
  onUnblockDate: () => void;
  onOverrideDay: () => void;
  onRestoreRecurring: () => void;
  onDeactivateSlots: (ids: number[]) => void;
  onSaveActivation: (toAdd: number[], toRemove: number[]) => void;
  onClose: () => void;
  onTimeline: () => void;
  onSelectBooking: (b: BookingRead) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const jsDay = new Date(date + "T00:00:00").getDay();
  const pyDay = jsWeekdayToPy(jsDay);

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

  const isBlocked = isHoliday || isRecurringOff;
  const hasWorkOverride = workOverrideSlotIds.size > 0;

  // 시간 휴무 선택 (일반 날)
  const [slotSelectMode, setSlotSelectMode] = useState(false);
  const [selectedSlotIds, setSelectedSlotIds] = useState<Set<number>>(new Set());

  function toggleSelect(id: number) {
    setSelectedSlotIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  function exitSelectMode() { setSlotSelectMode(false); setSelectedSlotIds(new Set()); }
  function handleDeactivateComplete() {
    if (selectedSlotIds.size > 0) onDeactivateSlots(Array.from(selectedSlotIds));
    exitSelectMode();
  }

  // 시간 활성화 (휴무/정기휴무 날)
  const [activateMode, setActivateMode] = useState(false);
  const [activateSelected, setActivateSelected] = useState<Set<number>>(new Set());

  function openActivateMode() {
    const initial = new Set(workOverrideSlotIds);
    // 예약/신청이 있는 슬롯은 항상 활성화 상태 유지
    activeBookingSlotIds.forEach(id => initial.add(id));
    setActivateSelected(initial);
    setActivateMode(true);
  }
  function toggleActivate(id: number) {
    setActivateSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  function handleActivateComplete() {
    const toAdd = daySlots.filter(s => activateSelected.has(s.id) && !workOverrideSlotIds.has(s.id)).map(s => s.id);
    // 예약/신청 있는 슬롯은 제거 불가
    const toRemove = daySlots.filter(s => !activateSelected.has(s.id) && workOverrideSlotIds.has(s.id) && !activeBookingSlotIds.has(s.id)).map(s => s.id);
    if (toAdd.length > 0 || toRemove.length > 0) onSaveActivation(toAdd, toRemove);
    setActivateMode(false);
  }

  // Session grouping
  const slotMapInst = Object.fromEntries(slots.map(s => [s.id, s])) as Record<number, { start_time: string; end_time: string }>;
  const activeBookings = bookings.filter(b => b.status !== "CANCELLED");
  const cancelledBookings = bookings.filter(b => b.status === "CANCELLED");
  const activeGroups = makeBookingGroups(activeBookings, slotMapInst);
  const cancelledGroups = makeBookingGroups(cancelledBookings, slotMapInst);

  const [bookingPage, setBookingPage] = useState(0);
  const bookScrollRef = useRef<ScrollView>(null);
  // 패널 paddingHorizontal: 20 → 사용가능 너비 = SCREEN_W - 40
  // PEEK: 양쪽 8px씩 이전/다음 탭 미리보기
  const PEEK = 8;
  const PAGE_W = SCREEN_W - 40 - PEEK * 2;

  // 탭 카테고리 — 지난날짜/오늘이후 구분
  const isPastDate = date < today;
  const pendingBookings = bookings.filter(b => b.status === "REQUESTED" || b.status === "CANCEL_REQUESTED");
  const confirmedBookings = bookings.filter(b => b.status === "CONFIRMED");
  const completedBookings = bookings.filter(b => b.status === "COMPLETED");
  const noShowBookings = bookings.filter(b => b.status === "NO_SHOW");
  const TABS = isPastDate ? [
    { label: "완료됨", data: completedBookings },
    { label: "노쇼", data: noShowBookings },
    { label: "취소됨", data: cancelledBookings },
  ] : [
    { label: "대기중", data: pendingBookings },
    { label: "확정", data: confirmedBookings },
    { label: "취소됨", data: cancelledBookings },
  ];

  // 확정/신청 예약이 있는 슬롯 ID (work override 복원 방지용)
  const activeBookingSlotIds = new Set(
    bookings.filter(b => b.status === "REQUESTED" || b.status === "CONFIRMED").map(b => b.time_slot_id)
  );
  const hasActiveBookingsOnDay = activeBookingSlotIds.size > 0;

  return (
    <View style={dp.wrap}>
      <View style={dp.handle} />
      <View style={dp.header}>
        <Text style={dp.dateTitle}>{date} ({DAYS_KO[jsDay]})</Text>
        <View style={dp.headerRight}>
          {!isHoliday && (!isRecurringOff || hasWorkOverride) && (
            <Pressable style={dp.timelineBtn} onPress={onTimeline}>
              <Text style={dp.timelineTxt}>타임라인 →</Text>
            </Pressable>
          )}
          <Pressable onPress={onClose} style={{ marginLeft: 12 }}>
            <Text style={dp.closeTxt}>✕</Text>
          </Pressable>
        </View>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        {/* 예약 섹션 헤더 + pill 탭 */}
        <View style={dp.bookingHeader}>
          <Text style={dp.sectionTitle}>예약</Text>
          <View style={dp.tabRow}>
            {TABS.map((tab, i) => (
              <Pressable
                key={i}
                style={[dp.tabPill, bookingPage === i && dp.tabPillActive]}
                onPress={() => {
                  bookScrollRef.current?.scrollTo({ x: i * PAGE_W, animated: true });
                  setBookingPage(i);
                }}
              >
                <Text style={[dp.tabPillTxt, bookingPage === i && dp.tabPillTxtActive]}>
                  {tab.label}{tab.data.length > 0 ? ` ${tab.data.length}` : ""}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        <ScrollView
            ref={bookScrollRef}
            horizontal
            pagingEnabled={false}
            snapToInterval={PAGE_W}
            decelerationRate="fast"
            showsHorizontalScrollIndicator={false}
            onMomentumScrollEnd={(e) => {
              setBookingPage(Math.round(e.nativeEvent.contentOffset.x / PAGE_W));
            }}
            contentContainerStyle={{ paddingHorizontal: PEEK }}
          >
            {TABS.map((tab, ti) => {
              const groups = makeBookingGroups(tab.data, slotMapInst);
              return (
                <View key={ti} style={{ width: PAGE_W, minHeight: 80 }}>
                  {groups.length === 0 ? (
                    <Text style={dp.empty}>{tab.label} 예약 없음</Text>
                  ) : groups.map((group, gi) => {
                    const b = group.bookings[0];
                    const isCancelled = ti === 2;
                    const color = isCancelled ? "#9ca3af" : (STATUS_COLOR[b.status] ?? "#9ca3af");
                    return (
                      <View key={`${ti}-${gi}`} style={[dp.bookCard, { borderLeftColor: color, opacity: isCancelled ? 0.65 : 1 }]}>
                        <View style={dp.bookTop}>
                          <View style={[dp.badge, { backgroundColor: color + "20" }]}>
                            <Text style={[dp.badgeTxt, { color }]}>{STATUS_LABEL[b.status] ?? b.status}</Text>
                          </View>
                          <Text style={[dp.customerName, isCancelled && { color: "#9ca3af" }]}>{customerMap[b.guest_id] ?? b.guest_id.slice(0, 8)}</Text>
                        </View>
                        {group.startTime && group.endTime && (
                          <Text style={[dp.bookTime, isCancelled && { color: "#9ca3af" }]}>{fmtTime(group.startTime)} ~ {fmtTime(group.endTime)}</Text>
                        )}
                        {b.topic ? <Text style={[dp.topic, isCancelled && { color: "#9ca3af" }]}>{b.topic}</Text> : null}
                        {isCancelled && b.cancel_reason && (
                          <Text style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>사유: {b.cancel_reason}</Text>
                        )}
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
                        {!isCancelled && (
                          <Pressable style={dp.detailBtn} onPress={() => onSelectBooking(b)}>
                            <Text style={dp.detailBtnTxt}>상세 보기</Text>
                          </Pressable>
                        )}
                      </View>
                    );
                  })}
                </View>
              );
            })}
          </ScrollView>

        {/* 타임슬롯 */}
        <View style={dp.slotHeader}>
          <Text style={dp.sectionTitle}>타임슬롯</Text>
          <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
            {/* 일반 날 */}
            {!isBlocked && !isPastDate && (
              <>
                <Pressable style={dp.blockBtn} onPress={onBlockDate}>
                  <Text style={dp.blockTxt}>휴일전환</Text>
                </Pressable>
                <Pressable style={dp.timeSelectBtn} onPress={() => setSlotSelectMode(true)}>
                  <Text style={dp.timeSelectTxt}>시간 휴무 선택</Text>
                </Pressable>
              </>
            )}
            {/* 휴무 날 */}
            {isHoliday && !isPastDate && (
              <Pressable style={dp.unblockBtn} onPress={onUnblockDate}>
                <Text style={dp.unblockTxt}>영업일전환</Text>
              </Pressable>
            )}
            {/* 정기 휴무 날 */}
            {isRecurringOff && !hasWorkOverride && !isPastDate && (
              <Pressable style={dp.overrideBtn} onPress={onOverrideDay}>
                <Text style={dp.overrideTxt}>이번만 전체영업</Text>
              </Pressable>
            )}
            {isRecurringOff && hasWorkOverride && !hasActiveBookingsOnDay && !isPastDate && (
              <Pressable style={dp.unblockBtn} onPress={onRestoreRecurring}>
                <Text style={dp.unblockTxt}>영업일전환 취소</Text>
              </Pressable>
            )}
            {/* 시간 활성화 — 휴무/정기휴무 공통 */}
            {isBlocked && !isPastDate && (
              <Pressable style={dp.activateBtn} onPress={openActivateMode}>
                <Text style={dp.activateTxt}>시간 활성화</Text>
              </Pressable>
            )}
          </View>
        </View>

        {isHoliday && (
          <View style={dp.holidayBanner}>
            <Text style={dp.holidayBannerTxt}>🔴 휴무일 {hasWorkOverride ? `— ${workOverrideSlotIds.size}개 시간 활성화됨` : "— 시간 활성화로 특정 시간만 열 수 있습니다"}</Text>
          </View>
        )}
        {isRecurringOff && (
          <View style={[dp.holidayBanner, { backgroundColor: hasWorkOverride ? "#f0fdf4" : "#f3f4f6" }]}>
            <Text style={[dp.holidayBannerTxt, { color: hasWorkOverride ? "#16a34a" : "#6b7280" }]}>
              {hasWorkOverride ? `✅ ${workOverrideSlotIds.size}개 시간 활성화됨` : "⛔ 정기 휴무 요일 — 시간 활성화로 특정 시간만 열 수 있습니다"}
            </Text>
          </View>
        )}

        {daySlots.length === 0 ? (
          <Text style={dp.empty}>이 요일 슬롯 없음</Text>
        ) : daySlots.map(slot => {
          const activated = workOverrideSlotIds.has(slot.id);
          return (
            <View key={slot.id} style={[dp.slotRow, isBlocked && !activated && dp.slotRowBlocked, isBlocked && activated && dp.slotRowActivated]}>
              <Text style={[dp.slotTime, isBlocked && !activated && dp.slotTimeInactive]}>
                {fmtTime(slot.start_time)} ~ {fmtTime(slot.end_time)}
              </Text>
              {isBlocked && activated && (
                <View style={dp.activatedBadge}>
                  <Text style={dp.activatedTxt}>활성화됨</Text>
                </View>
              )}
              {isBlocked && !activated && (
                <View style={dp.inactiveBadge}>
                  <Text style={dp.inactiveTxt}>차단됨</Text>
                </View>
              )}
              {!isBlocked && !slot.is_active && (
                <View style={dp.inactiveBadge}>
                  <Text style={dp.inactiveTxt}>비활성</Text>
                </View>
              )}
            </View>
          );
        })}
        <View style={{ height: 24 }} />
      </ScrollView>

      {/* 시간 휴무 선택 모달 (일반 날) */}
      <Modal visible={slotSelectMode} transparent animationType="fade">
        <View style={dp.selectOverlay}>
          <View style={dp.selectSheet}>
            <View style={dp.selectHeader}>
              <Text style={dp.selectTitle}>시간 휴무 선택</Text>
              <View style={{ flexDirection: "row", gap: 8 }}>
                <Pressable style={dp.cancelSelectBtn} onPress={exitSelectMode}>
                  <Text style={dp.cancelSelectTxt}>취소</Text>
                </Pressable>
                <Pressable style={dp.completeBtn} onPress={handleDeactivateComplete}>
                  <Text style={dp.completeBtnTxt}>완료{selectedSlotIds.size > 0 ? ` (${selectedSlotIds.size})` : ""}</Text>
                </Pressable>
              </View>
            </View>
            {daySlots.map(slot => (
              <Pressable
                key={slot.id}
                style={[dp.slotRow, selectedSlotIds.has(slot.id) && dp.slotRowSelected, !slot.is_active && dp.slotRowInactive]}
                onPress={() => slot.is_active && toggleSelect(slot.id)}
              >
                <View style={[dp.checkbox, selectedSlotIds.has(slot.id) && dp.checkboxOn]}>
                  {selectedSlotIds.has(slot.id) && <Text style={dp.checkmark}>✓</Text>}
                </View>
                <Text style={[dp.slotTime, !slot.is_active && dp.slotTimeInactive]}>
                  {fmtTime(slot.start_time)} ~ {fmtTime(slot.end_time)}
                </Text>
                {!slot.is_active && <View style={dp.inactiveBadge}><Text style={dp.inactiveTxt}>이미 비활성</Text></View>}
              </Pressable>
            ))}
          </View>
        </View>
      </Modal>

      {/* 시간 활성화 모달 (휴무/정기휴무 날) */}
      <Modal visible={activateMode} transparent animationType="fade">
        <View style={dp.selectOverlay}>
          <View style={dp.selectSheet}>
            <View style={dp.selectHeader}>
              <Text style={dp.selectTitle}>시간 활성화</Text>
              <Text style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>레슨을 열 시간을 선택하세요</Text>
              <View style={{ flexDirection: "row", gap: 8 }}>
                <Pressable style={dp.cancelSelectBtn} onPress={() => setActivateMode(false)}>
                  <Text style={dp.cancelSelectTxt}>취소</Text>
                </Pressable>
                <Pressable style={dp.completeBtn} onPress={handleActivateComplete}>
                  <Text style={dp.completeBtnTxt}>저장 ({activateSelected.size})</Text>
                </Pressable>
              </View>
            </View>
            {daySlots.map(slot => {
              const isOn = activateSelected.has(slot.id);
              const hasBooking = activeBookingSlotIds.has(slot.id);
              return (
                <Pressable
                  key={slot.id}
                  style={[dp.slotRow, isOn && dp.slotRowActivated]}
                  onPress={() => !hasBooking && toggleActivate(slot.id)}
                >
                  <View style={[dp.checkbox, isOn && dp.checkboxGreen]}>
                    {isOn && <Text style={dp.checkmark}>✓</Text>}
                  </View>
                  <Text style={[dp.slotTime, !isOn && { color: "#9ca3af" }]}>
                    {fmtTime(slot.start_time)} ~ {fmtTime(slot.end_time)}
                  </Text>
                  {hasBooking
                    ? <View style={[dp.activatedBadge, { backgroundColor: "#dbeafe" }]}><Text style={[dp.activatedTxt, { color: "#1d4ed8" }]}>예약있음</Text></View>
                    : isOn && <View style={dp.activatedBadge}><Text style={dp.activatedTxt}>활성화</Text></View>
                  }
                </Pressable>
              );
            })}
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
  bookCard: { borderLeftWidth: 3, backgroundColor: "#f9fafb", borderRadius: 10, padding: 14, marginBottom: 10 },
  bookTop: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 4 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 20 },
  badgeTxt: { fontSize: 11, fontWeight: "600" },
  customerName: { fontSize: 15, fontWeight: "600", color: "#111" },
  topic: { fontSize: 13, color: "#6b7280", marginBottom: 6 },
  actions: { flexDirection: "row", gap: 8 },
  actionBtn: { flex: 1, padding: 10, borderRadius: 8, alignItems: "center" },
  actionTxt: { color: "#fff", fontSize: 13, fontWeight: "600" },
  bookTime: { fontSize: 13, color: "#6b7280", marginBottom: 4 },
  cancelReqTxt: { fontSize: 12, color: "#c2410c", fontWeight: "600", marginBottom: 6, marginTop: 2 },
  detailBtn: { marginTop: 8, padding: 8, borderRadius: 8, borderWidth: 1, borderColor: "#e5e7eb", alignItems: "center" },
  detailBtnTxt: { fontSize: 12, color: "#6b7280", fontWeight: "600" },
  bookingHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 10, marginTop: 4 },
  tabRow: { flexDirection: "row", gap: 6 },
  tabPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20, borderWidth: 1, borderColor: "#e5e7eb", backgroundColor: "#f9fafb" },
  tabPillActive: { borderColor: "#3b82f6", backgroundColor: "#eff6ff" },
  tabPillTxt: { fontSize: 12, color: "#6b7280", fontWeight: "500" },
  tabPillTxtActive: { color: "#3b82f6", fontWeight: "700" },
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
  slotRowInactive: { backgroundColor: "#f3f4f6", opacity: 0.7 },
  slotTime: { fontSize: 14, fontWeight: "600", color: "#111", flex: 1 },
  slotTimeInactive: { color: "#9ca3af" },
  checkbox: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: "#d1d5db", backgroundColor: "#fff", alignItems: "center", justifyContent: "center", marginRight: 12 },
  checkboxOn: { borderColor: "#3b82f6", backgroundColor: "#3b82f6" },
  checkmark: { color: "#fff", fontSize: 14, fontWeight: "700", lineHeight: 17 },
  unblockBtn: { backgroundColor: "#dcfce7", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  unblockTxt: { fontSize: 12, color: "#15803d", fontWeight: "600" },
  overrideBtn: { backgroundColor: "#dbeafe", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  overrideTxt: { fontSize: 12, color: "#1e40af", fontWeight: "600" },
  activateBtn: { backgroundColor: "#f0fdf4", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, borderWidth: 1, borderColor: "#86efac" },
  activateTxt: { fontSize: 12, color: "#16a34a", fontWeight: "600" },
  slotRowBlocked: { backgroundColor: "#f9fafb", opacity: 0.6 },
  slotRowActivated: { backgroundColor: "#f0fdf4", borderWidth: 1.5, borderColor: "#86efac" },
  activatedBadge: { backgroundColor: "#dcfce7", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 20 },
  activatedTxt: { fontSize: 11, color: "#16a34a", fontWeight: "600" },
  checkboxGreen: { borderColor: "#16a34a", backgroundColor: "#16a34a" },
  holidayBanner: { backgroundColor: "#fee2e2", borderRadius: 8, padding: 10, marginBottom: 8 },
  holidayBannerTxt: { fontSize: 13, color: "#dc2626", fontWeight: "600", textAlign: "center" },
  inactiveBadge: { backgroundColor: "#e5e7eb", borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  inactiveTxt: { fontSize: 11, color: "#6b7280", fontWeight: "600" },
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
                  {b.topic ? <Text style={tl.bkTopic}>{b.topic}</Text> : null}
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
  const [recurringOffDays, setRecurringOffDays] = useState<number[]>([]);
  const [detailBooking, setDetailBooking] = useState<BookingRead | null>(null);
  const initialLoaded = useRef(false);
  const currentYear = useRef(year);
  const currentMonth = useRef(month);

  async function load(y = currentYear.current, m = currentMonth.current) {
    const start = new Date(y, m, 1).toISOString().slice(0, 10);
    const end = new Date(y, m + 1, 0).toISOString().slice(0, 10);
    const [bkRes, slRes, cuRes, meRes] = await Promise.allSettled([
      apiFetch<BookingRead[]>(`/calendars/me/bookings?start=${start}&end=${end}`),
      apiFetch<TimeSlotRead[]>("/calendars/me/time-slots"),
      apiFetch<UsersListResponse>("/users?limit=200"),
      apiFetch<UserRead>("/users/me"),
    ]);
    if (bkRes.status === "fulfilled") setBookings(Array.isArray(bkRes.value) ? bkRes.value : []);
    if (slRes.status === "fulfilled") setSlots(Array.isArray(slRes.value) ? slRes.value : []);
    if (cuRes.status === "fulfilled") {
      const map: Record<string, string> = {};
      cuRes.value.items.forEach(u => { map[u.id] = u.display_name; });
      setCustomerMap(map);
    }
    if (meRes.status === "fulfilled") setRecurringOffDays(meRes.value.recurring_off_days ?? []);
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

  // 달력 스와이프 애니메이션
  const calSlideX = useRef(new Animated.Value(0)).current;
  const prevGhostX = useRef(Animated.add(calSlideX, new Animated.Value(-SCREEN_W))).current;
  const nextGhostX = useRef(Animated.add(calSlideX, new Animated.Value(SCREEN_W))).current;
  const prevMonthRef = useRef(prevMonth);
  const nextMonthRef = useRef(nextMonth);
  const panelVisibleRef = useRef(panelVisible);
  prevMonthRef.current = prevMonth;
  nextMonthRef.current = nextMonth;
  panelVisibleRef.current = panelVisible;
  const prevY = month === 0 ? year - 1 : year;
  const prevM = month === 0 ? 11 : month - 1;
  const nextY = month === 11 ? year + 1 : year;
  const nextM = month === 11 ? 0 : month + 1;

  const isSwipingRef = useRef(false);
  const calendarPan = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, gs) =>
        !panelVisibleRef.current &&
        !isSwipingRef.current &&
        Math.abs(gs.dx) > 12 &&
        Math.abs(gs.dx) > Math.abs(gs.dy) * 1.5,
      onPanResponderMove: (_, gs) => { calSlideX.setValue(gs.dx * 0.92); },
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

  function openPanel(date: string) {
    setSelectedDate(date);
    setPanelVisible(true);
    panelAnim.setValue(PANEL_H);
    Animated.spring(panelAnim, { toValue: 0, useNativeDriver: true, tension: 65, friction: 11 }).start();
  }
  function closePanel() {
    Animated.timing(panelAnim, { toValue: PANEL_H, duration: 240, useNativeDriver: true }).start(() => {
      setPanelVisible(false);
    });
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
    const pyDay = selectedPyDay;
    const slot = slots.find(s => s.is_active && (s.weekdays ?? []).includes(pyDay)) ?? slots.find(s => s.is_active);
    if (!slot) { setInfoMsg("활성화된 타임슬롯이 없습니다."); return; }
    setConfirm({
      title: "휴무 등록",
      body: `${selectedDate}을 휴무로 등록하시겠습니까?`,
      onConfirm: async () => {
        await apiFetch("/bookings", { method: "POST", body: { time_slot_id: slot.id, when: selectedDate, topic: "휴무", type: "HOLIDAY" } });
        await load();
      },
    });
  }

  const holidayBooking = bookings.find(b => b.when === selectedDate && b.type === "HOLIDAY" && b.status !== "CANCELLED");
  const workOverrideBookings = bookings.filter(b => b.when === selectedDate && b.type === "WORK_OVERRIDE" && b.status !== "CANCELLED");
  const workOverrideSlotIds = new Set(workOverrideBookings.map(b => b.time_slot_id));
  const selectedJsDay = selectedDate ? new Date(selectedDate + "T00:00:00").getDay() : -1;
  const selectedPyDay = selectedJsDay >= 0 ? jsWeekdayToPy(selectedJsDay) : -1;
  const isSelectedRecurringOff = selectedPyDay >= 0 && recurringOffDays.includes(selectedPyDay);

  function unblockDate() {
    if (!holidayBooking) return;
    setConfirm({
      title: "영업일 전환",
      body: `${selectedDate}의 휴무를 해제하시겠습니까?`,
      onConfirm: async () => {
        try {
          await apiFetch(`/calendars/me/bookings/${holidayBooking.id}/cancel`, { method: "PATCH", body: { reason: null } });
        } finally {
          await load();
        }
      },
    });
  }

  function overrideDay() {
    const pyDay = selectedPyDay;
    const daySlotList = slots.filter(s => s.is_active && (s.weekdays ?? []).includes(pyDay));
    if (daySlotList.length === 0) { setInfoMsg("타임슬롯이 없습니다."); return; }
    setConfirm({
      title: "이번만 전체 영업",
      body: `${selectedDate}의 모든 시간(${daySlotList.length}개)을 활성화하시겠습니까?`,
      onConfirm: async () => {
        await Promise.all(daySlotList.map(s =>
          apiFetch("/bookings", { method: "POST", body: { time_slot_id: s.id, when: selectedDate, topic: "영업일전환", type: "WORK_OVERRIDE" } })
        ));
        await load();
      },
    });
  }

  function restoreRecurring() {
    if (workOverrideBookings.length === 0) return;
    setConfirm({
      title: "전체 복원",
      body: `${selectedDate}의 활성화된 ${workOverrideBookings.length}개 시간을 모두 비활성화하시겠습니까?`,
      onConfirm: async () => {
        try {
          await Promise.all(workOverrideBookings.map(b =>
            apiFetch(`/calendars/me/bookings/${b.id}/cancel`, { method: "PATCH", body: { reason: null } })
          ));
        } finally {
          await load();
        }
      },
    });
  }

  function saveActivation(toAdd: number[], toRemove: number[]) {
    setConfirm({
      title: "시간 활성화 저장",
      body: `열기: ${toAdd.length}개, 닫기: ${toRemove.length}개`,
      onConfirm: async () => {
        try {
          // 새로 활성화
          await Promise.all(toAdd.map(slotId =>
            apiFetch("/bookings", { method: "POST", body: { time_slot_id: slotId, when: selectedDate, topic: "시간활성화", type: "WORK_OVERRIDE" } })
          ));
          // 기존 활성화 취소
          const toRemoveBookings = workOverrideBookings.filter(b => toRemove.includes(b.time_slot_id));
          await Promise.all(toRemoveBookings.map(b =>
            apiFetch(`/calendars/me/bookings/${b.id}/cancel`, { method: "PATCH", body: { reason: null } })
          ));
        } finally {
          await load();
        }
      },
    });
  }

  const dayBookings = bookings.filter(b => b.when === selectedDate && b.type !== "HOLIDAY" && b.type !== "WORK_OVERRIDE");

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
      <View style={s.monthNav}>
        <Pressable onPress={prevMonth} style={s.navBtn}><Text style={s.navArrow}>‹</Text></Pressable>
        <Text style={s.monthTitle}>{year}년 {MONTHS[month]}</Text>
        <Pressable onPress={nextMonth} style={s.navBtn}><Text style={s.navArrow}>›</Text></Pressable>
      </View>
      <View style={{ flex: 1, overflow: "hidden" }} {...(!panelVisible ? calendarPan.panHandlers : {})}>
        <Animated.View style={[StyleSheet.absoluteFill, { transform: [{ translateX: prevGhostX }] }]} pointerEvents="none">
          <MonthGrid year={prevY} month={prevM} bookings={bookings} selectedDate={selectedDate} onSelect={openPanel} customerMap={customerMap} recurringOffDays={recurringOffDays} slots={slots} />
        </Animated.View>
        <Animated.View style={[StyleSheet.absoluteFill, { transform: [{ translateX: nextGhostX }] }]} pointerEvents="none">
          <MonthGrid year={nextY} month={nextM} bookings={bookings} selectedDate={selectedDate} onSelect={openPanel} customerMap={customerMap} recurringOffDays={recurringOffDays} slots={slots} />
        </Animated.View>
        <Animated.View style={{ flex: 1, transform: [{ translateX: calSlideX }] }}>
          <MonthGrid year={year} month={month} bookings={bookings} selectedDate={selectedDate} onSelect={openPanel} customerMap={customerMap} recurringOffDays={recurringOffDays} slots={slots} />
        </Animated.View>
      </View>

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
            isHoliday={!!holidayBooking}
            isRecurringOff={isSelectedRecurringOff}
            workOverrideSlotIds={workOverrideSlotIds}
            onAction={doAction}
            onBlockDate={blockDate}
            onUnblockDate={unblockDate}
            onOverrideDay={overrideDay}
            onRestoreRecurring={restoreRecurring}
            onDeactivateSlots={deactivateSlots}
            onSaveActivation={saveActivation}
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
  const pyDay = jsWeekdayToPy(jsDay);
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
