"use client";

import React, { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/axios";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { instructorNav } from "../page";
import { Loader2, Plus, X, TrendingUp, CreditCard } from "lucide-react";

type Payment = {
  id: string;
  amount: number;
  method: string;
  status: string;
  created_at: string;
  customer_id: string;
};

type InstructorStats = {
  customer_count: number;
  booking_count: number;
  completed_count: number;
  requested_count: number;
};

const METHODS = ["CASH", "TRANSFER", "TOSS", "KAKAO", "NAVER"];
const METHOD_LABEL: Record<string, string> = {
  CASH: "현금", TRANSFER: "계좌이체", TOSS: "토스", KAKAO: "카카오페이", NAVER: "네이버페이",
};
const STATUS_LABEL: Record<string, string> = {
  COMPLETED: "완료", PENDING: "대기", FAILED: "실패", REFUNDED: "환불",
};

export default function RevenuePage() {
  const [stats, setStats] = useState<InstructorStats | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ customer_id: "", amount: "", method: "CASH", membership_id: "" });
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([
        api.get("/instructors/me/stats"),
        api.get("/payments"),
      ]);
      setStats(s.data);
      setPayments(p.data ?? []);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const completed = payments.filter(p => p.status === "COMPLETED");
  const totalRevenue = completed.reduce((sum, p) => sum + p.amount, 0);

  const handleRecord = async () => {
    if (!form.customer_id.trim()) { setFormError("고객 ID를 입력해주세요."); return; }
    const amount = parseInt(form.amount);
    if (isNaN(amount) || amount <= 0) { setFormError("올바른 금액을 입력해주세요."); return; }
    setSubmitting(true);
    setFormError("");
    try {
      const body: Record<string, unknown> = {
        customer_id: form.customer_id.trim(),
        amount,
        method: form.method,
      };
      if (form.membership_id.trim()) body.membership_id = form.membership_id.trim();
      await api.post("/payments", body);
      setShowModal(false);
      setForm({ customer_id: "", amount: "", method: "CASH", membership_id: "" });
      await load();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setFormError(e?.response?.data?.detail ?? "등록 실패");
    } finally { setSubmitting(false); }
  };

  return (
    <DashboardLayout navItems={instructorNav} headerFallback="매출 관리">
      <div className="space-y-6">
        {/* 요약 카드 */}
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gray-400" /></div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-green-600 rounded-2xl p-6 text-white col-span-1 sm:col-span-2">
                <div className="flex items-center gap-2 text-green-100 text-sm mb-1">
                  <TrendingUp size={15} /> 완료된 결제 총액
                </div>
                <p className="text-3xl font-bold mt-1">{totalRevenue.toLocaleString()}원</p>
                <p className="text-green-100 text-xs mt-2">
                  완료 {completed.length}건 · 담당 고객 {stats?.customer_count ?? 0}명
                </p>
              </div>
              <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm">
                <p className="text-xs text-gray-400 font-semibold uppercase tracking-wider mb-3">결제 현황</p>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-sm"><span className="text-gray-500">전체</span><span className="font-semibold">{payments.length}건</span></div>
                  <div className="flex justify-between text-sm"><span className="text-gray-500">완료</span><span className="font-semibold text-green-600">{completed.length}건</span></div>
                  <div className="flex justify-between text-sm"><span className="text-gray-500">대기</span><span className="font-semibold text-yellow-600">{payments.filter(p => p.status === "PENDING").length}건</span></div>
                </div>
              </div>
            </div>

            {/* 결제 내역 */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider">
                  결제 내역 <span className="ml-1 bg-gray-100 text-gray-600 text-xs font-bold px-2 py-0.5 rounded-full">{payments.length}</span>
                </h2>
                <button
                  onClick={() => { setForm({ customer_id: "", amount: "", method: "CASH", membership_id: "" }); setFormError(""); setShowModal(true); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 text-white rounded-xl text-xs font-semibold hover:bg-gray-800 transition"
                >
                  <Plus size={14} /> 수동 등록
                </button>
              </div>

              {payments.length === 0 ? (
                <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center text-gray-400 text-sm">
                  결제 내역이 없습니다.
                </div>
              ) : (
                <div className="space-y-2">
                  {payments.map(p => (
                    <div key={p.id} className="bg-white border border-gray-100 rounded-2xl p-4 flex items-center gap-4 shadow-sm">
                      <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center shrink-0">
                        <CreditCard size={16} className="text-gray-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-bold text-gray-900">{p.amount.toLocaleString()}원</p>
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                            p.status === "COMPLETED" ? "bg-green-100 text-green-700" :
                            p.status === "PENDING" ? "bg-yellow-100 text-yellow-700" :
                            "bg-gray-100 text-gray-500"
                          }`}>
                            {STATUS_LABEL[p.status] ?? p.status}
                          </span>
                        </div>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {METHOD_LABEL[p.method] ?? p.method} · {p.created_at.slice(0, 10)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* 수동 등록 모달 */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-bold text-gray-900">결제 수동 등록</h3>
              <button onClick={() => setShowModal(false)} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">고객 ID (UUID)</label>
                <input
                  type="text"
                  placeholder="고객 UUID 입력"
                  value={form.customer_id}
                  onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))}
                  className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">금액 (원)</label>
                <input
                  type="number"
                  placeholder="100000"
                  value={form.amount}
                  onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
                  className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">결제 수단</label>
                <div className="flex flex-wrap gap-2">
                  {METHODS.map(m => (
                    <button
                      key={m}
                      onClick={() => setForm(f => ({ ...f, method: m }))}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium border transition ${
                        form.method === m
                          ? "bg-gray-900 text-white border-gray-900"
                          : "bg-white text-gray-600 border-gray-300 hover:border-gray-500"
                      }`}
                    >
                      {METHOD_LABEL[m]}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">수강권 ID (선택)</label>
                <input
                  type="text"
                  placeholder="수강권 UUID (선택)"
                  value={form.membership_id}
                  onChange={e => setForm(f => ({ ...f, membership_id: e.target.value }))}
                  className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                />
              </div>
            </div>

            {formError && <p className="mt-3 text-xs text-red-600">{formError}</p>}

            <button
              onClick={handleRecord}
              disabled={submitting}
              className="mt-5 w-full py-3 rounded-xl bg-gray-900 text-white text-sm font-bold hover:bg-gray-800 transition disabled:opacity-40 flex items-center justify-center gap-2"
            >
              {submitting ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} 등록
            </button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
