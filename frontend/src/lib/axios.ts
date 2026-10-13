// API 클라이언트: 항상 /api 프록시로 요청
import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
});
