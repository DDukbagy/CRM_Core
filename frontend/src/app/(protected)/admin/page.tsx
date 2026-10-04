// frontend/src/app/(protected)/admin/page.tsx
export const dynamic = "force-dynamic";

import DashboardLayout from "@/components/layout/DashboardLayout";
import { adminNav } from "./nav";

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
