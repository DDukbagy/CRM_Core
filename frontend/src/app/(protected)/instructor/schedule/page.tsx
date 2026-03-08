// frontend/src/app/(protected)/instructor/schedule/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/axios";
import { ArrowLeft, Plus, Trash2, Loader2, ToggleLeft, ToggleRight, AlertCircle } from "lucide-react";

const DAYS = ["월", "화", "수", "목", "금", "토", "일"];  // 0=월 ... 6=일

type Slot = {
  id: number;
  start_time: string;   // "HH:MM:SS"
  end_time: string;
  weekdays: number[];
  is_active: boolean;
};

type NewSlotForm = {
  start_time: string;
  end_time: string;
  weekdays: number[];
};

const EMPTY_FORM: NewSlotForm = {
  start_time: "10:00",
  end_time: "11:00",
  weekdays: [1, 2, 3, 4, 5],  // 기본 평일
};

function fmtTime(t: string) {
  // "10:00:00" → "10:00"
  return t.slice(0, 5);
}

export default function InstructorSchedulePage() {
  const router = useRouter();
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<NewSlotForm>({ ...EMPTY_FORM });
  const [adding, setAdding] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const res = await api.get("/calendars/me/time-slots");
      setSlots(res.data);
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } };
      if (err?.response?.status === 404) {
        // 캘린더 없음 → 빈 목록
        setSlots([]);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const toggleDay = (d: number) => {
    setForm((f) => ({
      ...f,
      weekdays: f.weekdays.includes(d) ? f.weekdays.filter((x) => x !== d) : [...f.weekdays, d].sort(),
    }));
  };

  const handleAdd = async () => {
    if (form.weekdays.length === 0) { setError("요일을 최소 1개 선택하세요."); return; }
    if (form.start_time >= form.end_time) { setError("종료 시간은 시작 시간보다 늦어야 합니다."); return; }
    setAdding(true);
    setError(null);
    try {
      await api.post("/calendars/me/time-slots", {
        start_time: form.start_time,
        end_time: form.end_time,
        weekdays: form.weekdays,
        is_active: true,
      });
      setForm({ ...EMPTY_FORM });
      setShowForm(false);
      await load();
    } catch {
      setError("슬롯 추가에 실패했습니다.");
    } finally {
      setAdding(false);
    }
  };

  const handleToggle = async (slot: Slot) => {
    setTogglingId(slot.id);
    try {
      await api.patch(`/calendars/me/time-slots/${slot.id}`, { is_active: !slot.is_active });
      setSlots((prev) =>
        prev.map((s) => s.id === slot.id ? { ...s, is_active: !s.is_active } : s)
      );
    } catch {
      setError("상태 변경에 실패했습니다.");
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (slot: Slot) => {
    if (!confirm(`이 슬롯(${fmtTime(slot.start_time)}~${fmtTime(slot.end_time)})을 삭제하시겠습니까?\n예약이 있으면 삭제할 수 없습니다.`)) return;
    setDeletingId(slot.id);
    try {
      await api.delete(`/calendars/me/time-slots/${slot.id}`);
      setSlots((prev) => prev.filter((s) => s.id !== slot.id));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "삭제에 실패했습니다. 해당 슬롯에 예약이 있는지 확인하세요.");
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="animate-spin text-gray-400" size={28} />
      </div>
    );
  }

  const activeSlots = slots.filter((s) => s.is_active);
  const inactiveSlots = slots.filter((s) => !s.is_active);

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="max-w-xl mx-auto space-y-6">

        {/* 헤더 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => router.back()} className="p-2 rounded-xl hover:bg-gray-200 transition">
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-xl font-bold text-gray-900">스케줄 관리</h1>
              <p className="text-xs text-gray-500 mt-0.5">반복 시간대를 설정하면 고객이 예약 신청할 수 있습니다</p>
            </div>
          </div>
          <button
            onClick={() => { setShowForm(true); setError(null); }}
            className="flex items-center gap-1.5 px-4 py-2 bg-gray-900 text-white rounded-xl text-sm font-semibold hover:bg-gray-800 transition"
          >
            <Plus size={16} /> 추가
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 rounded-xl px-4 py-3">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* 슬롯 추가 폼 */}
        {showForm && (
          <div className="bg-white border-2 border-gray-900 rounded-2xl p-5 shadow-sm space-y-4">
            <p className="font-semibold text-gray-900">새 시간대 추가</p>

            {/* 요일 선택 */}
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-2">예약 가능 요일</label>
              <div className="flex gap-1.5">
                {DAYS.map((d, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => toggleDay(i)}
                    className={`w-10 h-10 rounded-full text-sm font-semibold transition ${
                      form.weekdays.includes(i)
                        ? "bg-gray-900 text-white"
                        : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* 시간 선택 */}
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <label className="block text-xs font-semibold text-gray-500 mb-1.5">시작 시간</label>
                <input
                  type="time"
                  value={form.start_time}
                  onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-gray-900"
                />
              </div>
              <span className="text-gray-400 mt-5">~</span>
              <div className="flex-1">
                <label className="block text-xs font-semibold text-gray-500 mb-1.5">종료 시간</label>
                <input
                  type="time"
                  value={form.end_time}
                  onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-gray-900"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => { setShowForm(false); setError(null); }}
                className="flex-1 py-2.5 rounded-xl border border-gray-300 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition"
              >
                취소
              </button>
              <button
                onClick={handleAdd}
                disabled={adding}
                className="flex-1 py-2.5 rounded-xl bg-gray-900 text-white text-sm font-semibold hover:bg-gray-800 transition disabled:opacity-50 flex items-center justify-center gap-1"
              >
                {adding ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                추가하기
              </button>
            </div>
          </div>
        )}

        {/* 활성 슬롯 */}
        {activeSlots.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-1">활성 시간대 ({activeSlots.length})</p>
            {activeSlots.map((slot) => (
              <SlotCard
                key={slot.id}
                slot={slot}
                toggling={togglingId === slot.id}
                deleting={deletingId === slot.id}
                onToggle={() => handleToggle(slot)}
                onDelete={() => handleDelete(slot)}
              />
            ))}
          </div>
        )}

        {/* 비활성 슬롯 */}
        {inactiveSlots.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-1">비활성 시간대 ({inactiveSlots.length})</p>
            {inactiveSlots.map((slot) => (
              <SlotCard
                key={slot.id}
                slot={slot}
                toggling={togglingId === slot.id}
                deleting={deletingId === slot.id}
                onToggle={() => handleToggle(slot)}
                onDelete={() => handleDelete(slot)}
              />
            ))}
          </div>
        )}

        {slots.length === 0 && !showForm && (
          <div className="bg-white border border-gray-200 rounded-2xl p-10 text-center">
            <p className="text-gray-400 text-sm">등록된 시간대가 없습니다.</p>
            <p className="text-gray-400 text-sm mt-1">위의 <strong>추가</strong> 버튼을 눌러 시작하세요.</p>
          </div>
        )}

        {/* 안내 */}
        <div className="bg-blue-50 border border-blue-100 rounded-2xl p-4 text-sm text-blue-700 space-y-1">
          <p className="font-semibold">💡 이용 안내</p>
          <p>• 토글로 시간대를 일시적으로 비활성화할 수 있습니다</p>
          <p>• 예약이 있는 슬롯은 삭제할 수 없습니다 (비활성화 사용)</p>
          <p>• 변경사항은 고객 앱에 즉시 반영됩니다</p>
        </div>
      </div>
    </div>
  );
}

function SlotCard({
  slot, toggling, deleting, onToggle, onDelete,
}: {
  slot: Slot;
  toggling: boolean;
  deleting: boolean;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const activeDays = slot.weekdays.map((d) => DAYS[d]).join("  ");

  return (
    <div className={`bg-white border rounded-2xl p-4 shadow-sm transition ${
      slot.is_active ? "border-gray-200" : "border-gray-100 opacity-60"
    }`}>
      <div className="flex items-center justify-between">
        {/* 시간 + 요일 */}
        <div>
          <p className={`text-lg font-bold ${slot.is_active ? "text-gray-900" : "text-gray-400"}`}>
            {fmtTime(slot.start_time)} ~ {fmtTime(slot.end_time)}
          </p>
          <p className="text-sm text-gray-500 mt-0.5">{activeDays || "요일 없음"}</p>
        </div>

        {/* 토글 + 삭제 */}
        <div className="flex items-center gap-2">
          <button
            onClick={onToggle}
            disabled={toggling}
            className="text-gray-400 hover:text-gray-700 transition disabled:opacity-40"
            title={slot.is_active ? "비활성화" : "활성화"}
          >
            {toggling
              ? <Loader2 size={22} className="animate-spin" />
              : slot.is_active
                ? <ToggleRight size={28} className="text-green-500" />
                : <ToggleLeft size={28} />
            }
          </button>
          <button
            onClick={onDelete}
            disabled={deleting}
            className="text-gray-300 hover:text-red-500 transition disabled:opacity-40 p-1"
            title="삭제"
          >
            {deleting ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
