// 로그인·로그아웃 서버 액션: 세션 쿠키는 서버가 HttpOnly 로 쓰고 지운다
"use server";

import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { pickRedirectPath, sanitizeNext } from "./redirect";

const ROLE_UNAVAILABLE = "권한 정보를 불러오지 못했습니다. 다시 로그인 해주세요.";
const CUSTOMER_NOT_ALLOWED = "일반 회원은 관리자 웹페이지에 접속할 수 없습니다.";

function loginUrl(error: string, next: string | null) {
  const params = new URLSearchParams({ error });
  if (next) params.set("next", next);
  return `/login?${params.toString()}`;
}

/**
 * 로그인한 사용자의 역할을 백엔드에서 읽는다 (서버에서 서버로 호출, 브라우저에 백엔드 주소를 노출하지 않음).
 * 최초 로그인이면 백엔드가 이때 사용자를 만든다 (JIT).
 */
async function fetchMyRole(accessToken: string): Promise<string | null> {
  const base = process.env.API_BASE_URL;
  if (!base) return null;

  try {
    const res = await fetch(`${base.replace(/\/$/, "")}/users/me`, {
      headers: { authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { role?: string };
    return data.role ?? null;
  } catch {
    return null;
  }
}

export async function loginAction(formData: FormData) {
  const email = String(formData.get("username") || "");
  const password = String(formData.get("password") || "");
  const next = sanitizeNext(String(formData.get("next") || "") || null);

  const supabase = await createSupabaseServerClient();
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });

  if (error || !data.session) {
    redirect(loginUrl(error?.message || "로그인 실패", next));
  }

  const role = await fetchMyRole(data.session.access_token);
  if (!role) {
    await supabase.auth.signOut({ scope: "local" });
    redirect(loginUrl(ROLE_UNAVAILABLE, next));
  }

  const target = pickRedirectPath(role, next);
  if (!target) {
    await supabase.auth.signOut({ scope: "local" });
    redirect(loginUrl(CUSTOMER_NOT_ALLOWED, next));
  }

  redirect(target);
}

export async function logoutAction() {
  const supabase = await createSupabaseServerClient();
  await supabase.auth.signOut({ scope: "local" });
  redirect("/login");
}
