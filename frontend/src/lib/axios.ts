// src/lib/axios.ts
import axios from "axios";
import { supabase } from "@/lib/providers";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL, // .env에서 가져온 주소
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true, // 나중에 쿠키(로그인 정보) 주고받을 때 필수
});

// 모든 API 요청에 Supabase access_token 자동 주입
api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});
