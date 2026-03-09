// frontend/src/app/(protected)/instructor/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabaseBrowser } from "@/lib/supabase/client";
import { api } from "@/lib/axios";
import { Calendar, Users, Video, UserCog, LogOut, Loader2, Search, UserCheck, UserX, Phone } from "lucide-react";

type Me = {
  id?: string;
  email?: string;
  name?: string;
  role?: string;
};

type CustomerLookupResult = {
  id: string;
  display_name: string;
  username: string;
  phone: string | null;
  manager_id: string | null;
  manager_name: string | null;
  is_my_customer: boolean;
};

export default function InstructorPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  // 고객 전화번호 조회
  const [phone, setPhone] = useState("");
  const [lookupResult, setLookupResult] = useState<CustomerLookupResult | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignSuccess, setAssignSuccess] = useState(false);

  const handleLookup = async () => {
    const cleaned = phone.replace(/[^0-9]/g, "");
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
      if (e?.response?.status === 404) {
        setLookupError("해당 전화번호로 등록된 고객이 없습니다.");
      } else {
        setLookupError("조회 중 오류가 발생했습니다.");
      }
    } finally {
      setLookupLoading(false);
    }
  };

  const handleAssign = async () => {
    if (!lookupResult) return;
    setAssignLoading(true);
    try {
      await api.post(`/instructors/customers/${lookupResult.id}/assign`);
      setAssignSuccess(true);
      setLookupResult({ ...lookupResult, manager_id: me?.id ?? null, manager_name: me?.name ?? null });
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      if (e?.response?.status === 409) {
        setLookupError(e.response?.data?.detail ?? "이미 다른 강사의 담당 고객입니다.");
      } else {
        setLookupError("등록 중 오류가 발생했습니다.");
      }
    } finally {
      setAssignLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        const res = await api.get("/users/me");
        if (!mounted) return;
        setMe(res.data ?? null);
      } catch {
        // 세션/권한 이상이면 로그인으로 정리
        const supabase = supabaseBrowser();
        await supabase.auth.signOut({ scope: "local" });
        router.replace("/login");
        router.refresh();
      } finally {
        if (mounted) setLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [router]);

  const onLogout = async () => {
    try {
      const supabase = supabaseBrowser();
      await supabase.auth.signOut({ scope: "local" });
    } finally {
      router.replace("/login");
      router.refresh();
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="flex items-center gap-2 text-gray-700">
          <Loader2 className="animate-spin" />
          권한 확인 중...
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">강사용 페이지</h1>
              <p className="text-gray-600 mt-2">
                현재 강사용 화면은 준비 중입니다. (우선 404 방지 + 로그인/권한 흐름 안정화 목적)
              </p>
              <div className="text-sm text-gray-500 mt-3">
                {me?.email ? (
                  <>
                    계정: <span className="font-medium">{me.email}</span>
                    {me?.role ? (
                      <>
                        {" "}
                        · 역할: <span className="font-medium">{me.role}</span>
                      </>
                    ) : null}
                  </>
                ) : (
                  "계정 정보를 불러오지 못했습니다."
                )}
              </div>
            </div>

            <button
              onClick={onLogout}
              className="shrink-0 px-4 py-2 rounded-xl bg-white border border-gray-300 text-gray-800 hover:bg-gray-50 transition flex items-center gap-2"
            >
              <LogOut size={18} />
              로그아웃
            </button>
          </div>
        </div>

        {/* 고객 등록 — 전화번호 조회 */}
        <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 font-semibold text-gray-900">
            <Phone size={20} />
            고객 전화번호로 담당 고객 등록
          </div>
          <p className="text-sm text-gray-500">
            앱에 가입한 고객의 전화번호를 입력하면 해당 고객을 담당 고객으로 즉시 등록할 수 있습니다.
          </p>

          <div className="flex gap-2">
            <input
              type="tel"
              placeholder="010-1234-5678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLookup()}
              className="flex-1 border border-gray-300 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
            />
            <button
              onClick={handleLookup}
              disabled={lookupLoading || !phone}
              className="px-4 py-2 rounded-xl bg-gray-900 text-white text-sm hover:bg-gray-800 transition disabled:opacity-40 flex items-center gap-1"
            >
              {lookupLoading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              조회
            </button>
          </div>

          {lookupError && (
            <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 rounded-xl px-4 py-3">
              <UserX size={16} />
              {lookupError}
            </div>
          )}

          {lookupResult && (
            <div className="border border-gray-200 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-gray-900">{lookupResult.display_name}</div>
                  <div className="text-sm text-gray-500">@{lookupResult.username}</div>
                  {lookupResult.phone && (
                    <div className="text-sm text-gray-500">{lookupResult.phone}</div>
                  )}
                </div>
                {lookupResult.manager_id ? (
                  <div className="flex items-center gap-1 text-sm text-green-700 bg-green-50 px-3 py-1 rounded-full">
                    <UserCheck size={14} />
                    {assignSuccess ? "내 담당 고객" : `담당 강사 있음`}
                  </div>
                ) : (
                  <div className="text-sm text-gray-400 bg-gray-100 px-3 py-1 rounded-full">
                    담당 강사 없음
                  </div>
                )}
              </div>

              {assignSuccess ? (
                <div className="text-sm text-green-700 font-medium">
                  ✓ 담당 고객으로 등록되었습니다. 고객 앱에 즉시 반영됩니다.
                </div>
              ) : lookupResult.is_my_customer ? (
                <div className="text-sm text-green-700 font-medium">
                  이미 내 담당 고객입니다.
                </div>
              ) : lookupResult.manager_id ? (
                <div className="text-sm text-gray-500">
                  담당 강사: <span className="font-medium">{lookupResult.manager_name}</span>.
                  고객 동의 후 변경할 수 있습니다.
                </div>
              ) : (
                <button
                  onClick={handleAssign}
                  disabled={assignLoading}
                  className="w-full py-2 rounded-xl bg-gray-900 text-white text-sm hover:bg-gray-800 transition disabled:opacity-40 flex items-center justify-center gap-2"
                >
                  {assignLoading ? <Loader2 size={16} className="animate-spin" /> : <UserCheck size={16} />}
                  담당 고객으로 등록
                </button>
              )}
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card
            icon={<UserCog size={20} />}
            title="프로필 편집"
            desc="이름, 지역, 전문분야, 소개글을 수정합니다."
            action="프로필 편집"
            onClick={() => router.push("/instructor/profile")}
            highlight
          />
          <Card
            icon={<Calendar size={20} />}
            title="스케줄 관리"
            desc="예약 가능 시간대를 추가하거나 ON/OFF합니다."
            action="스케줄 관리"
            onClick={() => router.push("/instructor/schedule")}
            highlight
          />
          <Card
            icon={<Users size={20} />}
            title="고객 관리"
            desc="담당 고객 리스트를 확인합니다."
            action="고객 보기"
            onClick={() => router.push("/customers")}
          />
          <Card
            icon={<Video size={20} />}
            title="게시물 (준비중)"
            desc="콘텐츠 업로드/동의 플로우를 다음 단계에서 연결합니다."
            action="기획 확인"
            onClick={() => alert("게시물 기능은 다음 단계에서 연결합니다.")}
          />
        </div>
      </div>
    </div>
  );
}

function Card({
  icon, title, desc, action, onClick, highlight = false,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  action: string;
  onClick: () => void;
  highlight?: boolean;
}) {
  return (
    <div className={`rounded-2xl p-6 shadow-sm border ${highlight ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
      <div className={`flex items-center gap-2 font-semibold ${highlight ? "text-white" : "text-gray-900"}`}>
        {icon}
        {title}
      </div>
      <p className={`mt-2 text-sm ${highlight ? "text-gray-400" : "text-gray-600"}`}>{desc}</p>
      <button
        onClick={onClick}
        className={`mt-4 px-4 py-2 rounded-xl text-sm font-semibold transition ${
          highlight
            ? "bg-white text-gray-900 hover:bg-gray-100"
            : "bg-gray-900 text-white hover:bg-gray-800"
        }`}
      >
        {action}
      </button>
    </div>
  );
}
