// 백엔드 프록시: 브라우저 요청에 Supabase 토큰을 붙여 FastAPI 로 전달
import { NextResponse, type NextRequest } from "next/server";
import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { SESSION_COOKIE_OPTIONS } from "@/lib/supabase/cookies";

type RouteParams = { path?: string[] };
type RouteContext = { params?: RouteParams | Promise<RouteParams> };

function getUpstreamBaseUrl() {
  const base = process.env.API_BASE_URL;
  if (!base) throw new Error("API_BASE_URL is missing");
  return base.replace(/\/$/, "");
}

async function getPathParts(ctx: RouteContext): Promise<string[]> {
  const resolved = ctx.params ? await ctx.params : undefined;
  const parts = resolved?.path;
  return Array.isArray(parts) ? parts : [];
}

type CookieToSet = { name: string; value: string; options: CookieOptions };

/**
 * 쿠키에서 access token 을 꺼낸다. 만료됐으면 Supabase 가 refresh token 으로 갱신하고,
 * 갱신된 쿠키는 refreshed 에 모아 응답에 다시 저장한다 (브라우저 JS 는 HttpOnly 쿠키를 못 쓰므로 서버가 저장).
 */
async function getAccessTokenFromCookies(req: NextRequest, refreshed: CookieToSet[]): Promise<string | null> {
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookieOptions: SESSION_COOKIE_OPTIONS,
      cookies: {
        getAll: () => req.cookies.getAll(),
        setAll: (cookies) => {
          refreshed.push(...cookies);
        },
      },
    }
  );

  const {
    data: { session },
  } = await supabase.auth.getSession();

  return session?.access_token ?? null;
}

function withRefreshedCookies(res: NextResponse, refreshed: CookieToSet[]) {
  refreshed.forEach(({ name, value, options }) => res.cookies.set(name, value, options));
  return res;
}

async function proxyToUpstream(req: NextRequest, pathParts: string[]) {
  let base: string;
  try {
    base = getUpstreamBaseUrl();
  } catch (e) {
    return NextResponse.json(
      { error: "API_BASE_URL_MISSING", message: (e as Error).message },
      { status: 500 }
    );
  }

  const upstreamPath = `/${pathParts.join("/")}`;
  const upstreamUrl = new URL(base + upstreamPath);

  // 쿼리스트링 그대로 전달
  upstreamUrl.search = req.nextUrl.search;

  if (process.env.NODE_ENV === "production" && process.env.DEV_BEARER_TOKEN) {
    throw new Error("DEV_BEARER_TOKEN is set in production. Remove it.");
  }

  const devBearer =
    process.env.NODE_ENV !== "production" && process.env.ENABLE_DEV_BEARER === "1"
      ? process.env.DEV_BEARER_TOKEN
      : null;

  const refreshed: CookieToSet[] = [];
  const accessToken = (await getAccessTokenFromCookies(req, refreshed)) ?? devBearer ?? null;

  // 헤더 복사
  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("cookie"); // 업스트림에는 Authorization만 전달(쿠키 노출 방지)
  headers.delete("connection");

  if (accessToken) {
    const v = accessToken.trim();
    headers.set("authorization", v.toLowerCase().startsWith("bearer ") ? v : `Bearer ${v}`);
  } else {
    headers.delete("authorization");
  }

  // Body 전달(POST/PUT/PATCH/DELETE 등)
  const method = req.method.toUpperCase();
  const hasBody = !["GET", "HEAD"].includes(method);
  const body = hasBody ? await req.arrayBuffer() : undefined;

  try {
    const upstreamRes = await fetch(upstreamUrl.toString(), {
      method,
      headers,
      body,
      redirect: "manual",
    });

    // 응답 그대로
    const resHeaders = new Headers(upstreamRes.headers);
    // fetch 가 압축(gzip·br)을 풀어서 받으므로 압축 관련 헤더를 지운다.
    // content-length 는 압축된 크기라 남겨 두면 브라우저가 본문을 그 길이에서 잘라 JSON 이 깨진다 (Render 등 압축하는 환경)
    resHeaders.delete("content-encoding");
    resHeaders.delete("content-length");
    resHeaders.delete("transfer-encoding");

    return withRefreshedCookies(
      new NextResponse(upstreamRes.body, {
        status: upstreamRes.status,
        headers: resHeaders,
      }),
      refreshed
    );
  } catch (e) {
    return NextResponse.json(
      { error: "UPSTREAM_FETCH_FAILED", message: (e as Error).message },
      { status: 502 }
    );
  }
}

export async function GET(req: NextRequest, ctx: RouteContext) {
  return proxyToUpstream(req, await getPathParts(ctx));
}
export async function POST(req: NextRequest, ctx: RouteContext) {
  return proxyToUpstream(req, await getPathParts(ctx));
}
export async function PUT(req: NextRequest, ctx: RouteContext) {
  return proxyToUpstream(req, await getPathParts(ctx));
}
export async function PATCH(req: NextRequest, ctx: RouteContext) {
  return proxyToUpstream(req, await getPathParts(ctx));
}
export async function DELETE(req: NextRequest, ctx: RouteContext) {
  return proxyToUpstream(req, await getPathParts(ctx));
}
