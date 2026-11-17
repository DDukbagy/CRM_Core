// 로그인 후 이동할 화면 고르기 (서버 액션·로그인 화면 공용)

export function sanitizeNext(raw: string | null): string | null {
  if (!raw) return null;

  // 외부 URL 방지 (open redirect 차단)
  // next는 반드시 "/..." 형태만 허용
  if (!raw.startsWith("/")) return null;
  if (raw.startsWith("//")) return null;
  if (raw.includes("://")) return null;

  return raw;
}

export function pickRedirectPath(role: string | undefined | null, nextPath: string | null): string | null {
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
