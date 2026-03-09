// app/membership.tsx — 수강권 현황 화면
import { useCallback, useRef, useState } from "react";
import {
  View, Text, ScrollView, ActivityIndicator,
  Pressable, StyleSheet,
} from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { MembershipRead } from "@/types/api";

function formatDate(d: string | null) {
  if (!d) return "-";
  return d.slice(0, 10);
}

function MembershipCard({ m }: { m: MembershipRead }) {
  const isTimes  = m.type === "TIMES";
  const isActive = m.is_active;

  const remainPct =
    isTimes && m.total_count && m.total_count > 0
      ? Math.max(0, Math.round(((m.remaining_count ?? 0) / m.total_count) * 100))
      : null;

  return (
    <View style={[c.card, !isActive && c.inactiveCard]}>
      {/* 헤더 */}
      <View style={c.cardHeader}>
        <View>
          <Text style={c.typeLabel}>{isTimes ? "횟수제 수강권" : "기간제 수강권"}</Text>
          <Text style={c.dateRange}>
            {formatDate(m.started_at)} ~ {formatDate(m.expires_at)}
          </Text>
        </View>
        <View style={[c.statusBadge, isActive ? c.activeBadge : c.expiredBadge]}>
          <Text style={[c.statusTxt, isActive ? c.activeTxt : c.expiredTxt]}>
            {isActive ? "활성" : "만료"}
          </Text>
        </View>
      </View>

      {/* 횟수제: 남은 횟수 + 프로그레스 바 */}
      {isTimes && (
        <View style={c.timesSection}>
          <View style={c.timesRow}>
            <Text style={c.timesLabel}>잔여 횟수</Text>
            <Text style={c.timesValue}>
              <Text style={[c.remain, isActive && (m.remaining_count ?? 0) === 0 && c.remainZero]}>
                {m.remaining_count ?? 0}
              </Text>
              <Text style={c.totalSlash}> / {m.total_count ?? 0}회</Text>
            </Text>
          </View>
          {remainPct !== null && (
            <View style={c.progressBg}>
              <View
                style={[
                  c.progressFill,
                  { width: `${remainPct}%` as any },
                  remainPct <= 20 && c.progressLow,
                ]}
              />
            </View>
          )}
        </View>
      )}

      {/* 기간제: 남은 날짜 */}
      {!isTimes && m.expires_at && isActive && (
        <View style={c.periodSection}>
          <Text style={c.periodLabel}>남은 기간</Text>
          <Text style={c.periodDays}>
            {Math.max(0, Math.floor(
              (new Date(m.expires_at).getTime() - Date.now()) / 86_400_000
            ))}일
          </Text>
        </View>
      )}

      {/* 메모 */}
      {m.notes && <Text style={c.notes}>{m.notes}</Text>}
    </View>
  );
}

export default function MembershipScreen() {
  const router = useRouter();
  const [memberships, setMemberships] = useState<MembershipRead[]>([]);
  const [loading, setLoading] = useState(true);
  const initialLoaded = useRef(false);

  useFocusEffect(
    useCallback(() => {
      if (!initialLoaded.current) setLoading(true);
      apiFetch<MembershipRead[]>("/memberships")
        .then(setMemberships)
        .catch(console.error)
        .finally(() => { setLoading(false); initialLoaded.current = true; });
    }, [])
  );

  const active   = memberships.filter(m => m.is_active);
  const inactive = memberships.filter(m => !m.is_active);

  return (
    <View style={s.container}>
      {/* 헤더 */}
      <View style={s.header}>
        <Pressable onPress={() => router.back()} style={s.backBtn}>
          <Text style={s.backTxt}>← 뒤로</Text>
        </Pressable>
        <Text style={s.title}>수강권 현황</Text>
      </View>

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" /></View>
      ) : memberships.length === 0 ? (
        <View style={s.emptyBox}>
          <Text style={s.emptyEmoji}>🎫</Text>
          <Text style={s.emptyTitle}>등록된 수강권이 없습니다</Text>
          <Text style={s.emptySub}>담당 강사에게 수강권 등록을 요청하세요</Text>
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>
          {/* 활성 수강권 */}
          {active.length > 0 && (
            <>
              <Text style={s.sectionLabel}>활성 수강권 ({active.length})</Text>
              {active.map(m => <MembershipCard key={m.id} m={m} />)}
            </>
          )}

          {/* 만료 수강권 */}
          {inactive.length > 0 && (
            <>
              <Text style={[s.sectionLabel, { marginTop: 24 }]}>만료된 수강권 ({inactive.length})</Text>
              {inactive.map(m => <MembershipCard key={m.id} m={m} />)}
            </>
          )}
        </ScrollView>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  container:  { flex: 1, backgroundColor: "#f9fafb" },
  header:     { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingTop: 56, paddingBottom: 16, backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  backBtn:    { marginRight: 12 },
  backTxt:    { fontSize: 15, color: "#6b7280", fontWeight: "500" },
  title:      { fontSize: 18, fontWeight: "700", color: "#111" },
  center:     { flex: 1, alignItems: "center", justifyContent: "center" },
  sectionLabel: { fontSize: 13, fontWeight: "700", color: "#6b7280", marginHorizontal: 16, marginTop: 20, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 },
  emptyBox:   { flex: 1, alignItems: "center", justifyContent: "center", padding: 40 },
  emptyEmoji: { fontSize: 56, marginBottom: 16 },
  emptyTitle: { fontSize: 17, fontWeight: "700", color: "#374151", marginBottom: 6 },
  emptySub:   { fontSize: 13, color: "#9ca3af", textAlign: "center" },
});

const c = StyleSheet.create({
  card:         { marginHorizontal: 16, marginVertical: 6, backgroundColor: "#fff", borderRadius: 16, padding: 16, shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 8, elevation: 2 },
  inactiveCard: { opacity: 0.6 },
  cardHeader:   { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 },
  typeLabel:    { fontSize: 15, fontWeight: "700", color: "#111" },
  dateRange:    { fontSize: 12, color: "#9ca3af", marginTop: 2 },
  statusBadge:  { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 20 },
  activeBadge:  { backgroundColor: "#d1fae5" },
  expiredBadge: { backgroundColor: "#f3f4f6" },
  statusTxt:    { fontSize: 11, fontWeight: "700" },
  activeTxt:    { color: "#10b981" },
  expiredTxt:   { color: "#9ca3af" },
  timesSection: { marginBottom: 4 },
  timesRow:     { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  timesLabel:   { fontSize: 13, color: "#6b7280" },
  timesValue:   { fontSize: 13 },
  remain:       { fontSize: 22, fontWeight: "800", color: "#1a1a1a" },
  remainZero:   { color: "#ef4444" },
  totalSlash:   { fontSize: 13, color: "#9ca3af" },
  progressBg:   { height: 8, backgroundColor: "#f3f4f6", borderRadius: 4, overflow: "hidden" },
  progressFill: { height: 8, backgroundColor: "#10b981", borderRadius: 4 },
  progressLow:  { backgroundColor: "#ef4444" },
  periodSection: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  periodLabel:  { fontSize: 13, color: "#6b7280" },
  periodDays:   { fontSize: 22, fontWeight: "800", color: "#1a1a1a" },
  notes:        { marginTop: 10, fontSize: 12, color: "#9ca3af", fontStyle: "italic", borderTopWidth: 1, borderTopColor: "#f3f4f6", paddingTop: 10 },
});
