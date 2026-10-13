// 로그인 직후 세션 쿠키 갱신
import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export async function POST() {
  const supabase = await createSupabaseServerClient();

  // 세션 쿠키 갱신 트리거
  await supabase.auth.getUser();

  return NextResponse.json({ ok: true });
}
