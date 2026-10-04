// 운영 현황 (확인 전용): 매출 대시보드 + 프로모션. 수정은 강사 웹(매출 분석·프로모션)에서 한다
import { useCallback, useState } from "react";
import { View, Text, ScrollView, RefreshControl, ActivityIndicator, StyleSheet } from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { InstructorDashboard, PromotionRead } from "@/types/api";

const METHOD_LABEL: Record<string, string> = { CASH: "현금", TRANSFER: "계좌이체", TOSS: "토스", KAKAO: "카카오페이", NAVER: "네이버페이" };
const STATUS: Record<PromotionRead["status"], { label: string; color: string; bg: string }> = {
  ONGOING: { label: "진행 중", color: "#16a34a", bg: "#f0fdf4" },
  SCHEDULED: { label: "예정", color: "#2563eb", bg: "#eff6ff" },
  PAUSED: { label: "중지", color: "#6b7280", bg: "#f3f4f6" },
  ENDED: { label: "종료", color: "#9ca3af", bg: "#f3f4f6" },
};
const won = (n: number) => `${n.toLocaleString()}원`;
const discountLabel = (p: PromotionRead) =>
  p.discount_type === "PERCENT" ? `${p.discount_value}% 할인` : p.discount_type === "AMOUNT" ? `${p.discount_value.toLocaleString()}원 할인` : "이벤트";

