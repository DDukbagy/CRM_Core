// 로그인 화면: 서버 액션으로 로그인 후 역할별 화면으로 이동 (세션 쿠키는 서버가 HttpOnly 로 저장)
"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useFormStatus } from "react-dom";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/axios";
import { Lock, User, Loader2, ArrowRight } from "lucide-react";
import { loginAction } from "./actions";
import { pickRedirectPath, sanitizeNext } from "./redirect";

const ERROR_MESSAGES: Record<string, string> = {
  ROLE_UNAVAILABLE: "권한 정보를 불러오지 못했습니다. 다시 로그인 해주세요.",
};

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

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full bg-indigo-900 hover:bg-indigo-800 text-white font-bold py-3 rounded-xl transition-all shadow-lg shadow-indigo-500/30 flex items-center justify-center gap-2"
    >
      {pending ? (
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
  );
}

function LoginInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const nextParam = sanitizeNext(searchParams.get("next"));
  const errorParam = searchParams.get("error");

  const [errorDismissed, setErrorDismissed] = useState(false);
  const error = errorParam && !errorDismissed ? ERROR_MESSAGES[errorParam] ?? errorParam : "";

  // 이미 로그인돼 있으면 바로 역할별 화면으로 (세션 쿠키는 /api 프록시가 서버에서 읽는다)
  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        const res = await api.get("/users/me");
        const target = pickRedirectPath(res.data?.role as string | undefined, nextParam);
        if (mounted && target) router.replace(target);
      } catch {
        // 로그인 전이면 401 — 로그인 화면 그대로
      }
    })();

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

        <form action={loginAction} onChange={() => setErrorDismissed(true)} className="p-8 space-y-6">
          {error && (
            <div className="bg-red-50 text-red-600 text-sm p-3 rounded-lg flex items-center gap-2 font-medium">
              🚨 {error}
            </div>
          )}

          {nextParam && <input type="hidden" name="next" value={nextParam} />}

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">이메일</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="email"
                  name="username"
                  required
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
                  className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all"
                  placeholder="••••••••"
                />
              </div>
            </div>
          </div>

          <SubmitButton />
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
