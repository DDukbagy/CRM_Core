// Supabase 세션 쿠키 옵션 (서버에서만 쿠키를 쓴다)
import type { CookieOptionsWithName } from "@supabase/ssr";

/**
 * 세션 쿠키(access token·refresh token)는 브라우저 JS 가 읽지 못하게 HttpOnly 로 둔다.
 * - 로그인·로그아웃·토큰 갱신은 모두 Next 서버(서버 액션, proxy.ts, /api 프록시)에서 한다
 * - secure 는 HTTPS 인 운영에서만 (로컬 http://localhost 에서는 붙이면 쿠키가 저장되지 않는다)
 */
export const SESSION_COOKIE_OPTIONS: CookieOptionsWithName = {
  path: "/",
  httpOnly: true,
  sameSite: "lax",
  secure: process.env.NODE_ENV === "production",
};
