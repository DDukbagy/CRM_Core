"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { supabaseBrowser } from "@/lib/supabase/client";
import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Users,
  Target,
  Settings,
  Calendar,
  Menu,
  X,
  Bell,
  UserCircle,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  dashboard: LayoutDashboard,
  users: Users,
  target: Target,
  settings: Settings,
  calendar: Calendar,
};

export type SidebarItem = {
  name: string;
  href: string;
  iconKey: keyof typeof ICONS;
};

type DashboardLayoutProps = {
  children: React.ReactNode;
  navItems?: SidebarItem[];
  headerFallback?: string;
  userLabel?: { initial?: string; name?: string; role?: string };
};

const defaultSidebarItems: SidebarItem[] = [
  { name: "대시보드", href: "/", iconKey: "dashboard" },
  { name: "스케줄", href: "/schedule", iconKey: "calendar" },
  { name: "고객 관리", href: "/customers", iconKey: "users" },
  { name: "영업 기회", href: "/leads", iconKey: "target" },
  { name: "설정", href: "/settings", iconKey: "settings" },
];

export default function DashboardLayout({
  children,
  navItems,
  headerFallback = "관리 시스템",
  userLabel,
}: DashboardLayoutProps) {
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  const items = useMemo(() => navItems ?? defaultSidebarItems, [navItems]);

  // active 판정: exact 또는 하위 경로 포함
  const isActiveHref = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  const currentTitle =
    items.find((item) => isActiveHref(item.href))?.name ?? headerFallback;

  const initial = userLabel?.initial ?? "K";
  const userName = userLabel?.name ?? "강사님";
  const userRole = userLabel?.role ?? "Instructor";

  // 로그아웃 (최소/확실)
  const onLogout = async () => {
    try {
      const supabase = supabaseBrowser();
      await supabase.auth.signOut({ scope: "local" });
    } finally {
      router.replace("/login");
      router.refresh();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* 사이드바 (Sidebar) */}
      <aside
        className={`bg-white border-r border-gray-200 transition-all duration-300 ${
          isSidebarOpen ? "w-64" : "w-20"
        } fixed inset-y-0 z-50 flex flex-col`}
      >
        <div className="h-16 flex items-center justify-between px-6 border-b border-gray-100">
          <span
            className={`font-bold text-xl text-blue-600 ${
              !isSidebarOpen && "hidden"
            }`}
          >
            MY CRM
          </span>
          <button
            onClick={() => setSidebarOpen(!isSidebarOpen)}
            className="p-1 hover:bg-gray-100 rounded text-gray-500"
            aria-label="Toggle sidebar"
          >
            {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        <nav className="flex-1 py-6 space-y-1 px-3">
          {items.map((item) => {
            const active = isActiveHref(item.href);
            const Icon = ICONS[item.iconKey];

            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center space-x-3 px-3 py-3 rounded-lg transition-all group ${
                  active
                    ? "bg-blue-600 text-white shadow-md shadow-blue-200"
                    : "text-gray-600 hover:bg-blue-50 hover:text-blue-600"
                }`}
              >
                <Icon size={22} />
                <span className={`font-medium ${!isSidebarOpen && "hidden"}`}>
                  {item.name}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* 사용자 정보 섹션 */}
        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center space-x-3 px-2 py-2">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-xs">
              {initial}
            </div>
            <div className={`${!isSidebarOpen && "hidden"}`}>
              <p className="text-sm font-semibold text-gray-700">{userName}</p>
              <p className="text-xs text-gray-400">{userRole}</p>
            </div>
          </div>
        </div>
      </aside>

      {/* 메인 콘텐츠 영역 */}
      <main
        className={`flex-1 transition-all duration-300 ${
          isSidebarOpen ? "ml-64" : "ml-20"
        }`}
      >
        {/* 헤더 */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 sticky top-0 z-40">
          <h1 className="text-lg font-semibold text-gray-800">{currentTitle}</h1>

          <div className="flex items-center space-x-4">
            <button className="p-2 text-gray-400 hover:text-blue-600 relative transition-colors">
              <Bell size={20} />
              <span className="absolute top-2 right-2.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
            </button>

            <div className="h-8 w-8 bg-gray-100 rounded-full flex items-center justify-center text-gray-500 border border-gray-200">
              <UserCircle size={20} />
            </div>

            {/* 로그아웃 */}
            <button
              onClick={onLogout}
              className="px-3 py-2 rounded-xl bg-gray-900 text-white hover:bg-gray-800 transition"
            >
              로그아웃
            </button>
          </div>
        </header>

        {/* 페이지 내용 */}
        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
