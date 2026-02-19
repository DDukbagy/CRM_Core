// frontend/src/proxy.ts
import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

type Role = "ADMIN" | "INSTRUCTOR" | "CUSTOMER" | string;

function isProtectedPath(pathname: string) {
  return (
    pathname === "/admin" ||
    pathname.startsWith("/admin/") ||
    pathname === "/instructor" ||
    pathname.startsWith("/instructor/") ||
    pathname === "/schedule" ||
    pathname.startsWith("/schedule/") ||
    pathname === "/customers" ||
    pathname.startsWith("/customers/") ||
    pathname === "/leads" ||
    pathname.startsWith("/leads/") ||
    pathname === "/settings" ||
    pathname.startsWith("/settings/")
  );
}

function needsAdmin(pathname: string) {
  return pathname === "/admin" || pathname.startsWith("/admin/");
}

function needsInstructor(pathname: string) {
  return pathname === "/instructor" || pathname.startsWith("/instructor/");
}

async function getRoleFromUsersTable(
  supabase: ReturnType<typeof createServerClient>,
  userId: string
): Promise<Role | null> {
  const { data, error } = await supabase
    .from("users")
    .select("role")
    .eq("id", userId)
    .single();

  if (error || !data?.role) return null;
  return data.role as Role;
}

export async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // 보호 경로가 아니면 통과
  if (!isProtectedPath(pathname)) {
    return NextResponse.next();
  }

  const res = NextResponse.next();

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return req.cookies.getAll();
        },
        setAll(cookies) {
          cookies.forEach(({ name, value, options }) => {
            res.cookies.set(name, value, options);
          });
        },
      },
    }
  );

  // 로그인 여부 체크
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    const redirectUrl = req.nextUrl.clone();
    redirectUrl.pathname = "/login";
    redirectUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(redirectUrl);
  }

  // /admin, /instructor는 role 기반으로 강제
  if (needsAdmin(pathname) || needsInstructor(pathname)) {
    const role = await getRoleFromUsersTable(supabase, user.id);

    // role을 못 읽으면(테이블/RLS/데이터 불일치) 차단
    if (!role) {
      const redirectUrl = req.nextUrl.clone();
      redirectUrl.pathname = "/login";
      redirectUrl.searchParams.set("next", pathname);
      redirectUrl.searchParams.set("error", "ROLE_UNAVAILABLE");
      return NextResponse.redirect(redirectUrl);
    }

    if (needsAdmin(pathname) && role !== "ADMIN") {
      const forbiddenUrl = req.nextUrl.clone();
      forbiddenUrl.pathname = "/forbidden";
      forbiddenUrl.searchParams.set("need", "ADMIN");
      return NextResponse.redirect(forbiddenUrl);
    }

    if (needsInstructor(pathname) && role !== "INSTRUCTOR") {
      const forbiddenUrl = req.nextUrl.clone();
      forbiddenUrl.pathname = "/forbidden";
      forbiddenUrl.searchParams.set("need", "INSTRUCTOR");
      return NextResponse.redirect(forbiddenUrl);
    }
  }

  return res;
}

export const config = {
  matcher: [
    "/admin/:path*",
    "/instructor/:path*",
    "/schedule/:path*",
    "/customers/:path*",
    "/leads/:path*",
    "/settings/:path*",
  ],
};
