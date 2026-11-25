"use client";

// 관리자 예약 관리: 완료된 예약 목록(최근 90일)과 완료 되돌리기
// 되돌리면 그 예약은 취소되고 수강권 1회가 복구된다. 확정으로는 돌아가지 않는다 (수업을 다시 잡으려면 새로 예약)
import React, { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/axios";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Loader2, Undo2, X } from "lucide-react";
import { adminNav } from "../nav";

type CompletedBooking = {
  id: number;
  when: string;
  topic: string | null;
  start_time: string | null;
  end_time: string | null;
  instructor_name: string | null;
  guest_name: string | null;
  updated_at: string;
};

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

// "11/20 (목) 10:00 ~ 12:00"
function lessonLine(b: CompletedBooking) {
  const [, m, d] = b.when.split("-").map(Number);
  const day = WEEKDAYS[new Date(b.when + "T00:00:00").getDay()];
  const time = b.start_time && b.end_time ? ` ${b.start_time.slice(0, 5)} ~ ${b.end_time.slice(0, 5)}` : "";
  return `${m}/${d} (${day})${time}`;
}

export default function AdminBookingsPage() {
  const [items, setItems] = useState<CompletedBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<CompletedBooking | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.get("/admin/bookings/completed");
      setItems(r.data ?? []);
      setError(null);
    } catch (e) {
      setError(apiErrorMessage(e, "완료된 예약을 불러오지 못했습니다."));
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  function open(b: CompletedBooking) { setTarget(b); setReason(""); setError(null); setNotice(null); }

  async function revert() {
    if (!target) return;
    setSaving(true);
    try {
      await api.patch(`/admin/bookings/${target.id}/revert-complete`, reason.trim() ? { reason: reason.trim() } : {});
      setNotice(`${target.guest_name ?? "고객"} · ${lessonLine(target)} 레슨의 완료를 취소하고 수강권 1회를 복구했습니다.`);
      setTarget(null);
      await load();
    } catch (e) {
      setError(apiErrorMessage(e, "되돌리지 못했습니다."));
      setTarget(null);
      await load();  // 그사이 상태가 바뀌었을 수 있다
    } finally { setSaving(false); }
  }

  return (
    <DashboardLayout
      navItems={adminNav}
      userLabel={{ initial: "A", name: "관리자", role: "Admin" }}
      headerFallback="예약 관리"
    >
      <div className="space-y-5 p-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">완료된 예약</h1>
          <p className="mt-1 text-sm text-gray-500">
            최근 90일 안에 수업한 완료 예약입니다. 잘못 완료된 예약은 되돌릴 수 있습니다. 되돌리면 예약은 취소되고 수강권 1회가 복구됩니다.
          </p>
        </div>

        {notice && <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">{notice}</div>}
        {error && <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>}

        {loading ? (
          <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-200 py-16 text-center text-sm text-gray-400">완료된 예약이 없습니다.</div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500">
                <tr>
                  <th className="px-4 py-3 font-medium">수업 일시</th>
                  <th className="px-4 py-3 font-medium">강사</th>
                  <th className="px-4 py-3 font-medium">고객</th>
                  <th className="px-4 py-3 font-medium">수업 내용</th>
                  <th className="px-4 py-3 font-medium">완료 처리한 날</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map(b => (
                  <tr key={b.id}>
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-gray-900">{lessonLine(b)}</td>
                    <td className="px-4 py-3 text-gray-700">{b.instructor_name ?? "-"}</td>
                    <td className="px-4 py-3 text-gray-700">{b.guest_name ?? "-"}</td>
                    <td className="px-4 py-3 text-gray-500">{b.topic ?? "-"}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-gray-500">{new Date(b.updated_at).toLocaleDateString("ko-KR")}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => open(b)}
                        className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                      >
                        <Undo2 className="h-3.5 w-3.5" /> 완료 되돌리기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {target && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between">
              <h2 className="text-lg font-bold text-gray-900">완료 되돌리기</h2>
              <button onClick={() => setTarget(null)} aria-label="닫기" className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
            </div>
            <p className="mt-3 text-sm text-gray-700">
              <span className="font-medium">{target.guest_name ?? "고객"}</span> · {lessonLine(target)} ({target.instructor_name ?? "강사"})
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-gray-600">
              <li>이 예약은 <span className="font-medium text-red-600">취소됨</span>으로 바뀝니다. 확정으로 돌아가지 않습니다.</li>
              <li>수강권 1회가 복구됩니다.</li>
              <li>강사와 고객에게 알림이 갑니다. 다시 되돌릴 수 없습니다.</li>
            </ul>
            <label className="mt-4 block text-sm font-medium text-gray-700" htmlFor="revert-reason">사유 (선택)</label>
            <input
              id="revert-reason"
              value={reason}
              onChange={e => setReason(e.target.value)}
              maxLength={200}
              placeholder="예: 다른 예약을 잘못 완료함"
              className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
            />
            <div className="mt-6 flex justify-end gap-2">
              <button onClick={() => setTarget(null)} disabled={saving} className="rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">닫기</button>
              <button onClick={revert} disabled={saving} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
                {saving ? "처리 중..." : "완료 취소하고 1회 복구"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
