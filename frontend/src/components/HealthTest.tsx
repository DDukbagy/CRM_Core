"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/axios";

export default function HealthTest() {
  const [message, setMessage] = useState("서버 응답 대기중...");
  const [status, setStatus] = useState("loading"); // loading | success | error

  useEffect(() => {
    // 백엔드 루트('/') 경로로 찔러보기
    api.get("/")
      .then((res) => {
        console.log("백엔드 응답:", res.data);
        setMessage(`✅ 연결 성공! 백엔드 메시지: "${JSON.stringify(res.data)}"`);
        setStatus("success");
      })
      .catch((err) => {
        console.error("연결 실패:", err);
        setMessage("❌ 연결 실패. 백엔드 주소나 CORS 설정을 확인하세요.");
        setStatus("error");
      });
  }, []);

  return (
    <div className={`p-4 rounded-lg border mt-8 ${
      status === 'success' ? 'bg-green-100 border-green-400 text-green-700' :
      status === 'error' ? 'bg-red-100 border-red-400 text-red-700' :
      'bg-gray-100 border-gray-400 text-gray-700'
    }`}>
      <h2 className="font-bold text-lg mb-2">📡 백엔드 통신 테스트</h2>
      <p>{message}</p>
    </div>
  );
}