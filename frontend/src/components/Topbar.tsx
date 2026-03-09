// frontend/src/components/Topbar.tsx
"use client";

import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase/client";

export default function Topbar() {
  const router = useRouter();

  const onLogout = async () => {
    await supabase.auth.signOut();
    router.replace("/login");
  };

  return (
    <header className="bg-white border-b">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="font-bold text-indigo-900">CRM</div>

        <button
          onClick={onLogout}
          className="px-3 py-2 rounded-xl bg-gray-900 text-white hover:bg-gray-800 transition"
        >
          로그아웃
        </button>
      </div>
    </header>
  );
}
