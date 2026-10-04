"use client";

// 강사 웹 매출 분석: 최근 6개월 월별 매출, 결제수단·수강권별 합계, 고객·수강권 현황 (GET /instructors/me/dashboard)
// 강사 앱에서는 같은 데이터를 "운영 현황" 화면에서 확인만 한다
import React, { useEffect, useState } from "react";
import { api } from "@/lib/axios";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { instructorNav } from "../page";
import { Loader2 } from "lucide-react";

type Dashboard = {
  months: { month: string; amount: number; count: number }[];
  this_month: number;
  last_month: number;
  period_total: number;
  by_method: { method: string; amount: number }[];
  by_pass: { pass_name: string; amount: number }[];
  customers: { total: number; new_this_month: number };
  passes: { active: number; remaining_sessions: number; completed: number };
  lessons_completed_this_month: number;
};

const METHOD_LABEL: Record<string, string> = {
  CASH: "현금", TRANSFER: "계좌이체", TOSS: "토스", KAKAO: "카카오페이", NAVER: "네이버페이",
};
const won = (n: number) => `${n.toLocaleString()}원`;

export default function InsightsPage() {
  const [d, setD] = useState<Dashboard | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.get("/instructors/me/dashboard?months=6").then(r => setD(r.data)).catch(() => setError(true));
  }, []);

  const diff = d ? d.this_month - d.last_month : 0;
  const maxMonth = d ? Math.max(1, ...d.months.map(m => m.amount)) : 1;

  return (
    <DashboardLayout navItems={instructorNav} headerFallback="매출 분석">
      <div className="space-y-6 p-6">
        {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">대시보드를 불러오지 못했습니다.</p>}
        {!d && !error && <div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>}
        {d && (
          <>
            {/* 요약 */}
            <div className="grid gap-4 md:grid-cols-4">
              <Stat label="이번 달 매출" value={won(d.this_month)}
                sub={d.last_month || d.this_month ? `지난달 대비 ${diff >= 0 ? "+" : ""}${won(diff)}` : "지난달 매출 없음"}
                tone={diff >= 0 ? "text-green-600" : "text-red-500"} />
              <Stat label="최근 6개월 합계" value={won(d.period_total)} />
              <Stat label="담당 고객" value={`${d.customers.total}명`} sub={`이번 달 가입 ${d.customers.new_this_month}명`} />
              <Stat label="이번 달 완료 레슨" value={`${d.lessons_completed_this_month}회`} />
            </div>

            {/* 월별 매출 */}
            <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
              <h3 className="mb-5 text-sm font-semibold text-gray-500">월별 매출 (완료된 결제)</h3>
              <div className="flex h-48 items-end gap-3">
                {d.months.map(m => (
                  <div key={m.month} className="flex flex-1 flex-col items-center gap-2">
                    <span className="text-[11px] text-gray-500">{m.amount ? `${Math.round(m.amount / 10000)}만` : ""}</span>
                    <div className="w-full rounded-t-lg bg-green-500/80" style={{ height: `${Math.max(2, (m.amount / maxMonth) * 140)}px` }} />
                    <span className="text-xs text-gray-500">{Number(m.month.slice(5))}월</span>
                  </div>
                ))}
              </div>
            </section>

            <div className="grid gap-4 md:grid-cols-3">
              <Breakdown title="결제수단별 (6개월)" rows={d.by_method.map(x => ({ label: METHOD_LABEL[x.method] ?? x.method, amount: x.amount }))} />
              <Breakdown title="수강권별 (6개월)" rows={d.by_pass.map(x => ({ label: x.pass_name, amount: x.amount }))} />
              <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
                <h3 className="mb-4 text-sm font-semibold text-gray-500">수강권 현황</h3>
                <Row label="진행 중 수강권" value={`${d.passes.active}개`} />
                <Row label="남은 레슨 횟수" value={`${d.passes.remaining_sessions}회`} />
                <Row label="다 쓴 수강권" value={`${d.passes.completed}개`} />
              </section>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
      <p className="text-xs text-gray-400">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
      {sub && <p className={`mt-1 text-xs ${tone ?? "text-gray-400"}`}>{sub}</p>}
    </div>
  );
}

function Breakdown({ title, rows }: { title: string; rows: { label: string; amount: number }[] }) {
  const total = rows.reduce((s, r) => s + r.amount, 0) || 1;
  return (
    <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-gray-500">{title}</h3>
      {rows.length === 0 ? <p className="text-sm text-gray-400">결제 내역이 없습니다.</p> : rows.map(r => (
        <div key={r.label} className="mb-3">
          <div className="mb-1 flex justify-between text-sm"><span className="text-gray-700">{r.label}</span><span className="font-semibold">{won(r.amount)}</span></div>
          <div className="h-1.5 rounded-full bg-gray-100"><div className="h-1.5 rounded-full bg-green-500" style={{ width: `${(r.amount / total) * 100}%` }} /></div>
        </div>
      ))}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between py-1.5 text-sm"><span className="text-gray-500">{label}</span><span className="font-semibold text-gray-900">{value}</span></div>;
}
