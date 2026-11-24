// 홈 탭: 통계, 레슨 신청 처리, 완료할 레슨(일괄 완료), 오늘 예약
import { useCallback, useState } from "react";
import {
  View, Text, ScrollView, Pressable, Modal, TextInput,
  RefreshControl, StyleSheet, ActivityIndicator,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { InstructorStats, BookingRead, UsersListResponse, BulkCompleteItem, BulkCompleteResponse } from "@/types/api";
import { toLocalDateStr } from "@/lib/bookingUtils";
import { lessonLine } from "@/lib/lessonText";

const STATUS_COLOR: Record<string, string> = {
  REQUESTED: "#f59e0b", CONFIRMED: "#3b82f6", COMPLETED: "#16a34a",
  CANCELLED: "#9ca3af", NO_SHOW: "#ef4444",
};
const STATUS_LABEL: Record<string, string> = {
  REQUESTED: "대기", CONFIRMED: "확정", COMPLETED: "완료", CANCELLED: "취소", NO_SHOW: "노쇼",
};
const AVATAR_COLORS = ["#3b82f6", "#8b5cf6", "#ec4899", "#f97316", "#06b6d4", "#16a34a", "#dc2626"];

const LESSON_TYPES = ["드라이버", "아이언샷", "어프로치", "퍼팅", "벙커샷", "코스레슨", "체력훈련", "기타"];
const DECLINE_REASONS = ["일정 불가", "해당 시간 마감", "레슨 종류 불일치", "기타"];

function Avatar({ name, size = 44 }: { name: string; size?: number }) {
  const initial = name ? name.charAt(0) : "?";
  const bg = AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: bg, alignItems: "center", justifyContent: "center" }}>
      <Text style={{ color: "#fff", fontSize: size * 0.42, fontWeight: "700" }}>{initial}</Text>
    </View>
  );
}

