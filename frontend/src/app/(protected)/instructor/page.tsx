"use client";

import React, { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/axios";
import DashboardLayout, { type SidebarItem } from "@/components/layout/DashboardLayout";
import { Loader2, CheckCircle, XCircle, CheckSquare, AlertTriangle } from "lucide-react";

export const instructorNav: SidebarItem[] = [
  { name: "대시보드", href: "/instructor", iconKey: "dashboard" },
  { name: "고객 관리", href: "/instructor/customers", iconKey: "users" },
  { name: "스케줄", href: "/instructor/schedule", iconKey: "calendar" },
  { name: "게시물", href: "/instructor/posts", iconKey: "filetext" },
  { name: "매출", href: "/instructor/revenue", iconKey: "trending" },
  { name: "내 정보", href: "/instructor/profile", iconKey: "user" },
];

type Stats = {
  customer_count: number;
  booking_counts: { requested: number; confirmed: number; total: number; completed: number };
  attendance_rate: number | null;
};

type Booking = {
  id: number;
  when: string;
  topic: string | null;
  status: string;
  description: string | null;
  cancel_reason: string | null;
  time_slot_id: number;
  guest_id: string;
};

type SlotTime = { start_time: string; end_time: string };

const LESSON_TYPES = ["드라이버", "아이언샷", "어프로치", "퍼팅", "벙커샷", "코스레슨", "체력훈련", "기타"];
const DECLINE_REASONS = ["일정 불가", "해당 시간 마감", "레슨 종류 불일치", "기타"];

const STATUS_LABEL: Record<string, string> = {
  REQUESTED: "대기", CONFIRMED: "확정", COMPLETED: "완료",
  CANCELLED: "취소", NO_SHOW: "노쇼", CANCEL_REQUESTED: "취소신청",
};
const STATUS_COLOR: Record<string, string> = {
  REQUESTED: "bg-amber-100 text-amber-700",
  CONFIRMED: "bg-blue-100 text-blue-700",
  COMPLETED: "bg-green-100 text-green-700",
  CANCELLED: "bg-gray-100 text-gray-500",
  NO_SHOW: "bg-red-100 text-red-600",
  CANCEL_REQUESTED: "bg-orange-100 text-orange-700",
};

export default function InstructorDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [manageBookings, setManageBookings] = useState<Booking[]>([]);
  const [todayBookings, setTodayBookings] = useState<Booking[]>([]);
  const [customerMap, setCustomerMap] = useState<Record<string, string>>({});
  const [slotMap, setSlotMap] = useState<Record<number, SlotTime>>({});
  const [loading, setLoading] = useState(true);
  const [me, setMe] = useState<{ display_name: string } | null>(null);

  // 확정 모달
  const [confirmTarget, setConfirmTarget] = useState<Booking | null>(null);
  const [confirmTopic, setConfirmTopic] = useState("");
  const [confirmCustom, setConfirmCustom] = useState("");
  const [confirmLoading, setConfirmLoading] = useState(false);

  // 거절 모달
  const [declineTarget, setDeclineTarget] = useState<Booking | null>(null);
  const [declineReason, setDeclineReason] = useState("");
  const [declineCustom, setDeclineCustom] = useState("");
  const [declineLoading, setDeclineLoading] = useState(false);

  // 취소신청 모달
  const [cancelTarget, setCancelTarget] = useState<Booking | null>(null);
  const [cancelLoading, setCancelLoading] = useState(false);

  // 완료/노쇼 모달
  const [simpleTarget, setSimpleTarget] = useState<{ booking: Booking; action: "complete" | "no-show" } | null>(null);
  const [simpleLoading, setSimpleLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const today = new Date().toISOString().slice(0, 10);
  const futureEnd = (() => { const d = new Date(); d.setDate(d.getDate() + 30); return d.toISOString().slice(0, 10); })();
  const wideStart = (() => { const d = new Date(); d.setDate(d.getDate() - 90); return d.toISOString().slice(0, 10); })();

  const load = useCallback(async () => {
    try {
      const [statsRes, meRes, todayRes, futureRes, pastRes, usersRes, slotsRes] = await Promise.allSettled([
        api.get("/instructors/me/stats"),
        api.get("/users/me"),
        api.get(`/calendars/me/bookings?start=${today}&end=${today}`),
        api.get(`/calendars/me/bookings?start=${today}&end=${futureEnd}`),
        api.get(`/calendars/me/bookings?start=${wideStart}&end=${today}`),
        api.get("/users?limit=200"),
        api.get("/calendars/me/time-slots"),
      ]);

      if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
      if (meRes.status === "fulfilled") setMe(meRes.value.data);

      if (todayRes.status === "fulfilled") {
        const list: Booking[] = Array.isArray(todayRes.value.data) ? todayRes.value.data : [];
        setTodayBookings(list.filter(b => b.status !== "CANCELLED"));
      }

      const future: Booking[] = futureRes.status === "fulfilled" && Array.isArray(futureRes.value.data) ? futureRes.value.data : [];
      const past: Booking[] = pastRes.status === "fulfilled" && Array.isArray(pastRes.value.data) ? pastRes.value.data : [];
      const combined = [...future, ...past];
      const seen = new Set<number>();
      const manageable = combined.filter(b => {
        if (seen.has(b.id)) return false;
        seen.add(b.id);
        return b.status === "REQUESTED" || b.status === "CANCEL_REQUESTED";
      });
      manageable.sort((a, b) => {
        if (a.status === b.status) return b.id - a.id;
        return a.status === "CANCEL_REQUESTED" ? -1 : 1;
      });
      setManageBookings(manageable);

      if (usersRes.status === "fulfilled") {
        const items = usersRes.value.data?.items ?? [];
        const map: Record<string, string> = {};
        items.forEach((u: { id: string; display_name: string }) => { map[u.id] = u.display_name; });
        setCustomerMap(map);
      }

      if (slotsRes.status === "fulfilled" && Array.isArray(slotsRes.value.data)) {
        const m: Record<number, SlotTime> = {};
        slotsRes.value.data.forEach((s: { id: number; start_time: string; end_time: string }) => {
          m[s.id] = { start_time: s.start_time, end_time: s.end_time };
        });
        setSlotMap(m);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [today, futureEnd, wideStart]);

  useEffect(() => { load(); }, [load]);

  async function doConfirm() {
    if (!confirmTarget || !confirmTopic) return;
    const topic = confirmTopic === "기타" ? (confirmCustom.trim() || "기타") : confirmTopic;
    setConfirmLoading(true);
    try {
      await api.patch(`/calendars/me/bookings/${confirmTarget.id}/confirm`, { topic });
      setConfirmTarget(null); setConfirmTopic(""); setConfirmCustom("");
      await load();
    } catch { setError("확정 처리 실패"); } finally { setConfirmLoading(false); }
  }

  async function doDecline() {
    if (!declineTarget || !declineReason) return;
    const reason = declineReason === "기타" ? (declineCustom.trim() || "기타") : declineReason;
    setDeclineLoading(true);
    try {
      await api.patch(`/calendars/me/bookings/${declineTarget.id}/decline`, { reason });
      setDeclineTarget(null); setDeclineReason(""); setDeclineCustom("");
      await load();
    } catch { setError("거절 처리 실패"); } finally { setDeclineLoading(false); }
  }

  async function doCancel(action: "approve-cancel" | "reject-cancel") {
    if (!cancelTarget) return;
    setCancelLoading(true);
    try {
      await api.patch(`/calendars/me/bookings/${cancelTarget.id}/${action}`);
      setCancelTarget(null);
      await load();
    } catch { setError("처리 실패"); } finally { setCancelLoading(false); }
  }

  async function doSimple() {
    if (!simpleTarget) return;
    setSimpleLoading(true);
    try {
      await api.patch(`/calendars/me/bookings/${simpleTarget.booking.id}/${simpleTarget.action}`);
      setSimpleTarget(null);
      await load();
    } catch { setError("처리 실패"); } finally { setSimpleLoading(false); }
  }

  if (loading) {
    return (
      <DashboardLayout navItems={instructorNav} headerFallback="대시보드" userLabel={{ name: "강사님", role: "Instructor" }}>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="animate-spin text-gray-400" size={28} />
        </div>
      </DashboardLayout>
    );
  }

  const guestName = (guestId: string) => customerMap[guestId] ?? "알 수 없음";
  const slotTime = (slotId: number) => {
    const s = slotMap[slotId];
    return s ? `${s.start_time.slice(0, 5)} ~ ${s.end_time.slice(0, 5)}` : "";
  };

  return (
    <DashboardLayout
      navItems={instructorNav}
      headerFallback="대시보드"
      userLabel={{ initial: me?.display_name.charAt(0), name: me?.display_name ?? "강사님", role: "Instructor" }}
    >
      <div className="space-y-6">
        {error && (
          <div className="flex items-center gap-2 bg-red-50 text-red-600 px-4 py-3 rounded-xl text-sm">
            <AlertTriangle size={16} /> {error}
            <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">✕</button>
          </div>
        )}

        {/* 통계 카드 */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="담당 고객" value={`${stats.customer_count}명`} color="text-green-600" border="border-t-green-500" />
            <StatCard label="대기 예약" value={String(stats.booking_counts.requested)} color="text-amber-600" border="border-t-amber-500" />
            <StatCard label="확정 예약" value={String(stats.booking_counts.confirmed)} color="text-blue-600" border="border-t-blue-500" />
            <StatCard label="완료 레슨" value={String(stats.booking_counts.completed)} color="text-gray-700" border="border-t-gray-400" />
          </div>
        )}

        {/* 신청 관리 */}
        <section>
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">
            신청 관리 <span className="ml-1 bg-purple-100 text-purple-700 text-xs font-bold px-2 py-0.5 rounded-full">{manageBookings.length}</span>
          </h2>
          {manageBookings.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center text-gray-400 text-sm">처리할 신청이 없습니다.</div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500 text-xs">
                  <tr>
                    <th className="text-left px-4 py-3">고객</th>
                    <th className="text-left px-4 py-3">날짜</th>
                    <th className="text-left px-4 py-3">시간</th>
                    <th className="text-left px-4 py-3">상태</th>
                    <th className="text-left px-4 py-3">메모</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {manageBookings.map(b => (
                    <tr key={b.id} className={b.status === "CANCEL_REQUESTED" ? "bg-orange-50" : ""}>
                      <td className="px-4 py-3 font-semibold text-gray-900">{guestName(b.guest_id)}</td>
                      <td className="px-4 py-3 text-gray-600">{b.when}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{slotTime(b.time_slot_id)}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-bold px-2 py-1 rounded-full ${STATUS_COLOR[b.status] ?? ""}`}>
                          {STATUS_LABEL[b.status] ?? b.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs max-w-[160px] truncate">
                        {b.status === "CANCEL_REQUESTED" ? (b.cancel_reason ?? "사유 없음") : (b.description ?? "-")}
                      </td>
                      <td className="px-4 py-3">
                        {b.status === "CANCEL_REQUESTED" ? (
                          <button
                            onClick={() => setCancelTarget(b)}
                            className="text-orange-600 hover:underline text-xs font-semibold"
                          >
                            처리하기
                          </button>
                        ) : (
                          <div className="flex gap-2">
                            <button
                              onClick={() => { setConfirmTopic(""); setConfirmCustom(""); setConfirmTarget(b); }}
                              className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700 transition"
                            >
                              수락
                            </button>
                            <button
                              onClick={() => { setDeclineReason(""); setDeclineCustom(""); setDeclineTarget(b); }}
                              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-semibold hover:bg-gray-200 transition"
                            >
                              거절
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* 오늘 예약 */}
        <section>
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">
            오늘 예약 <span className="ml-1 bg-green-100 text-green-700 text-xs font-bold px-2 py-0.5 rounded-full">{todayBookings.length}</span>
          </h2>
          {todayBookings.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center text-gray-400 text-sm">오늘 예약이 없습니다.</div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500 text-xs">
                  <tr>
                    <th className="text-left px-4 py-3">고객</th>
                    <th className="text-left px-4 py-3">시간</th>
                    <th className="text-left px-4 py-3">수업 내용</th>
                    <th className="text-left px-4 py-3">상태</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {todayBookings.map(b => (
                    <tr key={b.id}>
                      <td className="px-4 py-3 font-semibold text-gray-900">{guestName(b.guest_id)}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{slotTime(b.time_slot_id)}</td>
                      <td className="px-4 py-3 text-blue-600 text-xs font-semibold">{b.topic ?? "-"}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-bold px-2 py-1 rounded-full ${STATUS_COLOR[b.status] ?? ""}`}>
                          {STATUS_LABEL[b.status] ?? b.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {b.status === "REQUESTED" && (
                          <div className="flex gap-2">
                            <button onClick={() => { setConfirmTopic(""); setConfirmCustom(""); setConfirmTarget(b); }} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700 transition">수락</button>
                            <button onClick={() => { setDeclineReason(""); setDeclineCustom(""); setDeclineTarget(b); }} className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-semibold hover:bg-gray-200 transition">거절</button>
                          </div>
                        )}
                        {b.status === "CONFIRMED" && (
                          <div className="flex gap-2">
                            <button onClick={() => setSimpleTarget({ booking: b, action: "complete" })} className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-semibold hover:bg-green-700 transition">완료</button>
                            <button onClick={() => setSimpleTarget({ booking: b, action: "no-show" })} className="px-3 py-1.5 bg-red-100 text-red-600 rounded-lg text-xs font-semibold hover:bg-red-200 transition">노쇼</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {/* 확정 모달 */}
      {confirmTarget && (
        <Modal title={`${guestName(confirmTarget.guest_id)} — 수업 내용 선택`} onClose={() => setConfirmTarget(null)}>
          <div className="space-y-2">
            {LESSON_TYPES.map(opt => (
              <label key={opt} className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer border transition ${confirmTopic === opt ? "border-blue-500 bg-blue-50" : "border-gray-100 hover:bg-gray-50"}`}>
                <input type="radio" name="topic" value={opt} checked={confirmTopic === opt} onChange={() => setConfirmTopic(opt)} className="accent-blue-600" />
                <span className="text-sm font-medium">{opt}</span>
              </label>
            ))}
            {confirmTopic === "기타" && (
              <input
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm mt-1"
                placeholder="직접 입력..."
                value={confirmCustom}
                onChange={e => setConfirmCustom(e.target.value)}
              />
            )}
          </div>
          <div className="flex gap-3 mt-5">
            <button onClick={() => setConfirmTarget(null)} className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 transition">취소</button>
            <button onClick={doConfirm} disabled={!confirmTopic || confirmLoading} className="flex-1 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-bold hover:bg-blue-700 transition disabled:opacity-40 flex items-center justify-center gap-2">
              {confirmLoading ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />} 확정
            </button>
          </div>
        </Modal>
      )}

      {/* 거절 모달 */}
      {declineTarget && (
        <Modal title={`${guestName(declineTarget.guest_id)} — 거절 사유`} onClose={() => setDeclineTarget(null)}>
          <div className="space-y-2">
            {DECLINE_REASONS.map(opt => (
              <label key={opt} className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer border transition ${declineReason === opt ? "border-red-400 bg-red-50" : "border-gray-100 hover:bg-gray-50"}`}>
                <input type="radio" name="reason" value={opt} checked={declineReason === opt} onChange={() => setDeclineReason(opt)} className="accent-red-500" />
                <span className="text-sm font-medium">{opt}</span>
              </label>
            ))}
            {declineReason === "기타" && (
              <input
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm mt-1"
                placeholder="직접 입력..."
                value={declineCustom}
                onChange={e => setDeclineCustom(e.target.value)}
              />
            )}
          </div>
          <div className="flex gap-3 mt-5">
            <button onClick={() => setDeclineTarget(null)} className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 transition">취소</button>
            <button onClick={doDecline} disabled={!declineReason || declineLoading} className="flex-1 py-2.5 rounded-xl bg-red-500 text-white text-sm font-bold hover:bg-red-600 transition disabled:opacity-40 flex items-center justify-center gap-2">
              {declineLoading ? <Loader2 size={16} className="animate-spin" /> : <XCircle size={16} />} 거절 확정
            </button>
          </div>
        </Modal>
      )}

      {/* 취소신청 모달 */}
      {cancelTarget && (
        <Modal title="취소 신청 확인" onClose={() => setCancelTarget(null)}>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between py-2 border-b border-gray-50">
              <span className="text-gray-500">고객</span>
              <span className="font-semibold">{guestName(cancelTarget.guest_id)}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-gray-50">
              <span className="text-gray-500">날짜</span>
              <span className="font-semibold">{cancelTarget.when}</span>
            </div>
            {slotMap[cancelTarget.time_slot_id] && (
              <div className="flex justify-between py-2 border-b border-gray-50">
                <span className="text-gray-500">시간</span>
                <span className="font-semibold">{slotTime(cancelTarget.time_slot_id)}</span>
              </div>
            )}
            <div className="bg-orange-50 rounded-xl p-3 mt-2">
              <p className="text-xs text-gray-400 font-semibold mb-1">취소 사유</p>
              <p className="text-orange-700">{cancelTarget.cancel_reason ?? "사유 없음"}</p>
            </div>
          </div>
          <div className="flex gap-3 mt-5">
            <button onClick={() => doCancel("reject-cancel")} disabled={cancelLoading} className="flex-1 py-2.5 rounded-xl bg-gray-100 text-gray-700 text-sm font-semibold hover:bg-gray-200 transition disabled:opacity-40">
              거절
            </button>
            <button onClick={() => doCancel("approve-cancel")} disabled={cancelLoading} className="flex-1 py-2.5 rounded-xl bg-red-500 text-white text-sm font-bold hover:bg-red-600 transition disabled:opacity-40 flex items-center justify-center gap-2">
              {cancelLoading ? <Loader2 size={16} className="animate-spin" /> : null} 취소 승인
            </button>
          </div>
        </Modal>
      )}

      {/* 완료/노쇼 모달 */}
      {simpleTarget && (
        <Modal
          title={simpleTarget.action === "complete" ? "레슨 완료 처리" : "노쇼 처리"}
          onClose={() => setSimpleTarget(null)}
        >
          <p className="text-sm text-gray-600 mb-5">
            {guestName(simpleTarget.booking.guest_id)} 고객의 예약을{" "}
            <strong>{simpleTarget.action === "complete" ? "완료" : "노쇼"}</strong> 처리하시겠습니까?
          </p>
          <div className="flex gap-3">
            <button onClick={() => setSimpleTarget(null)} className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 transition">취소</button>
            <button
              onClick={doSimple}
              disabled={simpleLoading}
              className={`flex-1 py-2.5 rounded-xl text-white text-sm font-bold transition disabled:opacity-40 flex items-center justify-center gap-2 ${simpleTarget.action === "complete" ? "bg-green-600 hover:bg-green-700" : "bg-red-500 hover:bg-red-600"}`}
            >
              {simpleLoading ? <Loader2 size={16} className="animate-spin" /> : <CheckSquare size={16} />}
              확인
            </button>
          </div>
        </Modal>
      )}
    </DashboardLayout>
  );
}

function StatCard({ label, value, color, border }: { label: string; value: string; color: string; border: string }) {
  return (
    <div className={`bg-white rounded-2xl border-t-4 ${border} p-5 shadow-sm`}>
      <p className={`text-2xl font-extrabold ${color}`}>{value}</p>
      <p className="text-xs text-gray-400 mt-1 font-medium">{label}</p>
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6" onClick={e => e.stopPropagation()}>
        <h3 className="text-base font-bold text-gray-900 mb-4">{title}</h3>
        {children}
      </div>
    </div>
  );
}
