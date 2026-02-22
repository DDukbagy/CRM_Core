// frontend/src/app/page.tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * 보안 목적:
 * 루트(/)는 어떤 UI도 노출하지 않고 즉시 /login으로 보냅니다.
 */
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/login");
  }, [router]);

  return null;
}