// 드롭다운 스타일 옵션 선택 모달
function PickerModal({
  visible, title, options, selected, onSelect, customValue, onCustomChange, onConfirm, onCancel, confirmLabel, confirmColor,
}: {
  visible: boolean; title: string; options: string[]; selected: string;
  onSelect: (v: string) => void;
  customValue: string; onCustomChange: (v: string) => void;
  onConfirm: () => void; onCancel: () => void;
  confirmLabel: string; confirmColor: string;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={pm.backdrop}>
        <View style={pm.sheet}>
          <Text style={pm.title}>{title}</Text>
          {options.map(opt => (
            <Pressable key={opt} style={[pm.option, selected === opt && pm.optionOn]} onPress={() => onSelect(opt)}>
              <View style={[pm.radio, selected === opt && pm.radioOn]} />
              <Text style={[pm.optTxt, selected === opt && pm.optTxtOn]}>{opt}</Text>
            </Pressable>
          ))}
          {selected === "기타" && (
            <TextInput
              style={pm.customInput}
              placeholder="직접 입력..."
              value={customValue}
              onChangeText={onCustomChange}
            />
          )}
          <View style={pm.btnRow}>
            <Pressable style={[pm.btn, pm.cancelBtn]} onPress={onCancel}>
              <Text style={pm.cancelTxt}>취소</Text>
            </Pressable>
            <Pressable
              style={[pm.btn, { backgroundColor: confirmColor }, !selected && pm.btnDisabled]}
              onPress={onConfirm}
              disabled={!selected}
            >
              <Text style={pm.confirmTxt}>{confirmLabel}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const MANAGE_LIMIT = 5;
const BULK_LIMIT = 50; // 일괄 완료 한 요청에 담을 수 있는 예약 수 (서버 제한과 같다)

// 예약을 고객별로 묶는다 (확인 창·결과 창에서 고객이 섞이지 않게)
function byCustomer<T>(items: T[], guestOf: (item: T) => string): { guestId: string; items: T[] }[] {
  const groups: { guestId: string; items: T[] }[] = [];
  for (const item of items) {
    const guestId = guestOf(item);
    const group = groups.find(g => g.guestId === guestId);
    if (group) group.items.push(item);
    else groups.push({ guestId, items: [item] });
  }
  return groups;
}

export default function DashboardScreen() {
  const router = useRouter();
  const [stats, setStats] = useState<InstructorStats | null>(null);
  const [todayBookings, setTodayBookings] = useState<BookingRead[]>([]);
  const [manageBookings, setManageBookings] = useState<BookingRead[]>([]); // REQUESTED + CANCEL_REQUESTED
  const [customerMap, setCustomerMap] = useState<Record<string, string>>({});
  const [refreshing, setRefreshing] = useState(false);
  const [manageModalVisible, setManageModalVisible] = useState(false);

  // 확정 모달
  const [confirmTarget, setConfirmTarget] = useState<{ id: number; name: string } | null>(null);
  const [selectedTopic, setSelectedTopic] = useState("");
  const [customTopic, setCustomTopic] = useState("");
  const [confirmLoading, setConfirmLoading] = useState(false);

  // 거절 모달
  const [declineTarget, setDeclineTarget] = useState<{ id: number; name: string } | null>(null);
  const [selectedReason, setSelectedReason] = useState("");
  const [customReason, setCustomReason] = useState("");
  const [declineLoading, setDeclineLoading] = useState(false);

  // 완료/노쇼 모달 (기존 단순 confirm)
  const [simpleTarget, setSimpleTarget] = useState<{ id: number; action: "complete" | "no-show"; label: string } | null>(null);
  const [simpleLoading, setSimpleLoading] = useState(false);

  // 완료할 레슨: 오늘까지의 확정 예약 (밀린 것 포함). 골라서 한 번에 완료한다
  const [dueBookings, setDueBookings] = useState<BookingRead[]>([]);
  const [dueSelected, setDueSelected] = useState<Set<number>>(new Set());
  const [bulkConfirmVisible, setBulkConfirmVisible] = useState(false);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResult, setBulkResult] = useState<{ completed: number; failed: { booking: BookingRead; message: string }[] } | null>(null);

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [cancelModalTarget, setCancelModalTarget] = useState<BookingRead | null>(null);
  const [cancelActionLoading, setCancelActionLoading] = useState(false);

  const today = toLocalDateStr();
  const futureEnd = (() => { const d = new Date(); d.setDate(d.getDate() + 30); return toLocalDateStr(d); })();
  // 취소 신청은 과거 기간 것도 있을 수 있으므로 넓게 조회
  const wideStart = (() => { const d = new Date(); d.setDate(d.getDate() - 90); return toLocalDateStr(d); })();

  const load = useCallback(async () => {
    try {
      const [stRes, todayRes, futureRes, pastRes, cuRes] = await Promise.allSettled([
        apiFetch<InstructorStats>("/instructors/me/stats"),
        apiFetch<BookingRead[]>(`/calendars/me/bookings?start=${today}&end=${today}`),
        apiFetch<BookingRead[]>(`/calendars/me/bookings?start=${today}&end=${futureEnd}`),
        apiFetch<BookingRead[]>(`/calendars/me/bookings?start=${wideStart}&end=${today}`),
        apiFetch<UsersListResponse>("/users?limit=200"),
      ]);
      if (stRes.status === "fulfilled") setStats(stRes.value);
      if (todayRes.status === "fulfilled") {
        setTodayBookings((Array.isArray(todayRes.value) ? todayRes.value : []).filter(b => b.status !== "CANCELLED" && b.status !== "CANCEL_REQUESTED"));
      }
      // 신청 관리: 미래 REQUESTED + 과거·미래 CANCEL_REQUESTED
      const futureList = futureRes.status === "fulfilled" ? (Array.isArray(futureRes.value) ? futureRes.value : []) : [];
      const pastList = pastRes.status === "fulfilled" ? (Array.isArray(pastRes.value) ? pastRes.value : []) : [];
      const combined = [...futureList, ...pastList];
      const seen = new Set<number>();
      const manageable = combined.filter(b => {
        if (seen.has(b.id)) return false;
        seen.add(b.id);
        return b.status === "REQUESTED" || b.status === "CANCEL_REQUESTED";
      });
      // CANCEL_REQUESTED 우선, 그 다음 REQUESTED, 최신순
      manageable.sort((a, b) => {
        if (a.status === b.status) return b.id - a.id;
        return a.status === "CANCEL_REQUESTED" ? -1 : 1;
      });
      setManageBookings(manageable);
      // 완료할 레슨: 오늘까지의 확정 예약, 날짜가 빠른 순
      const due = pastList
        .filter(b => b.status === "CONFIRMED" && b.when <= today)
        .sort((a, b) => a.when.localeCompare(b.when) || (a.start_time ?? "").localeCompare(b.start_time ?? ""));
      setDueBookings(due);
      setDueSelected(prev => new Set(due.filter(b => prev.has(b.id)).map(b => b.id)));
      if (cuRes.status === "fulfilled") {
        const items = Array.isArray(cuRes.value?.items) ? cuRes.value.items : [];
        const map: Record<string, string> = {};
        items.forEach(u => { if (u?.id) map[u.id] = u.display_name ?? "알 수 없음"; });
        setCustomerMap(map);
      }
    } catch (e) {
      console.error("대시보드 로드 실패:", e);
    }
  }, [today]);

  // 다른 탭에서 돌아올 때도 다시 읽는다 (레슨노트 탭에서 노트를 저장하면 그 레슨이 완료되어 목록이 바뀐다)
  useFocusEffect(useCallback(() => { load(); }, [load]));
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  async function doConfirm() {
    if (!confirmTarget || !selectedTopic) return;
    const topic = selectedTopic === "기타" ? (customTopic.trim() || "기타") : selectedTopic;
    setConfirmLoading(true);
    try {
      await apiFetch(`/calendars/me/bookings/${confirmTarget.id}/confirm`, { method: "PATCH", body: { topic } });
      setConfirmTarget(null); setSelectedTopic(""); setCustomTopic("");
      await load();
    } catch (e) { setErrorMsg(e instanceof Error ? e.message : "처리 실패"); setConfirmTarget(null); }
    finally { setConfirmLoading(false); }
  }

  async function doDecline() {
    if (!declineTarget || !selectedReason) return;
    const reason = selectedReason === "기타" ? (customReason.trim() || "기타") : selectedReason;
    setDeclineLoading(true);
    try {
      await apiFetch(`/calendars/me/bookings/${declineTarget.id}/decline`, { method: "PATCH", body: { reason } });
      setDeclineTarget(null); setSelectedReason(""); setCustomReason("");
      await load();
    } catch (e) { setErrorMsg(e instanceof Error ? e.message : "처리 실패"); setDeclineTarget(null); }
    finally { setDeclineLoading(false); }
  }

  async function doCancelModal(action: "approve-cancel" | "reject-cancel") {
    if (!cancelModalTarget) return;
    setCancelActionLoading(true);
    try {
      await apiFetch(`/calendars/me/bookings/${cancelModalTarget.id}/${action}`, { method: "PATCH" });
      setCancelModalTarget(null);
      await load();
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "처리 실패");
      setCancelModalTarget(null);
    } finally {
      setCancelActionLoading(false);
    }
  }

  async function doSimple() {
    if (!simpleTarget) return;
    setSimpleLoading(true);
    try {
      await apiFetch(`/calendars/me/bookings/${simpleTarget.id}/${simpleTarget.action}`, { method: "PATCH" });
      setSimpleTarget(null);
      await load();
    } catch (e) { setErrorMsg(e instanceof Error ? e.message : "처리 실패"); setSimpleTarget(null); }
    finally { setSimpleLoading(false); }
  }

  function toggleDue(id: number) {
    setDueSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  // 일괄 완료: 요청 하나로 보내고(많으면 50건씩) 건별 결과를 받는다. 안 된 건은 이유와 함께 결과 창에 보여 준다
  async function doBulkComplete() {
    const ids = dueBookings.filter(b => dueSelected.has(b.id)).map(b => b.id);
    if (ids.length === 0) return;
    setBulkLoading(true);
    try {
      const results: BulkCompleteItem[] = [];
      for (let i = 0; i < ids.length; i += BULK_LIMIT) {
        const res = await apiFetch<BulkCompleteResponse>("/calendars/me/bookings/complete", {
          method: "POST", body: { booking_ids: ids.slice(i, i + BULK_LIMIT) },
        });
        results.push(...res.results);
      }
      const byId = new Map(dueBookings.map(b => [b.id, b]));
      setBulkResult({
        completed: results.filter(r => r.ok).length,
        failed: results.filter(r => !r.ok && byId.has(r.booking_id))
          .map(r => ({ booking: byId.get(r.booking_id) as BookingRead, message: r.message ?? "처리되지 않았습니다." })),
      });
      setDueSelected(new Set());
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "처리 실패");
    } finally {
      setBulkConfirmVisible(false);
      setBulkLoading(false);
      await load();
    }
  }

  const activeToday = todayBookings.filter(b => b.status !== "CANCELLED");
  const dueChosen = dueBookings.filter(b => dueSelected.has(b.id));
  const dueAllSelected = dueBookings.length > 0 && dueChosen.length === dueBookings.length;
  const nameOf = (guestId: string) => customerMap[guestId] ?? "알 수 없음";

  return (
    <View style={{ flex: 1 }}>
      <ScrollView style={s.container} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
        <Text style={s.heading}>대시보드</Text>

        {stats && (
          <View style={s.statsRow}>
            <StatBox label="담당고객" value={`${stats.customer_count}명`} color="#16a34a" />
            <StatBox label="대기" value={String(stats.booking_counts.requested)} color="#f59e0b" />
            <StatBox label="확정" value={String(stats.booking_counts.confirmed)} color="#3b82f6" />
          </View>
        )}

        {/* 신청 관리 */}
        <>
          <SectionHeader title="신청 관리" count={manageBookings.length} color="#6d28d9" bg="#ede9fe" />
          {manageBookings.length === 0 ? (
            <View style={s.emptyBox}><Text style={s.emptyText}>신청 내역 없음</Text></View>
          ) : (
            <>{manageBookings.slice(0, MANAGE_LIMIT).map(b => {
              const name = customerMap[b.guest_id] ?? "알 수 없음";
              const isCancelReq = b.status === "CANCEL_REQUESTED";
              return (
                <Pressable key={b.id} style={[s.pendingCard, isCancelReq && s.cancelReqCard]} onPress={isCancelReq ? () => setCancelModalTarget(b) : undefined}>
                  {isCancelReq && (
                    <View style={s.cancelReqBanner}>
                      <Text style={s.cancelReqBannerTxt}>취소 신청 — 탭하여 처리</Text>
                    </View>
                  )}
                  <View style={s.pendingRow}>
                    <View style={s.pendingLeft}>
                      <Text style={s.pendingName}>{name}</Text>
                      <Text style={s.pendingDate}>{b.when}</Text>
                      {b.description ? (
                        <Text style={s.pendingMemo} numberOfLines={2}>{b.description}</Text>
                      ) : null}
                      {isCancelReq && b.cancel_reason ? (
                        <Text style={s.cancelReasonTxt} numberOfLines={1}>사유: {b.cancel_reason}</Text>
                      ) : null}
                    </View>
                    <View style={s.pendingBtns}>
                      {isCancelReq ? (
                        <Text style={s.cancelDetailHint}>자세히{"\n"}보기 →</Text>
                      ) : (
                        <>
                          {b.when > today && (
                            <Pressable style={s.squareConfirm} onPress={() => { setSelectedTopic(""); setCustomTopic(""); setConfirmTarget({ id: b.id, name }); }}>
                              <Text style={s.squareConfirmTxt}>수락</Text>
                            </Pressable>
                          )}
                          <Pressable style={s.squareDecline} onPress={() => { setSelectedReason(""); setCustomReason(""); setDeclineTarget({ id: b.id, name }); }}>
                            <Text style={s.squareDeclineTxt}>거절</Text>
                          </Pressable>
                        </>
                      )}
                    </View>
                  </View>
                </Pressable>
              );
            })}
            {manageBookings.length > MANAGE_LIMIT && (
              <Pressable style={s.moreBtn} onPress={() => setManageModalVisible(true)}>
                <Text style={s.moreBtnTxt}>신청 관리 전체보기 ({manageBookings.length}건) →</Text>
              </Pressable>
            )}</>
          )}
        </>

        {/* 완료할 레슨: 오늘까지의 확정 예약을 골라 한 번에 완료 */}
        <SectionHeader title="완료할 레슨" count={dueBookings.length} color="#15803d" bg="#dcfce7" />
        {dueBookings.length === 0 ? (
          <View style={s.emptyBox}><Text style={s.emptyText}>완료할 레슨이 없습니다.</Text></View>
        ) : (
          <View style={bk.box}>
            <Pressable style={bk.allRow} onPress={() => setDueSelected(dueAllSelected ? new Set() : new Set(dueBookings.map(b => b.id)))}>
              <View style={[bk.check, dueAllSelected && bk.checkOn]}>{dueAllSelected && <Text style={bk.checkTxt}>✓</Text>}</View>
              <Text style={bk.allTxt}>전체 선택</Text>
            </Pressable>
            {dueBookings.map(b => {
              const on = dueSelected.has(b.id);
              return (
                <Pressable key={b.id} style={[bk.row, on && bk.rowOn]} onPress={() => toggleDue(b.id)}>
                  <View style={[bk.check, on && bk.checkOn]}>{on && <Text style={bk.checkTxt}>✓</Text>}</View>
                  <View style={{ flex: 1 }}>
                    <Text style={bk.name}>{nameOf(b.guest_id)}</Text>
                    <Text style={bk.when}>{lessonLine(b)}{b.topic ? ` · ${b.topic}` : ""}</Text>
                  </View>
                  {/* 레슨노트를 쓰면서 완료: 노트가 저장되면 이 레슨이 완료·차감된다 */}
                  <Pressable style={bk.noteBtn} onPress={() => router.push({ pathname: "/(tabs)/notes", params: { booking_id: String(b.id) } })}>
                    <Text style={bk.noteBtnTxt}>노트 작성</Text>
                  </Pressable>
                </Pressable>
              );
            })}
            <Pressable
              style={[bk.submit, dueChosen.length === 0 && bk.submitOff]}
              disabled={dueChosen.length === 0}
              onPress={() => setBulkConfirmVisible(true)}
            >
              <Text style={bk.submitTxt}>선택 완료{dueChosen.length > 0 ? ` (${dueChosen.length})` : ""}</Text>
            </Pressable>
          </View>
        )}

        {/* 오늘 예약 */}
        <SectionHeader title="오늘 예약" count={activeToday.length} color="#16a34a" bg="#d1fae5" />
        {activeToday.length === 0 ? (
          <View style={s.emptyBox}><Text style={s.emptyText}>오늘 예약이 없습니다.</Text></View>
        ) : activeToday.map(b => {
          const name = customerMap[b.guest_id] ?? "알 수 없음";
          const sc = STATUS_COLOR[b.status] ?? "#9ca3af";
          return (
            <View key={b.id} style={[s.todayCard, { borderLeftColor: sc }]}>
              <View style={s.pendingRow}>
                <Avatar name={name} size={40} />
                <View style={s.pendingLeft}>
                  <Text style={s.customerName}>{name}</Text>
                  {b.topic ? <Text style={s.topicTxt}>{b.topic}</Text> : null}
                </View>
                <View style={[s.statusPill, { backgroundColor: sc + "22" }]}>
                  <Text style={[s.statusTxt, { color: sc }]}>{STATUS_LABEL[b.status] ?? b.status}</Text>
                </View>
              </View>
              {b.description ? (
                <View style={s.memoBox}>
                  <Text style={s.memoLabel}>메모</Text>
                  <Text style={s.memoText}>{b.description}</Text>
                </View>
              ) : null}
              {b.status === "REQUESTED" && (
                <View style={s.actions}>
                  {b.when > today && (
                    <Pressable style={[s.actionBtn, s.confirmBtn]} onPress={() => { setSelectedTopic(""); setCustomTopic(""); setConfirmTarget({ id: b.id, name }); }}>
                      <Text style={s.actionTxt}>✓ 확정</Text>
                    </Pressable>
                  )}
                  <Pressable style={[s.actionBtn, s.declineBtn]} onPress={() => { setSelectedReason(""); setCustomReason(""); setDeclineTarget({ id: b.id, name }); }}>
                    <Text style={s.actionTxt}>✕ 거절</Text>
                  </Pressable>
                </View>
              )}
              {b.status === "CONFIRMED" && (
                <View style={s.actions}>
                  <Pressable style={[s.actionBtn, s.completeBtn]} onPress={() => setSimpleTarget({ id: b.id, action: "complete", label: "완료 처리" })}>
                    <Text style={s.actionTxt}>완료</Text>
                  </Pressable>
                  <Pressable style={[s.actionBtn, s.noshowBtn]} onPress={() => setSimpleTarget({ id: b.id, action: "no-show", label: "노쇼 처리" })}>
                    <Text style={s.actionTxt}>노쇼</Text>
                  </Pressable>
                </View>
              )}
            </View>
          );
        })}

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* 확정 모달 - 수업 내용 선택 */}
      <PickerModal
        visible={confirmTarget !== null}
        title={`${confirmTarget?.name ?? ""} — 수업 내용 선택`}
        options={LESSON_TYPES}
        selected={selectedTopic}
        onSelect={setSelectedTopic}
        customValue={customTopic}
        onCustomChange={setCustomTopic}
        onConfirm={doConfirm}
        onCancel={() => setConfirmTarget(null)}
        confirmLabel={confirmLoading ? "처리 중..." : "확정"}
        confirmColor="#2563eb"
      />

      {/* 거절 모달 - 사유 선택 */}
      <PickerModal
        visible={declineTarget !== null}
        title={`${declineTarget?.name ?? ""} — 거절 사유`}
        options={DECLINE_REASONS}
        selected={selectedReason}
        onSelect={setSelectedReason}
        customValue={customReason}
        onCustomChange={setCustomReason}
        onConfirm={doDecline}
        onCancel={() => setDeclineTarget(null)}
        confirmLabel={declineLoading ? "처리 중..." : "거절 확정"}
        confirmColor="#ef4444"
      />

      {/* 완료/노쇼 단순 확인 모달 */}
      <Modal visible={simpleTarget !== null} transparent animationType="fade">
        <View style={cm.backdrop}>
          <View style={cm.sheet}>
            <Text style={cm.title}>{simpleTarget?.label}</Text>
            <Text style={cm.body}>진행하시겠습니까?</Text>
            <View style={cm.btnRow}>
              <Pressable style={[cm.btn, cm.cancelBtn]} onPress={() => setSimpleTarget(null)} disabled={simpleLoading}>
                <Text style={cm.cancelTxt}>취소</Text>
              </Pressable>
              <Pressable style={[cm.btn, cm.okBtn]} onPress={doSimple} disabled={simpleLoading}>
                {simpleLoading ? <ActivityIndicator color="#fff" size="small" /> : <Text style={cm.okTxt}>확인</Text>}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      {/* 일괄 완료 확인: 고객별로 나눠 보여 준다 */}
      <Modal visible={bulkConfirmVisible} transparent animationType="fade">
        <View style={cm.backdrop}>
          <View style={bk.sheet}>
            <Text style={cm.title}>레슨 완료 처리</Text>
            <ScrollView style={{ maxHeight: 360 }}>
              {byCustomer(dueChosen, b => b.guest_id).map(g => (
                <View key={g.guestId} style={bk.group}>
                  <View style={bk.groupHead}>
                    <Text style={bk.groupName}>{nameOf(g.guestId)}</Text>
                    <Text style={bk.groupCount}>{g.items.length}건 · {g.items.length}회 차감</Text>
                  </View>
                  {g.items.map(b => (
                    <Text key={b.id} style={bk.groupLine}>{lessonLine(b)}{b.topic ? ` · ${b.topic}` : ""}</Text>
                  ))}
                </View>
              ))}
            </ScrollView>
            <Text style={bk.total}>
              합계 {byCustomer(dueChosen, b => b.guest_id).length}명 · {dueChosen.length}건 · {dueChosen.length}회 차감
            </Text>
            <View style={cm.btnRow}>
              <Pressable style={[cm.btn, cm.cancelBtn]} onPress={() => setBulkConfirmVisible(false)} disabled={bulkLoading}>
                <Text style={cm.cancelTxt}>취소</Text>
              </Pressable>
              <Pressable style={[cm.btn, { backgroundColor: "#16a34a" }]} onPress={doBulkComplete} disabled={bulkLoading}>
                {bulkLoading ? <ActivityIndicator color="#fff" size="small" /> : <Text style={cm.okTxt}>완료 처리</Text>}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      {/* 일괄 완료 결과: 안 된 건은 고객별로 이유와 함께 */}
      <Modal visible={bulkResult !== null} transparent animationType="fade">
        <View style={cm.backdrop}>
          <View style={bk.sheet}>
            <Text style={cm.title}>완료 처리 결과</Text>
            <Text style={cm.body}>
              {bulkResult?.completed ?? 0}건 완료{bulkResult && bulkResult.failed.length > 0 ? ` · ${bulkResult.failed.length}건은 처리되지 않았습니다` : ""}
            </Text>
            {bulkResult && bulkResult.failed.length > 0 && (
              <ScrollView style={{ maxHeight: 300 }}>
                {byCustomer(bulkResult.failed, f => f.booking.guest_id).map(g => (
                  <View key={g.guestId} style={[bk.group, bk.groupFailed]}>
                    <Text style={bk.groupName}>{nameOf(g.guestId)}</Text>
                    {g.items.map(f => (
                      <View key={f.booking.id}>
                        <Text style={bk.groupLine}>{lessonLine(f.booking)}</Text>
                        <Text style={bk.failReason}>{f.message}</Text>
                      </View>
                    ))}
                  </View>
                ))}
              </ScrollView>
            )}
            <Pressable style={[cm.btn, cm.okBtn, { flex: 0 }]} onPress={() => setBulkResult(null)}>
              <Text style={cm.okTxt}>확인</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      {/* 신청 관리 전체 모달 */}
      <Modal visible={manageModalVisible} animationType="slide" presentationStyle="pageSheet">
        <View style={{ flex: 1, backgroundColor: "#f3f4f6" }}>
          <View style={mm.header}>
            <Text style={mm.title}>신청 관리</Text>
            <Pressable onPress={() => setManageModalVisible(false)} style={mm.closeBtn}>
              <Text style={mm.closeTxt}>✕</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
            {manageBookings.map(b => {
              const name = customerMap[b.guest_id] ?? "알 수 없음";
              const isCancelReq = b.status === "CANCEL_REQUESTED";
              return (
                <Pressable key={b.id} style={[s.pendingCard, isCancelReq && s.cancelReqCard]} onPress={isCancelReq ? () => { setManageModalVisible(false); setTimeout(() => setCancelModalTarget(b), 300); } : undefined}>
                  {isCancelReq && (
                    <View style={s.cancelReqBanner}>
                      <Text style={s.cancelReqBannerTxt}>취소 신청 — 탭하여 처리</Text>
                    </View>
                  )}
                  <View style={s.pendingRow}>
                    <View style={s.pendingLeft}>
                      <Text style={s.pendingName}>{name}</Text>
                      <Text style={s.pendingDate}>{b.when}</Text>
                      {b.description ? (
                        <Text style={s.pendingMemo} numberOfLines={2}>{b.description}</Text>
                      ) : null}
                      {isCancelReq && b.cancel_reason ? (
                        <Text style={s.cancelReasonTxt} numberOfLines={1}>사유: {b.cancel_reason}</Text>
                      ) : null}
                    </View>
                    <View style={s.pendingBtns}>
                      {isCancelReq ? (
                        <Text style={s.cancelDetailHint}>자세히{"\n"}보기 →</Text>
                      ) : (
                        <>
                          {b.when > today && (
                            <Pressable style={s.squareConfirm} onPress={() => { setSelectedTopic(""); setCustomTopic(""); setConfirmTarget({ id: b.id, name }); }}>
                              <Text style={s.squareConfirmTxt}>수락</Text>
                            </Pressable>
                          )}
                          <Pressable style={s.squareDecline} onPress={() => { setSelectedReason(""); setCustomReason(""); setDeclineTarget({ id: b.id, name }); }}>
                            <Text style={s.squareDeclineTxt}>거절</Text>
                          </Pressable>
                        </>
                      )}
                    </View>
                  </View>
                </Pressable>
              );
            })}
            {manageBookings.length === 0 && (
              <View style={s.emptyBox}><Text style={s.emptyText}>처리할 신청이 없습니다.</Text></View>
            )}
          </ScrollView>
        </View>
      </Modal>

      {/* 취소 신청 처리 모달 */}
      <Modal visible={cancelModalTarget !== null} transparent animationType="fade">
        <Pressable style={cancelSt.backdrop} onPress={() => setCancelModalTarget(null)}>
          <Pressable style={cancelSt.sheet} onPress={() => {}}>
            <Text style={cancelSt.title}>취소 신청 확인</Text>
            <View style={cancelSt.row}>
              <Text style={cancelSt.label}>고객</Text>
              <Text style={cancelSt.value}>{customerMap[cancelModalTarget?.guest_id ?? ""] ?? "알 수 없음"}</Text>
            </View>
            <View style={cancelSt.row}>
              <Text style={cancelSt.label}>날짜</Text>
              <Text style={cancelSt.value}>{cancelModalTarget?.when}</Text>
            </View>
            {cancelModalTarget?.start_time && cancelModalTarget.end_time && (
              <View style={cancelSt.row}>
                <Text style={cancelSt.label}>시간</Text>
                <Text style={cancelSt.value}>
                  {cancelModalTarget.start_time.slice(0, 5)} ~ {cancelModalTarget.end_time.slice(0, 5)}
                </Text>
              </View>
            )}
            <View style={cancelSt.reasonBox}>
              <Text style={cancelSt.reasonLabel}>취소 사유</Text>
              <Text style={cancelSt.reasonText}>{cancelModalTarget?.cancel_reason ?? "사유 없음"}</Text>
            </View>
            <View style={cancelSt.btnRow}>
              <Pressable
                style={[cancelSt.rejectBtn, cancelActionLoading && { opacity: 0.6 }]}
                onPress={() => doCancelModal("reject-cancel")}
                disabled={cancelActionLoading}
              >
                <Text style={cancelSt.rejectTxt}>거절</Text>
              </Pressable>
              <Pressable
                style={[cancelSt.approveBtn, cancelActionLoading && { opacity: 0.6 }]}
                onPress={() => doCancelModal("approve-cancel")}
                disabled={cancelActionLoading}
              >
                <Text style={cancelSt.approveTxt}>{cancelActionLoading ? "처리 중..." : "취소 승인"}</Text>
              </Pressable>
            </View>
            <Pressable style={cancelSt.closeRow} onPress={() => setCancelModalTarget(null)}>
              <Text style={cancelSt.closeTxt}>닫기</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>

      {/* 오류 모달 */}
      <Modal visible={errorMsg !== null} transparent animationType="fade">
        <View style={cm.backdrop}>
          <View style={cm.sheet}>
            <Text style={cm.title}>오류</Text>
            <Text style={cm.body}>{errorMsg}</Text>
            <Pressable style={[cm.btn, cm.okBtn, { alignSelf: "stretch" }]} onPress={() => setErrorMsg(null)}>
              <Text style={cm.okTxt}>확인</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={[s.statBox, { borderTopColor: color, borderTopWidth: 3 }]}>
      <Text style={[s.statVal, { color }]}>{value}</Text>
      <Text style={s.statLabel}>{label}</Text>
    </View>
  );
}

