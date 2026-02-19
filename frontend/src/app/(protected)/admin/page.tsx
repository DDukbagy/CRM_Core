// frontend/src/app/(protected)/admin/page.tsx
import DashboardLayout, { type SidebarItem } from "@/components/layout/DashboardLayout";

const adminNav: SidebarItem[] = [
  { name: "대시보드", href: "/admin", iconKey: "dashboard" },
  { name: "강사 관리", href: "/admin/instructors", iconKey: "users" },
  { name: "시스템 관리", href: "/admin/system", iconKey: "settings" },
  { name: "영업/통계", href: "/admin/analytics", iconKey: "target" },
];

export default function AdminPage() {
  return (
    <DashboardLayout
      navItems={adminNav}
      userLabel={{ initial: "A", name: "관리자", role: "Admin" }}
      headerFallback="관리자"
    >
      <div className="p-6">관리자 대시보드</div>
    </DashboardLayout>
  );
}