export default function BusinessScreen() {
  const [d, setD] = useState<InstructorDashboard | null>(null);
  const [promos, setPromos] = useState<PromotionRead[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [dash, p] = await Promise.all([
        apiFetch<InstructorDashboard>("/instructors/me/dashboard?months=6"),
        apiFetch<PromotionRead[]>("/promotions/me"),
      ]);
      setD(dash);
      setPromos(p);
    } catch (e) {
      console.error("운영 현황 로딩 실패:", e);
    } finally {
      setRefreshing(false);
    }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (!d) return <View style={s.center}><ActivityIndicator size="large" /></View>;
  const diff = d.this_month - d.last_month;
  const maxMonth = Math.max(1, ...d.months.map(m => m.amount));

  return (
    <ScrollView style={s.container} contentContainerStyle={{ padding: 16, paddingBottom: 40, gap: 12 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
      <Text style={s.notice}>확인 전용 화면입니다. 프로모션 수정은 강사 웹에서 할 수 있어요.</Text>

      <View style={s.hero}>
        <Text style={s.heroLabel}>이번 달 매출</Text>
        <Text style={s.heroAmount}>{won(d.this_month)}</Text>
        <Text style={s.heroSub}>지난달 대비 {diff >= 0 ? "+" : ""}{won(diff)} · 6개월 합계 {won(d.period_total)}</Text>
      </View>

      <View style={s.card}>
        <Text style={s.cardTitle}>월별 매출</Text>
        <View style={s.bars}>
          {d.months.map(m => (
            <View key={m.month} style={s.barCol}>
              <Text style={s.barVal}>{m.amount ? `${Math.round(m.amount / 10000)}만` : ""}</Text>
              <View style={[s.bar, { height: Math.max(2, (m.amount / maxMonth) * 90) }]} />
              <Text style={s.barLabel}>{Number(m.month.slice(5))}월</Text>
            </View>
          ))}
        </View>
      </View>

      <View style={s.grid}>
        <Mini label="담당 고객" value={`${d.customers.total}명`} sub={`이번 달 +${d.customers.new_this_month}`} />
        <Mini label="이번 달 완료 레슨" value={`${d.lessons_completed_this_month}회`} />
        <Mini label="진행 중 수강권" value={`${d.passes.active}개`} sub={`남은 ${d.passes.remaining_sessions}회`} />
      </View>

      <View style={s.card}>
        <Text style={s.cardTitle}>결제수단별 (6개월)</Text>
        {d.by_method.length === 0 ? <Text style={s.empty}>결제 내역이 없습니다.</Text> : d.by_method.map(x => (
          <Row key={x.method} label={METHOD_LABEL[x.method] ?? x.method} value={won(x.amount)} />
        ))}
      </View>
      <View style={s.card}>
        <Text style={s.cardTitle}>수강권별 (6개월)</Text>
        {d.by_pass.length === 0 ? <Text style={s.empty}>결제 내역이 없습니다.</Text> : d.by_pass.map(x => (
          <Row key={x.pass_name} label={x.pass_name} value={won(x.amount)} />
        ))}
      </View>

      <View style={s.card}>
        <Text style={s.cardTitle}>프로모션</Text>
        {promos.length === 0 ? <Text style={s.empty}>등록된 프로모션이 없습니다. 강사 웹에서 만들 수 있어요.</Text> : promos.map(p => (
          <View key={p.id} style={s.promo}>
            <View style={s.promoTop}>
              <Text style={[s.badge, { color: STATUS[p.status].color, backgroundColor: STATUS[p.status].bg }]}>{STATUS[p.status].label}</Text>
              <Text style={s.discount}>{discountLabel(p)}</Text>
            </View>
            <Text style={s.promoTitle}>{p.title}</Text>
            <Text style={s.promoSub}>{p.start_date} ~ {p.end_date}{p.pass_type_name ? ` · ${p.pass_type_name}` : ""}</Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

function Mini({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <View style={s.mini}>
      <Text style={s.miniLabel}>{label}</Text>
      <Text style={s.miniValue}>{value}</Text>
      {sub ? <Text style={s.miniSub}>{sub}</Text> : null}
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return <View style={s.row}><Text style={s.rowLabel}>{label}</Text><Text style={s.rowValue}>{value}</Text></View>;
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  notice: { fontSize: 12, color: "#6b7280", backgroundColor: "#f3f4f6", padding: 10, borderRadius: 8 },
  hero: { backgroundColor: "#16a34a", borderRadius: 16, padding: 20 },
  heroLabel: { color: "#dcfce7", fontSize: 13 },
  heroAmount: { color: "#fff", fontSize: 30, fontWeight: "800", marginTop: 4 },
  heroSub: { color: "#dcfce7", fontSize: 12, marginTop: 6 },
  card: { backgroundColor: "#fff", borderRadius: 14, padding: 16, borderWidth: 1, borderColor: "#f3f4f6" },
  cardTitle: { fontSize: 13, fontWeight: "700", color: "#6b7280", marginBottom: 10 },
  bars: { flexDirection: "row", alignItems: "flex-end", height: 130, gap: 8 },
  barCol: { flex: 1, alignItems: "center", justifyContent: "flex-end", gap: 4 },
  bar: { width: "100%", backgroundColor: "#22c55e", borderTopLeftRadius: 6, borderTopRightRadius: 6 },
  barVal: { fontSize: 10, color: "#6b7280" },
  barLabel: { fontSize: 11, color: "#6b7280" },
  grid: { flexDirection: "row", gap: 8 },
  mini: { flex: 1, backgroundColor: "#fff", borderRadius: 12, padding: 12, borderWidth: 1, borderColor: "#f3f4f6" },
  miniLabel: { fontSize: 11, color: "#9ca3af" },
  miniValue: { fontSize: 18, fontWeight: "700", color: "#111", marginTop: 2 },
  miniSub: { fontSize: 11, color: "#16a34a", marginTop: 2 },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 },
  rowLabel: { fontSize: 14, color: "#374151" },
  rowValue: { fontSize: 14, fontWeight: "700", color: "#111" },
  empty: { fontSize: 13, color: "#9ca3af" },
  promo: { paddingVertical: 10, borderTopWidth: 1, borderTopColor: "#f3f4f6" },
  promoTop: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 4 },
  badge: { fontSize: 11, fontWeight: "700", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, overflow: "hidden" },
  discount: { fontSize: 12, fontWeight: "700", color: "#f97316" },
  promoTitle: { fontSize: 15, fontWeight: "700", color: "#111" },
  promoSub: { fontSize: 12, color: "#9ca3af", marginTop: 2 },
});