function SectionHeader({ title, count, color, bg }: { title: string; count: number; color: string; bg: string }) {
  return (
    <View style={s.sectionHeader}>
      <Text style={s.sectionTitle}>{title}</Text>
      <View style={[s.badge, { backgroundColor: bg }]}>
        <Text style={[s.badgeTxt, { color }]}>{count}</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f3f4f6" },
  heading: { fontSize: 22, fontWeight: "700", paddingHorizontal: 20, paddingTop: 20, paddingBottom: 14 },
  statsRow: { flexDirection: "row", gap: 8, paddingHorizontal: 16, marginBottom: 8 },
  statBox: { flex: 1, backgroundColor: "#fff", borderRadius: 10, padding: 12, alignItems: "center" },
  statVal: { fontSize: 20, fontWeight: "800", marginBottom: 2 },
  statLabel: { fontSize: 11, color: "#6b7280" },
  sectionHeader: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 },
  sectionTitle: { fontSize: 15, fontWeight: "700", color: "#111" },
  badge: { paddingHorizontal: 9, paddingVertical: 2, borderRadius: 20 },
  badgeTxt: { fontSize: 13, fontWeight: "700" },

  // 신청 대기 카드
  pendingCard: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 10, borderRadius: 12, padding: 16, borderWidth: 2, borderColor: "#111" },
  pendingRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  pendingLeft: { flex: 1, gap: 4 },
  pendingName: { fontSize: 18, fontWeight: "800", color: "#111" },
  pendingDate: { fontSize: 12, color: "#9ca3af" },
  pendingMemo: { fontSize: 13, color: "#3b82f6", lineHeight: 18, marginTop: 2 },
  pendingBtns: { flexDirection: "row", gap: 8 },
  squareConfirm: { width: 64, height: 64, borderWidth: 2, borderColor: "#2563eb", borderRadius: 10, alignItems: "center", justifyContent: "center", backgroundColor: "#eff6ff" },
  squareDecline: { width: 64, height: 64, borderWidth: 2, borderColor: "#d1d5db", borderRadius: 10, alignItems: "center", justifyContent: "center", backgroundColor: "#fff" },
  squareConfirmTxt: { color: "#2563eb", fontSize: 13, fontWeight: "700" },
  squareDeclineTxt: { color: "#374151", fontSize: 13, fontWeight: "700" },

  cancelReqCard: { borderColor: "#f97316", backgroundColor: "#fff7ed" },
  cancelDetailHint: { color: "#f97316", fontSize: 12, fontWeight: "700", textAlign: "center", lineHeight: 18 },
  cancelReqBanner: { backgroundColor: "#f97316", borderRadius: 6, alignSelf: "flex-start", paddingHorizontal: 8, paddingVertical: 2, marginBottom: 8 },
  cancelReqBannerTxt: { color: "#fff", fontSize: 11, fontWeight: "700" },
  cancelReasonTxt: { fontSize: 12, color: "#c2410c", marginTop: 2 },
  moreBtn: { marginHorizontal: 16, marginBottom: 10, padding: 12, backgroundColor: "#f3f4f6", borderRadius: 10, alignItems: "center" },
  moreBtnTxt: { color: "#6b7280", fontSize: 13, fontWeight: "600" },
  memoBox: { backgroundColor: "#f9fafb", borderRadius: 8, padding: 10, marginTop: 10 },
  memoLabel: { fontSize: 10, color: "#9ca3af", marginBottom: 2, fontWeight: "600" },
  memoText: { fontSize: 13, color: "#374151", lineHeight: 18 },

  // 오늘 예약
  todayCard: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8, borderRadius: 12, padding: 14, borderLeftWidth: 4 },
  customerName: { fontSize: 15, fontWeight: "700", color: "#111" },
  topicTxt: { fontSize: 12, color: "#3b82f6", fontWeight: "600", marginTop: 1 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  statusTxt: { fontSize: 12, fontWeight: "700" },
  actions: { flexDirection: "row", gap: 8, marginTop: 10 },
  actionBtn: { flex: 1, paddingVertical: 11, borderRadius: 10, alignItems: "center" },
  actionTxt: { color: "#fff", fontSize: 14, fontWeight: "700" },
  confirmBtn: { backgroundColor: "#2563eb" },
  declineBtn: { backgroundColor: "#9ca3af" },
  completeBtn: { backgroundColor: "#16a34a" },
  noshowBtn: { backgroundColor: "#ef4444" },

  emptyBox: { margin: 16, padding: 24, backgroundColor: "#fff", borderRadius: 12, alignItems: "center" },
  emptyText: { color: "#9ca3af", fontSize: 14 },
});

