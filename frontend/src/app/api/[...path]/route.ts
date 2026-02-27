// frontend/src/app/api/[...path]/route.ts
import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

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

async function getAccessTokenFromCookies(req: NextRequest): Promise<string | null> {
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => req.cookies.getAll(),
        setAll: () => {
        },
      },
    }
  );

  const {
    data: { session },
  } = await supabase.auth.getSession();

  return session?.access_token ?? null;
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

  const accessToken = (await getAccessTokenFromCookies(req)) ?? devBearer ?? null;

  console.log("proxy auth debug:", {
    nodeEnv: process.env.NODE_ENV,
    enableDev: process.env.ENABLE_DEV_BEARER,
    hasDevToken: !!process.env.DEV_BEARER_TOKEN,
    accessTokenPrefix: accessToken?.slice?.(0, 12) ?? null,
  });

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

  console.log("upstream auth header:", headers.get("authorization")?.slice(0, 30));

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
    // fetch가 자동으로 디코드한 경우 헤더 불일치 방지
    resHeaders.delete("content-encoding");

    return new NextResponse(upstreamRes.body, {
      status: upstreamRes.status,
      headers: resHeaders,
    });
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
