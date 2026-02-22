"use client";

import { useSearchParams } from "next/navigation";

export default function ForbiddenClient() {
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason");

  return (
    <main>
      <h1>Forbidden</h1>
      {reason ? <p>{reason}</p> : null}
    </main>
  );
}