// 단순 확인 모달 스타일
// 완료할 레슨 (일괄 완료)
const bk = StyleSheet.create({
  box: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 10, borderRadius: 12, padding: 12, gap: 6 },
  allRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 6, paddingHorizontal: 4 },
  allTxt: { fontSize: 13, color: "#6b7280", fontWeight: "600" },
  row: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 10, paddingHorizontal: 4, borderTopWidth: 1, borderTopColor: "#f3f4f6" },
  rowOn: { backgroundColor: "#f0fdf4" },
  check: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: "#d1d5db", alignItems: "center", justifyContent: "center" },
  checkOn: { backgroundColor: "#16a34a", borderColor: "#16a34a" },
  checkTxt: { color: "#fff", fontSize: 13, fontWeight: "800" },
  name: { fontSize: 15, fontWeight: "700", color: "#111" },
  when: { fontSize: 12, color: "#6b7280", marginTop: 2 },
  noteBtn: { paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8, borderWidth: 1, borderColor: "#16a34a", backgroundColor: "#fff" },
  noteBtnTxt: { fontSize: 12, color: "#15803d", fontWeight: "700" },
  submit: { marginTop: 6, backgroundColor: "#16a34a", paddingVertical: 12, borderRadius: 10, alignItems: "center" },
  submitOff: { backgroundColor: "#d1d5db" },
  submitTxt: { color: "#fff", fontSize: 14, fontWeight: "700" },
  sheet: { backgroundColor: "#fff", borderRadius: 16, padding: 20, width: 320, gap: 12 },
  group: { borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 10, padding: 12, marginBottom: 8, gap: 4 },
  groupFailed: { borderColor: "#fecaca", backgroundColor: "#fef2f2" },
  groupHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 2 },
  groupName: { fontSize: 15, fontWeight: "800", color: "#111" },
  groupCount: { fontSize: 12, fontWeight: "700", color: "#15803d" },
  groupLine: { fontSize: 13, color: "#374151" },
  failReason: { fontSize: 12, color: "#b91c1c", marginBottom: 4 },
  total: { fontSize: 13, fontWeight: "700", color: "#111", textAlign: "center" },
});

