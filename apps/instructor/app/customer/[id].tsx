import { useEffect, useState } from "react";
import { View, Text, ScrollView, StyleSheet } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UserRead, CustomerPassRead } from "@/types/api";

export default function CustomerDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [customer, setCustomer] = useState<UserRead | null>(null);
  // 이 고객에게 발급한 수강권 (멤버십은 수강권으로 통합, 2026-10-04)
  const [passes, setPasses] = useState<CustomerPassRead[]>([]);

  useEffect(() => {
    Promise.all([
      apiFetch<UserRead>(`/users/${id}`),
      apiFetch<CustomerPassRead[]>(`/passes/customer-passes?customer_id=${id}`),
    ]).then(([u, p]) => { setCustomer(u); setPasses(p); }).catch(() => {});
  }, [id]);

  if (!customer) return <View style={s.center}><Text>불러오는 중...</Text></View>;

  const active = passes.filter(p => p.status === "ACTIVE");
  const inactive = passes.filter(p => p.status !== "ACTIVE");

  return (
    <ScrollView style={s.container}>
      {/* 기본 정보 */}
      <View style={s.card}>
        <Text style={s.name}>{customer.display_name}</Text>
        {customer.phone && <Row label="전화번호" value={customer.phone} />}
        {customer.email && <Row label="이메일" value={customer.email} />}
        {customer.gender && <Row label="성별" value={customer.gender} />}
        {customer.birth_date && <Row label="생년월일" value={customer.birth_date} />}
        {customer.lesson_purpose && <Row label="레슨 목표" value={customer.lesson_purpose} />}
      </View>

      {/* 활성 수강권 */}
      <Text style={s.section}>활성 수강권 ({active.length})</Text>
      {active.length === 0
        ? <View style={s.emptyBox}><Text style={s.emptyText}>활성 수강권이 없습니다.</Text></View>
        : active.map(p => <PassCard key={p.id} p={p} />)
      }

      {inactive.length > 0 && (
        <>
          <Text style={s.section}>만료/비활성 수강권 ({inactive.length})</Text>
          {inactive.map(p => <PassCard key={p.id} p={p} />)}
        </>
      )}
    </ScrollView>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={s.row}>
      <Text style={s.rowLabel}>{label}</Text>
      <Text style={s.rowValue}>{value}</Text>
    </View>
  );
}

const PASS_STATUS_LABEL: Record<string, string> = { COMPLETED: "완료", EXPIRED: "만료", CANCELLED: "취소" };

function PassCard({ p }: { p: CustomerPassRead }) {
  const active = p.status === "ACTIVE";
  return (
    <View style={[s.memCard, !active && s.memCardInactive]}>
      <View style={s.memHeader}>
        <Text style={s.memType}>{p.pass_name}</Text>
        {!active && <Text style={s.inactiveTag}>{PASS_STATUS_LABEL[p.status] ?? "비활성"}</Text>}
      </View>
      <Text style={s.memInfo}>잔여 {p.sessions_remaining} / {p.sessions_total}회</Text>
      {p.note && <Text style={s.memNotes}>{p.note}</Text>}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: "#fff", margin: 16, marginBottom: 8, borderRadius: 12, padding: 16, elevation: 1 },
  name: { fontSize: 20, fontWeight: "700", marginBottom: 12 },
  row: { flexDirection: "row", marginBottom: 6 },
  rowLabel: { width: 90, fontSize: 13, color: "#6b7280" },
  rowValue: { flex: 1, fontSize: 13, color: "#111" },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  sectionLabel: { fontSize: 15, fontWeight: "600" },
  toggle: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, backgroundColor: "#e5e7eb" },
  toggleOn: { backgroundColor: "#16a34a" },
  badge: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 20 },
  badgeOn: { backgroundColor: "#dcfce7" },
  badgeOff: { backgroundColor: "#f3f4f6" },
  badgeText: { fontSize: 13, fontWeight: "600" },
  badgeTextOn: { color: "#16a34a" },
  badgeTextOff: { color: "#9ca3af" },
  hint: { fontSize: 12, color: "#9ca3af", lineHeight: 18 },
  section: { fontSize: 15, fontWeight: "600", paddingHorizontal: 16, paddingTop: 12, paddingBottom: 6 },
  emptyBox: { margin: 16, padding: 20, backgroundColor: "#fff", borderRadius: 12, alignItems: "center" },
  emptyText: { color: "#9ca3af" },
  memCard: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8, borderRadius: 10, padding: 14, elevation: 1 },
  memCardInactive: { opacity: 0.55 },
  memHeader: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 },
  memType: { fontSize: 14, fontWeight: "700", color: "#16a34a" },
  inactiveTag: { fontSize: 11, backgroundColor: "#fee2e2", color: "#b91c1c", paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  memInfo: { fontSize: 15, fontWeight: "600", color: "#111", marginBottom: 2 },
  memNotes: { fontSize: 12, color: "#9ca3af", marginTop: 4 },
});
