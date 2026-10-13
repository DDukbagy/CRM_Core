// 로그인이 필요한 화면 공통 레이아웃
import React from "react";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