const cm = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center" },
  sheet: { backgroundColor: "#fff", borderRadius: 16, padding: 24, width: 300, gap: 12 },
  title: { fontSize: 17, fontWeight: "700", color: "#111", textAlign: "center" },
  body: { fontSize: 14, color: "#374151", textAlign: "center" },
  btnRow: { flexDirection: "row", gap: 10 },
  btn: { flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: "center" },
  cancelBtn: { backgroundColor: "#f3f4f6" },
  cancelTxt: { color: "#374151", fontWeight: "600" },
  okBtn: { backgroundColor: "#2563eb" },
  okTxt: { color: "#fff", fontWeight: "700" },
});

// 피커 모달 스타일
const mm = StyleSheet.create({
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 20, paddingTop: 20, paddingBottom: 14, backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  title: { fontSize: 20, fontWeight: "700", color: "#111" },
  closeBtn: { padding: 4 },
  closeTxt: { fontSize: 18, color: "#9ca3af" },
});

const cancelSt = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.55)", alignItems: "center", justifyContent: "center" },
  sheet: { backgroundColor: "#fff", borderRadius: 16, padding: 24, width: 300 },
  title: { fontSize: 16, fontWeight: "700", color: "#111", marginBottom: 16, textAlign: "center" },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  label: { fontSize: 13, color: "#6b7280" },
  value: { fontSize: 13, fontWeight: "600", color: "#111" },
  reasonBox: { backgroundColor: "#fff7ed", borderRadius: 10, padding: 12, marginTop: 14 },
  reasonLabel: { fontSize: 11, color: "#9ca3af", fontWeight: "600", marginBottom: 4 },
  reasonText: { fontSize: 14, color: "#c2410c", lineHeight: 20 },
  btnRow: { flexDirection: "row", gap: 10, marginTop: 18 },
  rejectBtn: { flex: 1, paddingVertical: 13, borderRadius: 10, backgroundColor: "#f3f4f6", alignItems: "center" },
  rejectTxt: { color: "#374151", fontWeight: "700", fontSize: 14 },
  approveBtn: { flex: 1, paddingVertical: 13, borderRadius: 10, backgroundColor: "#ef4444", alignItems: "center" },
  approveTxt: { color: "#fff", fontWeight: "700", fontSize: 14 },
  closeRow: { marginTop: 12, alignItems: "center" },
  closeTxt: { color: "#9ca3af", fontSize: 13, paddingVertical: 4 },
});

const pm = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center" },
  sheet: { backgroundColor: "#fff", borderRadius: 20, padding: 24, width: 320, gap: 4 },
  title: { fontSize: 15, fontWeight: "700", color: "#111", marginBottom: 10 },
  option: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 11, paddingHorizontal: 8, borderRadius: 10 },
  optionOn: { backgroundColor: "#eff6ff" },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 2, borderColor: "#d1d5db" },
  radioOn: { borderColor: "#2563eb", backgroundColor: "#2563eb" },
  optTxt: { fontSize: 15, color: "#374151" },
  optTxtOn: { color: "#1d4ed8", fontWeight: "700" },
  customInput: { borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 10, padding: 10, fontSize: 14, marginTop: 4, marginBottom: 4 },
  btnRow: { flexDirection: "row", gap: 10, marginTop: 12 },
  btn: { flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: "center" },
  btnDisabled: { opacity: 0.4 },
  cancelBtn: { backgroundColor: "#f3f4f6" },
  cancelTxt: { color: "#374151", fontWeight: "600", fontSize: 14 },
  confirmTxt: { color: "#fff", fontWeight: "700", fontSize: 14 },
});
