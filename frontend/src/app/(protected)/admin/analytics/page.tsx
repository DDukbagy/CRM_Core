// frontend/src/app/(protected)/admin/analytics/page.tsx — 준비 중
export const dynamic = "force-dynamic";

import DashboardLayout from "@/components/layout/DashboardLayout";
import ComingSoon from "@/components/common/ComingSoon";
import { adminNav } from "../nav";

export default function AdminAnalyticsPage() {
  return (
    <DashboardLayout
      navItems={adminNav}
      userLabel={{ initial: "A", name: "관리자", role: "Admin" }}
      headerFallback="관리자"
    >
      <ComingSoon title="영업/통계" />
    </DashboardLayout>
  );
}
