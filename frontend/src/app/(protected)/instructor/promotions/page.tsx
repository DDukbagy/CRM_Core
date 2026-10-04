"use client";

// 강사 웹 프로모션 관리 (프로토타입): 할인·이벤트를 만들고 수정·중지·삭제. 고객 앱 수강권 탭에 진행 중인 것만 안내로 표시
// 결제 연동 전이라 실제 결제 금액에는 할인이 적용되지 않는다. 강사 앱은 확인만
import React, { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/axios";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { instructorNav } from "../page";
import { Loader2, Plus, X, Trash2 } from "lucide-react";

type Promotion = {
  id: number;
  pass_type_id: number | null;
  pass_type_name: string | null;
  pass_price: number | null;
  discounted_price: number | null;
  title: string;
  description: string | null;
  discount_type: "PERCENT" | "AMOUNT" | "NONE";
  discount_value: number;
  start_date: string;
  end_date: string;
  is_active: boolean;
  status: "SCHEDULED" | "ONGOING" | "ENDED" | "PAUSED";
};
type PassType = { id: number; name: string; price: number | null };

const STATUS: Record<Promotion["status"], { label: string; cls: string }> = {
  ONGOING: { label: "진행 중", cls: "bg-green-50 text-green-600" },
  SCHEDULED: { label: "예정", cls: "bg-blue-50 text-blue-600" },
  PAUSED: { label: "중지", cls: "bg-gray-100 text-gray-500" },
  ENDED: { label: "종료", cls: "bg-gray-100 text-gray-400" },
};

function discountLabel(p: Pick<Promotion, "discount_type" | "discount_value">) {
  if (p.discount_type === "PERCENT") return `${p.discount_value}% 할인`;
  if (p.discount_type === "AMOUNT") return `${p.discount_value.toLocaleString()}원 할인`;
  return "이벤트";
}

function errMsg(err: unknown, fallback: string) {
  const e = err as { response?: { data?: { error?: { message?: string; details?: { msg?: string }[] } } } };
  return e.response?.data?.error?.details?.[0]?.msg?.replace(/^Value error, /, "") ?? e.response?.data?.error?.message ?? fallback;
}

export default function PromotionsPage() {
  const [items, setItems] = useState<Promotion[]>([]);
  const [types, setTypes] = useState<PassType[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Promotion | "new" | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, t] = await Promise.all([api.get("/promotions/me"), api.get("/passes/types")]);
      setItems(p.data ?? []);
      setTypes(t.data ?? []);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function toggle(p: Promotion) {
    await api.patch(`/promotions/${p.id}`, { is_active: !p.is_active });
    load();
  }

  return (
    <DashboardLayout navItems={instructorNav} headerFallback="프로모션">
      <div className="space-y-5 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-500">할인·이벤트 프로모션</h2>
            <p className="mt-0.5 text-xs text-gray-400">진행 중인 프로모션은 담당 고객의 수강권 화면에 표시됩니다. (결제 연동 전 — 안내용)</p>
          </div>
          <button onClick={() => setEditing("new")}
            className="flex items-center gap-1.5 rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800">
            <Plus className="h-4 w-4" /> 프로모션 만들기
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-gray-200 bg-white py-16 text-center">
            <p className="text-sm font-semibold text-gray-600">등록된 프로모션이 없습니다</p>
            <p className="mt-1 text-xs text-gray-400">수강권 할인이나 이벤트를 만들어 고객에게 알려 보세요</p>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {items.map(p => (
              <div key={p.id} className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
                <div className="mb-2 flex items-center gap-2">
                  <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${STATUS[p.status].cls}`}>{STATUS[p.status].label}</span>
                  <span className="text-xs font-semibold text-orange-500">{discountLabel(p)}</span>
                </div>
                <p className="text-base font-bold text-gray-900">{p.title}</p>
                {p.description && <p className="mt-1 text-sm text-gray-500">{p.description}</p>}
                <p className="mt-2 text-xs text-gray-400">{p.start_date} ~ {p.end_date}</p>
                {p.pass_type_name && (
                  <p className="mt-1 text-xs text-gray-500">
                    대상: {p.pass_type_name}
                    {p.pass_price != null && p.discounted_price != null && (
                      <> · <span className="line-through">{p.pass_price.toLocaleString()}원</span> → <b className="text-gray-900">{p.discounted_price.toLocaleString()}원</b></>
                    )}
                  </p>
                )}
                <div className="mt-4 flex gap-2">
                  <button onClick={() => setEditing(p)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700">수정</button>
                  <button onClick={() => toggle(p)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700">
                    {p.is_active ? "중지" : "다시 켜기"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {editing && <PromotionModal target={editing} types={types} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </DashboardLayout>
  );
}

function PromotionModal({ target, types, onClose, onSaved }: {
  target: Promotion | "new"; types: PassType[]; onClose: () => void; onSaved: () => void;
}) {
  const p = target === "new" ? null : target;
  const today = new Date();
  const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const [form, setForm] = useState({
    title: p?.title ?? "",
    description: p?.description ?? "",
    pass_type_id: p?.pass_type_id ? String(p.pass_type_id) : "",
    discount_type: p?.discount_type ?? "PERCENT",
    discount_value: p ? String(p.discount_value) : "10",
    start_date: p?.start_date ?? iso(today),
    end_date: p?.end_date ?? iso(new Date(today.getTime() + 30 * 86400000)),
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  async function save() {
    setError("");
    if (!form.title.trim()) { setError("제목을 입력해주세요."); return; }
    setBusy(true);
    const body = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      pass_type_id: form.pass_type_id ? Number(form.pass_type_id) : null,
      discount_type: form.discount_type,
      discount_value: form.discount_type === "NONE" ? 0 : Number(form.discount_value || 0),
      start_date: form.start_date,
      end_date: form.end_date,
    };
    try {
      if (p) await api.patch(`/promotions/${p.id}`, body);
      else await api.post("/promotions", body);
      onSaved();
    } catch (e) { setError(errMsg(e, "저장하지 못했습니다.")); } finally { setBusy(false); }
  }

  async function remove() {
    if (!p || !window.confirm("이 프로모션을 삭제할까요?")) return;
    try { await api.delete(`/promotions/${p.id}`); onSaved(); } catch (e) { setError(errMsg(e, "삭제 실패")); }
  }

  const input = "w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900";
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-base font-bold text-gray-900">{p ? "프로모션 수정" : "프로모션 만들기"}</h3>
          <button onClick={onClose} className="rounded-lg p-1 hover:bg-gray-100"><X className="h-5 w-5 text-gray-500" /></button>
        </div>
        <div className="space-y-4">
          <Field label="제목"><input value={form.title} onChange={set("title")} maxLength={100} placeholder="예: 가을맞이 10회권 할인" className={input} /></Field>
          <Field label="설명 (선택)"><textarea value={form.description} onChange={set("description")} rows={3} placeholder="고객에게 보여 줄 안내 문구" className={input} /></Field>
          <Field label="대상 수강권 (선택)">
            <select value={form.pass_type_id} onChange={set("pass_type_id")} className={input}>
              <option value="">전체 (특정 수강권 아님)</option>
              {types.map(t => <option key={t.id} value={t.id}>{t.name}{t.price != null ? ` · ${t.price.toLocaleString()}원` : ""}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="할인 방식">
              <select value={form.discount_type} onChange={set("discount_type")} className={input}>
                <option value="PERCENT">비율 (%)</option>
                <option value="AMOUNT">금액 (원)</option>
                <option value="NONE">할인 없는 이벤트</option>
              </select>
            </Field>
            <Field label={form.discount_type === "PERCENT" ? "할인율 (%)" : "할인 금액 (원)"}>
              <input type="number" min={0} value={form.discount_value} onChange={set("discount_value")} disabled={form.discount_type === "NONE"} className={`${input} disabled:bg-gray-50`} />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="시작일"><input type="date" value={form.start_date} onChange={set("start_date")} className={input} /></Field>
            <Field label="종료일"><input type="date" value={form.end_date} onChange={set("end_date")} className={input} /></Field>
          </div>
          {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
          <div className="flex gap-2 pt-2">
            {p && <button onClick={remove} className="flex items-center gap-1 rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-600"><Trash2 className="h-4 w-4" /> 삭제</button>}
            <button onClick={save} disabled={busy} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gray-900 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
              {busy && <Loader2 className="h-4 w-4 animate-spin" />} 저장
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="mb-1.5 block text-xs font-semibold text-gray-600">{label}</label>{children}</div>;
}
