// frontend/src/app/forbidden/page.tsx
"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabaseBrowser } from "@/lib/supabase/client";
import { api } from "@/lib/axios";
import { ShieldAlert, LogOut, Home, Loader2 } from "lucide-react";

type Me = {
  role?: string;
  email?: string;
  name?: string;
};

type Need = "ADMIN" | "INSTRUCTOR" | null;

function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="flex items-center gap-2 text-gray-700">
        <Loader2 className="animate-spin" />
        권한 확인 중...
      </div>
    </div>
  );
}

function ForbiddenInner() {
  const router = useRouter();
  const params = useSearchParams();

  const need = useMemo<Need>(() => {
    const raw = params.get("need");
    if (raw === "ADMIN" || raw === "INSTRUCTOR") return raw;
    return null;
  }, [params]);

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
        // 세션이 없거나 깨졌으면 로그인으로
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

  const roleText = useMemo(() => {
    if (me?.role === "ADMIN") return "관리자";
    if (me?.role === "INSTRUCTOR") return "강사";
    if (me?.role) return me.role;
    return "알 수 없음";
  }, [me?.role]);

  const title = useMemo(() => {
    if (need === "ADMIN") return "관리자 전용 페이지입니다";
    if (need === "INSTRUCTOR") return "강사 전용 페이지입니다";
    return "접근 권한이 없습니다";
  }, [need]);

  const description = useMemo(() => {
    if (need === "ADMIN") {
      return "현재 계정 권한으로는 관리자 페이지에 접근할 수 없습니다. 관리자 계정으로 로그인해 주세요.";
    }
    if (need === "INSTRUCTOR") {
      return "현재 계정 권한으로는 강사 페이지에 접근할 수 없습니다. 강사 계정으로 로그인해 주세요.";
    }
    return "현재 계정 권한으로는 요청하신 페이지에 접근할 수 없습니다.";
  }, [need]);

  const goHomeByRole = () => {
    if (me?.role === "ADMIN") {
      router.replace("/admin");
      return;
    }
    if (me?.role === "INSTRUCTOR") {
      router.replace("/instructor");
      return;
    }
    router.replace("/login");
  };

  const logout = async () => {
    try {
      const supabase = supabaseBrowser();
      await supabase.auth.signOut({ scope: "local" });
    } finally {
      router.replace("/login");
      router.refresh();
    }
  };

  if (loading) return <LoadingScreen />;

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-lg w-full bg-white border border-gray-200 rounded-2xl p-8 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-red-50 flex items-center justify-center text-red-600">
            <ShieldAlert />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{title}</h1>
            <p className="text-gray-600 mt-1">{description}</p>
          </div>
        </div>

        <div className="mt-5 bg-gray-50 border border-gray-100 rounded-xl p-4 text-sm text-gray-700">
          <div>
            현재 권한: <b>{roleText}</b>
          </div>
          {me?.email ? <div className="mt-1 text-gray-500">계정: {me.email}</div> : null}
          {need ? (
            <div className="mt-2">
              필요 권한: <b>{need === "ADMIN" ? "관리자" : "강사"}</b>
            </div>
          ) : null}
        </div>

        <div className="mt-6 flex gap-3">
          <button
            onClick={goHomeByRole}
            className="flex-1 px-4 py-3 rounded-xl bg-gray-900 text-white hover:bg-gray-800 transition flex items-center justify-center gap-2"
          >
            <Home size={18} />
            내 홈으로 이동
          </button>

          <button
            onClick={logout}
            className="flex-1 px-4 py-3 rounded-xl bg-white border border-gray-300 text-gray-800 hover:bg-gray-50 transition flex items-center justify-center gap-2"
          >
            <LogOut size={18} />
            로그아웃
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ForbiddenPage() {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <ForbiddenInner />
    </Suspense>
  );
}