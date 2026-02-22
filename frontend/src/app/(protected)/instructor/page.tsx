// frontend/src/app/(protected)/instructor/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabaseBrowser } from "@/lib/supabase/client";
import { api } from "@/lib/axios";
import { Calendar, Users, Video, Settings, LogOut, Loader2 } from "lucide-react";

type Me = {
  id?: string;
  email?: string;
  name?: string;
  role?: string;
};

export default function InstructorPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

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

        {/* Quick actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card
            icon={<Calendar size={20} />}
            title="스케줄"
            desc="오늘 수업/예약을 확인합니다."
            action="스케줄 보기"
            onClick={() => router.push("/schedule")}
          />
          <Card
            icon={<Users size={20} />}
            title="고객"
            desc="고객 리스트/메모/진행상태를 관리합니다."
            action="고객 보기"
            onClick={() => router.push("/customers")}
          />
          <Card
            icon={<Video size={20} />}
            title="영상/게시물(준비중)"
            desc="콘텐츠 업로드/동의 플로우를 다음 단계에서 연결합니다."
            action="기획 확인"
            onClick={() => alert("게시물 기능은 다음 단계에서 연결합니다.")}
          />
          <Card
            icon={<Settings size={20} />}
            title="Forbidden UX 확인"
            desc="권한이 없을 때 안내/로그아웃 UX를 확인합니다."
            action="forbidden 보기"
            onClick={() => router.push("/forbidden")}
          />
        </div>

        {/* Next steps */}
        <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
          <div className="font-semibold text-gray-900">다음 개발 순서(추천)</div>
          <ol className="mt-2 list-decimal ml-5 text-gray-700 space-y-1">
            <li>proxy.ts에서 ADMIN/INSTRUCTOR 역할 기반 접근 차단(서버 레벨)</li>
            <li>/forbidden UX 확정(역할별 안내 + 로그아웃 + 홈 이동)</li>
            <li>강사용 실제 기능 라우트 연결(스케줄/고객/게시물)</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

function Card({
  icon,
  title,
  desc,
  action,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  action: string;
  onClick: () => void;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center gap-2 font-semibold text-gray-900">
        {icon}
        {title}
      </div>
      <p className="text-gray-600 mt-2">{desc}</p>
      <button
        onClick={onClick}
        className="mt-4 px-4 py-2 rounded-xl bg-gray-900 text-white hover:bg-gray-800 transition"
      >
        {action}
      </button>
    </div>
  );
}
