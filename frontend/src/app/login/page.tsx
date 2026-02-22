// frontend/src/app/login/page.tsx
"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/axios";
import { Lock, User, Loader2, ArrowRight } from "lucide-react";
import { supabaseBrowser } from "@/lib/supabase/client";

function sanitizeNext(raw: string | null): string | null {
  if (!raw) return null;

  // 외부 URL 방지 (open redirect 차단)
  // next는 반드시 "/..." 형태만 허용
  if (!raw.startsWith("/")) return null;
  if (raw.startsWith("//")) return null;
  if (raw.includes("://")) return null;

  return raw;
}

function pickRedirectPath(role: string | undefined, nextPath: string | null): string | null {
  // 역할별로 허용할 next 범위를 제한
  if (role === "ADMIN") {
    if (nextPath && (nextPath === "/admin" || nextPath.startsWith("/admin/"))) return nextPath;
    return "/admin";
  }

  if (role === "INSTRUCTOR") {
    if (nextPath && (nextPath === "/instructor" || nextPath.startsWith("/instructor/"))) return nextPath;
    return "/instructor";
  }

  return null;
}

function LoginFallback() {
  // 단순 fallback
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="flex items-center gap-2 text-gray-700">
        <Loader2 className="animate-spin" />
        Loading...
      </div>
    </div>
  );
}

function LoginInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const supabase = supabaseBrowser();

  const nextParam = sanitizeNext(searchParams.get("next"));

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const [formData, setFormData] = useState({
    username: "",
    password: "",
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError("");
  };

  // 이미 세션 있으면 바로 role 체크
  useEffect(() => {
    let mounted = true;

    (async () => {
      const { data } = await supabase.auth.getSession();
      if (!mounted) return;
      if (data.session) {
        await redirectByRole();
      }
    })();

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const redirectByRole = async () => {
    try {
      const res = await api.get("/users/me");
      const role = res.data?.role as string | undefined;

      const target = pickRedirectPath(role, nextParam);

      if (target) {
        router.replace(target);
        return;
      }

      await supabase.auth.signOut({ scope: "local" });
      setError("일반 회원은 관리자 웹페이지에 접속할 수 없습니다.");
    } catch {
      await supabase.auth.signOut({ scope: "local" });
      setError("권한 정보를 불러오지 못했습니다. 다시 로그인 해주세요.");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const email = formData.username;

      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password: formData.password,
      });

      if (signInError) {
        setError(signInError.message || "로그인 실패");
        return;
      }

      await redirectByRole();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl overflow-hidden border border-gray-100">
        <div className="bg-indigo-900 px-8 py-10 text-center">
          <div className="mx-auto w-16 h-16 bg-white/10 backdrop-blur-sm rounded-2xl flex items-center justify-center mb-4 text-white">
            <Lock size={32} />
          </div>
          <h1 className="text-2xl font-bold text-white">관리자 시스템</h1>
          <p className="text-indigo-200 text-sm mt-2">강사 및 관리자 전용 로그인</p>
        </div>

        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          {error && (
            <div className="bg-red-50 text-red-600 text-sm p-3 rounded-lg flex items-center gap-2 font-medium">
              🚨 {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">이메일</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="email"
                  name="username"
                  required
                  value={formData.username}
                  onChange={handleInputChange}
                  className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all"
                  placeholder="admin@example.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">비밀번호</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="password"
                  name="password"
                  required
                  value={formData.password}
                  onChange={handleInputChange}
                  className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all"
                  placeholder="••••••••"
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-indigo-900 hover:bg-indigo-800 text-white font-bold py-3 rounded-xl transition-all shadow-lg shadow-indigo-500/30 flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="animate-spin" />
                로그인 중...
              </>
            ) : (
              <>
                로그인하기 <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginInner />
    </Suspense>
  );
}