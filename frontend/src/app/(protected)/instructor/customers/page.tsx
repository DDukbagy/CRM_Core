"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/axios";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { instructorNav } from "../page";
import { Loader2, Search, UserPlus, Phone, Mail, X } from "lucide-react";

type Customer = {
  id: string;
  display_name: string;
  username: string;
  email: string | null;
  phone: string | null;
  lesson_purpose: string | null;
  manager_id: string | null;
};

export default function CustomersPage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  // 전화번호 조회 등록
  const [lookupPhone, setLookupPhone] = useState("");
  const [lookupResult, setLookupResult] = useState<{
    id: string; display_name: string; username: string; phone: string | null;
    manager_id: string | null; manager_name: string | null; is_my_customer: boolean;
  } | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignSuccess, setAssignSuccess] = useState(false);

  // 이메일 등록 모달
  const [registerModal, setRegisterModal] = useState(false);
  const [email, setEmail] = useState("");
  const [registerLoading, setRegisterLoading] = useState(false);
  const [registerError, setRegisterError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await api.get("/users?limit=100");
      const items: Customer[] = res.data?.items ?? [];
      setCustomers(items.filter(u => u.manager_id !== null));
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = customers.filter(c =>
    c.display_name.includes(search) ||
    (c.phone ?? "").includes(search) ||
    (c.email ?? "").includes(search)
  );

  const handleLookup = async () => {
    const cleaned = lookupPhone.replace(/[^0-9]/g, "");
    if (!cleaned) return;
    setLookupLoading(true);
    setLookupResult(null);
    setLookupError(null);
    setAssignSuccess(false);
    try {
      const res = await api.get("/instructors/customers/lookup", { params: { phone: cleaned } });
      setLookupResult(res.data);
    } catch (err: unknown) {
      const e = err as { response?: { status?: number } };
      setLookupError(e?.response?.status === 404 ? "해당 전화번호로 등록된 고객이 없습니다." : "조회 중 오류가 발생했습니다.");
    } finally { setLookupLoading(false); }
  };

  const handleAssign = async () => {
    if (!lookupResult) return;
    setAssignLoading(true);
    try {
      await api.post(`/instructors/customers/${lookupResult.id}/assign`);
      setAssignSuccess(true);
      await load();
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      setLookupError(e?.response?.status === 409 ? (e.response?.data?.detail ?? "이미 다른 강사의 담당 고객입니다.") : "등록 중 오류가 발생했습니다.");
    } finally { setAssignLoading(false); }
  };

  const handleRegisterByEmail = async () => {
    const trimmed = email.trim();
    if (!trimmed) { setRegisterError("이메일을 입력해주세요."); return; }
    setRegisterLoading(true);
    setRegisterError("");
    try {
      await api.post("/users/me/customers", { email: trimmed });
      setRegisterModal(false);
      setEmail("");
      await load();
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      if (e?.response?.status === 404) setRegisterError("해당 고객을 찾을 수 없습니다.");
      else setRegisterError(e?.response?.data?.detail ?? "오류가 발생했습니다.");
    } finally { setRegisterLoading(false); }
  };

  return (
    <DashboardLayout navItems={instructorNav} headerFallback="고객 관리">
      <div className="space-y-6">
        {/* 전화번호 조회 등록 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 font-semibold text-gray-900 mb-1">
            <Phone size={18} /> 전화번호로 담당 고객 등록
          </div>
          <p className="text-xs text-gray-400 mb-4">앱에 가입한 고객의 전화번호로 바로 담당 고객으로 등록합니다.</p>
          <div className="flex gap-2">
            <input
              type="tel"
              placeholder="010-1234-5678"
              value={lookupPhone}
              onChange={e => setLookupPhone(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleLookup()}
              className="flex-1 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
            />
            <button
              onClick={handleLookup}
              disabled={lookupLoading || !lookupPhone}
              className="px-4 py-2 rounded-xl bg-gray-900 text-white text-sm hover:bg-gray-800 transition disabled:opacity-40 flex items-center gap-1"
            >
              {lookupLoading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} 조회
            </button>
          </div>

          {lookupError && <p className="mt-2 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{lookupError}</p>}

          {lookupResult && (
            <div className="mt-3 border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold text-gray-900">{lookupResult.display_name}</p>
                  <p className="text-xs text-gray-400">@{lookupResult.username}</p>
                  {lookupResult.phone && <p className="text-xs text-gray-400">{lookupResult.phone}</p>}
                </div>
                {lookupResult.manager_id ? (
                  <span className="text-xs font-semibold bg-green-50 text-green-700 px-3 py-1 rounded-full">
                    {assignSuccess ? "내 담당 고객" : "담당 강사 있음"}
                  </span>
                ) : (
                  <span className="text-xs bg-gray-100 text-gray-400 px-3 py-1 rounded-full">담당 강사 없음</span>
                )}
              </div>
              {assignSuccess ? (
                <p className="text-sm text-green-700 font-medium mt-2">✓ 담당 고객으로 등록되었습니다.</p>
              ) : lookupResult.is_my_customer ? (
                <p className="text-sm text-green-700 mt-2">이미 내 담당 고객입니다.</p>
              ) : lookupResult.manager_id ? (
                <p className="text-sm text-gray-500 mt-2">담당 강사: <strong>{lookupResult.manager_name}</strong></p>
              ) : (
                <button
                  onClick={handleAssign}
                  disabled={assignLoading}
                  className="mt-3 w-full py-2 rounded-xl bg-gray-900 text-white text-sm font-semibold hover:bg-gray-800 transition disabled:opacity-40 flex items-center justify-center gap-2"
                >
                  {assignLoading ? <Loader2 size={15} className="animate-spin" /> : <UserPlus size={15} />} 담당 고객으로 등록
                </button>
              )}
            </div>
          )}
        </div>

        {/* 고객 목록 */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider">
              담당 고객 목록 <span className="ml-1 bg-gray-100 text-gray-600 text-xs font-bold px-2 py-0.5 rounded-full">{customers.length}</span>
            </h2>
            <button
              onClick={() => { setEmail(""); setRegisterError(""); setRegisterModal(true); }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 text-white rounded-xl text-xs font-semibold hover:bg-gray-800 transition"
            >
              <UserPlus size={14} /> 이메일로 등록
            </button>
          </div>

          <div className="relative mb-3">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="이름 / 전화번호 / 이메일 검색"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
            />
          </div>

          {loading ? (
            <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gray-400" /></div>
          ) : filtered.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center text-gray-400 text-sm">담당 고객이 없습니다.</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filtered.map(c => (
                <button
                  key={c.id}
                  onClick={() => router.push(`/instructor/customers/${c.id}`)}
                  className="bg-white border border-gray-100 rounded-2xl p-4 flex items-center gap-3 hover:border-gray-300 hover:shadow-sm transition text-left"
                >
                  <div className="w-11 h-11 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                    <span className="text-lg font-bold text-green-600">{c.display_name.charAt(0)}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-gray-900 truncate">{c.display_name}</p>
                    {c.phone && <p className="text-xs text-gray-400 flex items-center gap-1"><Phone size={10} />{c.phone}</p>}
                    {c.email && <p className="text-xs text-gray-400 flex items-center gap-1"><Mail size={10} />{c.email}</p>}
                    {c.lesson_purpose && <p className="text-xs text-gray-300 truncate mt-0.5">{c.lesson_purpose}</p>}
                  </div>
                  <span className="text-gray-300 text-lg">›</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 이메일 등록 모달 */}
      {registerModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setRegisterModal(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-bold text-gray-900">고객 이메일로 등록</h3>
              <button onClick={() => setRegisterModal(false)} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <label className="block text-xs font-semibold text-gray-600 mb-1.5">고객 이메일</label>
            <input
              type="email"
              placeholder="customer@example.com"
              value={email}
              onChange={e => { setEmail(e.target.value); setRegisterError(""); }}
              onKeyDown={e => e.key === "Enter" && handleRegisterByEmail()}
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 mb-2"
            />
            {registerError && <p className="text-xs text-red-600 mb-2">{registerError}</p>}
            <button
              onClick={handleRegisterByEmail}
              disabled={registerLoading}
              className="w-full py-3 rounded-xl bg-gray-900 text-white text-sm font-bold hover:bg-gray-800 transition disabled:opacity-40 flex items-center justify-center gap-2 mt-2"
            >
              {registerLoading ? <Loader2 size={16} className="animate-spin" /> : <UserPlus size={16} />} 등록
            </button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
