"use client";

import React, { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { useAuth, supabase } from "@/lib/providers";
import { api } from "@/lib/axios";

/**
 * 보안 목적:
 * - /login 은 인증 없이 접근 가능
 * - 그 외 모든 경로는 로그인(세션) + 역할(role) 검증 후에만 접근
 * - CUSTOMER 등 웹 접근 불가 역할은 즉시 로그아웃 처리
 */
export default function AuthShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, loading } = useAuth();

  const isLoginPage = useMemo(() => pathname === "/login", [pathname]);
  const [roleChecked, setRoleChecked] = useState(false);

  useEffect(() => {
    // 로그인 페이지는 인증 가드 적용하지 않음
    if (isLoginPage) return;

    // 세션 로딩 중이면 대기
    if (loading) return;

    // 세션이 없으면 즉시 로그인으로 이동
    if (!session) {
      router.replace("/login");
      return;
    }

    // 세션이 있으면 백엔드(/users/me) 기준으로 role 확인
    (async () => {
      try {
        const res = await api.get("/users/me");
        const role = res.data?.role;

        if (role === "ADMIN" || role === "INSTRUCTOR") {
          setRoleChecked(true);
          return;
        }

        // CUSTOMER 등 접근 불가 역할
        await supabase.auth.signOut();
        router.replace("/login");
      } catch {
        // /users/me 실패 시도도 보안상 로그인으로 돌림
        await supabase.auth.signOut();
        router.replace("/login");
      }
    })();
  }, [isLoginPage, loading, session, router]);

  // /login은 그냥 렌더링
  if (isLoginPage) {
    return <>{children}</>;
  }

  // 로그인 페이지가 아니면 "세션 + role" 확인 전까지 화면을 안 열어줌(보안)
  if (loading || !session || !roleChecked) {
    return null;
  }

  return <DashboardLayout>{children}</DashboardLayout>;
}
