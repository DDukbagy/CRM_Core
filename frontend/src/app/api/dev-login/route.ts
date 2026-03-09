import { NextResponse, type NextRequest } from "next/server";

function getUpstreamBaseUrl() {
  const base = process.env.API_BASE_URL;
  if (!base) throw new Error("API_BASE_URL is missing");
  return base.replace(/\/$/, "");
}

export async function POST(req: NextRequest) {
  const { username, password } = await req.json();

  const upstream = new URL(getUpstreamBaseUrl() + "/users/login/access-token");

  // FastAPI OAuth2PasswordRequestForm: x-www-form-urlencoded
  const body = new URLSearchParams({ username, password });

  const upstreamRes = await fetch(upstream.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  const data = await upstreamRes.json().catch(() => null);

  if (!upstreamRes.ok) {
    return NextResponse.json(
      { error: "LOGIN_FAILED", upstream_status: upstreamRes.status, data },
      { status: 401 }
    );
  }

  const token = data?.access_token;
  if (!token) {
    return NextResponse.json({ error: "NO_TOKEN_IN_RESPONSE", data }, { status: 500 });
  }

  const res = NextResponse.json({ ok: true });

  // 개발용: 백엔드 JWT를 httpOnly 쿠키로 저장
  res.cookies.set("backend_access_token", token, {
    httpOnly: true,
    sameSite: "lax",
    secure: false, // dev
    path: "/",
    maxAge: 60 * 60 * 24, // 1 day (실제 만료는 JWT exp가 우선)
  });

  return res;
}