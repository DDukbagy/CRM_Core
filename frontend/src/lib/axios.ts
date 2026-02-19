// frontend/src/lib/axios.ts
import axios from "axios";

export const api = axios.create({
  baseURL: "/api", // ✅ 항상 같은 오리진
  withCredentials: true,
});
