import { useEffect, useState } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet, Alert } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UserRead, MembershipRead } from "@/types/api";

export default function CustomerDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [customer, setCustomer] = useState<UserRead | null>(null);
  const [memberships, setMemberships] = useState<MembershipRead[]>([]);

  useEffect(() => {
    Promise.all([
      apiFetch<UserRead>(`/users/${id}`),
      apiFetch<MembershipRead[]>(`/memberships?customer_id=${id}&active_only=false`),
    ]).then(([u, m]) => { setCustomer(u); setMemberships(m); }).catch(() => {});
  }, [id]);

  async function toggleConsent() {
    if (!customer) return;
    const next = !customer.feedback_consent;
    try {
      await apiFetch(`/instructor-posts/customers/${id}/feedback-consent?consent=${next}`, { method: "PATCH" });
      setCustomer(c => c ? { ...c, feedback_consent: next } : c);
    } catch { Alert.alert("오류", "설정 변경에 실패했습니다."); }
  }

  if (!customer) return <View style={s.center}><Text>불러오는 중...</Text></View>;

  const active = memberships.filter(m => m.is_active);
  const inactive = memberships.filter(m => !m.is_active);

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

      {/* 피드백 공개 동의 */}
      <View style={s.card}>
        <View style={s.rowBetween}>
          <Text style={s.sectionLabel}>피드백 공개 동의</Text>
          <Pressable
            onPress={toggleConsent}
            style={[s.toggle, customer.feedback_consent && s.toggleOn]}
          >
            <Text style={[s.toggleText, customer.feedback_consent && s.toggleTextOn]}>
              {customer.feedback_consent ? "동의" : "미동의"}
            </Text>
          </Pressable>
        </View>
        <Text style={s.hint}>동의 시 해당 고객의 피드백 게시물을 전체 공개할 수 있습니다.</Text>
      </View>

      {/* 활성 수강권 */}
      <Text style={s.section}>활성 수강권 ({active.length})</Text>
      {active.length === 0
        ? <View style={s.emptyBox}><Text style={s.emptyText}>활성 수강권이 없습니다.</Text></View>
        : active.map(m => <MembershipCard key={m.id} m={m} />)
      }

      {inactive.length > 0 && (
        <>
          <Text style={s.section}>만료/비활성 수강권 ({inactive.length})</Text>
          {inactive.map(m => <MembershipCard key={m.id} m={m} />)}
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

function MembershipCard({ m }: { m: MembershipRead }) {
  return (
    <View style={[s.memCard, !m.is_active && s.memCardInactive]}>
      <View style={s.memHeader}>
        <Text style={s.memType}>{m.type === "TIMES" ? "횟수제" : "기간제"}</Text>
        {!m.is_active && <Text style={s.inactiveTag}>비활성</Text>}
      </View>
      {m.type === "TIMES" && (
        <Text style={s.memInfo}>잔여 {m.remaining_count ?? 0} / {m.total_count ?? 0}회</Text>
      )}
      {m.type === "PERIOD" && m.expires_at && (
        <Text style={s.memInfo}>만료일: {m.expires_at}</Text>
      )}
      {m.notes && <Text style={s.memNotes}>{m.notes}</Text>}
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
  toggleText: { fontSize: 13, fontWeight: "600", color: "#6b7280" },
  toggleTextOn: { color: "#fff" },
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
