// API 클라이언트: 항상 /api 프록시로 요청
import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

// 서버 오류 응답 {"error": {"code", "message"}} 에서 사람이 읽을 이유를 꺼낸다 (없으면 fallback)
export function apiErrorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) {
    const message = (e.response?.data as { error?: { message?: unknown } } | undefined)?.error?.message;
    if (typeof message === "string" && message) return message;
  }
  return fallback;
}
