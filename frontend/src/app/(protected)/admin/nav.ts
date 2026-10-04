// 관리자 화면 공용 사이드바 메뉴
import type { SidebarItem } from "@/components/layout/DashboardLayout";

export const adminNav: SidebarItem[] = [
  { name: "대시보드", href: "/admin", iconKey: "dashboard" },
  { name: "강사 관리", href: "/admin/instructors", iconKey: "users" },
  { name: "시스템 관리", href: "/admin/system", iconKey: "settings" },
  { name: "영업/통계", href: "/admin/analytics", iconKey: "target" },
];
