import { useCallback, useState } from "react";
import {
  View, Text, ScrollView, Pressable, Modal,
  StyleSheet, ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { CustomerPassRead, PassTypeRead } from "@/types/api";

const STATUS_COLOR: Record<string, string> = {
  ACTIVE: "#16a34a", COMPLETED: "#6b7280", EXPIRED: "#f97316", CANCELLED: "#ef4444",
};
const STATUS_LABEL: Record<string, string> = {
  ACTIVE: "진행중", COMPLETED: "완료", EXPIRED: "만료", CANCELLED: "취소",
};

export default function PassesScreen() {
  const [passes, setPasses] = useState<CustomerPassRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalPass, setModalPass] = useState<CustomerPassRead | null>(null);
  const [instructorTypes, setInstructorTypes] = useState<PassTypeRead[]>([]);
  const [loadingTypes, setLoadingTypes] = useState(false);

  useFocusEffect(useCallback(() => { load(); }, []));

  async function load() {
    setLoading(true);
    try {
      const data = await apiFetch<CustomerPassRead[]>("/passes/me");
      setPasses(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("수강권 로드 실패:", e);
    } finally {
      setLoading(false);
    }
  }

  async function openInstructor(pass: CustomerPassRead) {
    setModalPass(pass);
    setLoadingTypes(true);
    try {
      const types = await apiFetch<PassTypeRead[]>(
        `/passes/instructor/${pass.instructor_id}/types`
      );
      setInstructorTypes(Array.isArray(types) ? types : []);
    } catch {
      setInstructorTypes([]);
    } finally {
      setLoadingTypes(false);
    }
  }

  const active = passes.filter((p) => p.status === "ACTIVE");
  const past = passes.filter((p) => p.status !== "ACTIVE");

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color="#16a34a" />
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <ScrollView style={s.container} contentContainerStyle={{ paddingBottom: 40 }}>
        {passes.length === 0 ? (
          <View style={s.emptyWrap}>
            <Text style={s.emptyIcon}>🎫</Text>
            <Text style={s.emptyTitle}>보유한 수강권이 없습니다</Text>
            <Text style={s.emptySub}>강사에게 문의하여 수강권을 발급받으세요</Text>
          </View>
        ) : (
          <>
            {active.length > 0 && (
              <>
                <Text style={s.section}>진행중인 수강권</Text>
                {active.map((p) => (
                  <PassCard key={p.id} pass={p} onPressInstructor={() => openInstructor(p)} />
                ))}
              </>
            )}
            {past.length > 0 && (
              <>
                <Text style={s.section}>과거 수강권</Text>
                {past.map((p) => (
                  <PassCard key={p.id} pass={p} onPressInstructor={() => openInstructor(p)} />
                ))}
              </>
            )}
          </>
        )}
      </ScrollView>

      {/* 강사 상세 모달 */}
      <Modal
        visible={modalPass !== null}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setModalPass(null)}
      >
        <View style={{ flex: 1, backgroundColor: "#f9fafb" }}>
          <View style={md.header}>
            <Text style={md.headerTitle}>강사 정보</Text>
            <Pressable onPress={() => setModalPass(null)} style={md.closeBtn}>
              <Text style={md.closeTxt}>✕</Text>
            </Pressable>
          </View>

          <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 40 }}>
            {/* 강사 카드 */}
            {modalPass?.instructor && (
              <View style={md.instructorCard}>
                <View style={md.avatar}>
                  <Text style={md.avatarTxt}>
                    {modalPass.instructor.display_name.charAt(0)}
                  </Text>
                </View>
                <View style={{ flex: 1, gap: 6 }}>
                  <Text style={md.instructorName}>
                    {modalPass.instructor.display_name}
                  </Text>
                  {modalPass.instructor.instructor_location ? (
                    <Text style={md.instructorMeta}>
                      📍 {modalPass.instructor.instructor_location}
                    </Text>
                  ) : null}
                  {modalPass.instructor.instructor_specialties ? (
                    <Text style={md.instructorMeta}>
                      ⛳ {modalPass.instructor.instructor_specialties}
                    </Text>
                  ) : null}
                  {modalPass.instructor.instructor_bio ? (
                    <Text style={md.instructorBio}>
                      {modalPass.instructor.instructor_bio}
                    </Text>
                  ) : null}
                </View>
              </View>
            )}

            {/* 수강권 상품 목록 */}
            <Text style={md.sectionLabel}>제공 수강권 상품</Text>
            {loadingTypes ? (
              <ActivityIndicator color="#16a34a" style={{ marginTop: 20 }} />
            ) : instructorTypes.length === 0 ? (
              <Text style={md.noData}>등록된 수강권 상품이 없습니다</Text>
            ) : (
              instructorTypes.map((pt) => (
                <View key={pt.id} style={md.typeCard}>
                  <Text style={md.typeName}>{pt.name}</Text>
                  <View style={md.pillRow}>
                    <Pill label={`회당 ${pt.duration_hours}시간`} />
                    <Pill label={`총 ${pt.session_count}회`} />
                    {pt.price !== null && (
                      <Pill
                        label={`${pt.price.toLocaleString()}원`}
                        color="#fff7ed"
                        textColor="#f97316"
                      />
                    )}
                  </View>
                  {pt.description ? (
                    <Text style={md.typeDesc}>{pt.description}</Text>
                  ) : null}
                </View>
              ))
            )}
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

// ─── Pass Card ───────────────────────────────────────────────────────────────
function PassCard({
  pass,
  onPressInstructor,
}: {
  pass: CustomerPassRead;
  onPressInstructor: () => void;
}) {
  const sc = STATUS_COLOR[pass.status] ?? "#9ca3af";
  const sl = STATUS_LABEL[pass.status] ?? pass.status;
  const pct =
    pass.sessions_total > 0
      ? Math.min((pass.sessions_used / pass.sessions_total) * 100, 100)
      : 0;

  return (
    <View style={[c.card, pass.status !== "ACTIVE" && c.dim]}>
      {/* 상단: 수강권명 + 상태 */}
      <View style={c.row}>
        <Text style={c.passName} numberOfLines={1}>
          {pass.pass_name}
        </Text>
        <View style={[c.pill, { backgroundColor: sc + "22" }]}>
          <Text style={[c.pillTxt, { color: sc }]}>{sl}</Text>
        </View>
      </View>

      {/* 강사 정보 (탭 → 모달) */}
      <Pressable onPress={onPressInstructor} style={c.instructorRow}>
        <View style={c.dot} />
        <Text style={c.instructorName}>
          {pass.instructor?.display_name ?? "강사"}
        </Text>
        {pass.instructor?.instructor_location ? (
          <Text style={c.instructorLoc} numberOfLines={1}>
            {pass.instructor.instructor_location}
          </Text>
        ) : null}
        <Text style={c.arrow}>상세 →</Text>
      </Pressable>

      {/* 회당 시간 */}
      <Text style={c.duration}>회당 {pass.duration_hours}시간 레슨</Text>

      {/* 진도 */}
      <View style={c.progressWrap}>
        <View style={c.track}>
          <View style={[c.fill, { width: `${pct}%` }]} />
        </View>
        <Text style={c.progressTxt}>
          {pass.sessions_used} / {pass.sessions_total}회
          {pass.status === "ACTIVE"
            ? ` · 남은 횟수 ${pass.sessions_remaining}회`
            : ""}
        </Text>
      </View>
    </View>
  );
}

function Pill({
  label,
  color = "#f0fdf4",
  textColor = "#16a34a",
}: {
  label: string;
  color?: string;
  textColor?: string;
}) {
  return (
    <View style={[md.pill, { backgroundColor: color }]}>
      <Text style={[md.pillTxt, { color: textColor }]}>{label}</Text>
    </View>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  section: {
    fontSize: 13, fontWeight: "700", color: "#6b7280",
    paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8,
    textTransform: "uppercase", letterSpacing: 0.6,
  },
  emptyWrap: { alignItems: "center", paddingTop: 120, gap: 12 },
  emptyIcon: { fontSize: 52 },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: "#111" },
  emptySub: { fontSize: 14, color: "#9ca3af", textAlign: "center", paddingHorizontal: 40 },
});

const c = StyleSheet.create({
  card: {
    backgroundColor: "#fff",
    marginHorizontal: 16, marginBottom: 12,
    borderRadius: 16, padding: 18,
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07, shadowRadius: 6, elevation: 3,
  },
  dim: { opacity: 0.6 },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
  passName: { fontSize: 18, fontWeight: "800", color: "#111", flex: 1 },
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  pillTxt: { fontSize: 12, fontWeight: "700" },
  instructorRow: {
    flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 8,
    backgroundColor: "#f9fafb", borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7,
  },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: "#16a34a" },
  instructorName: { fontSize: 14, fontWeight: "600", color: "#111" },
  instructorLoc: { fontSize: 12, color: "#9ca3af", flex: 1 },
  arrow: { fontSize: 12, color: "#16a34a", fontWeight: "700" },
  duration: { fontSize: 13, color: "#6b7280", marginBottom: 12 },
  progressWrap: { gap: 6 },
  track: { height: 8, backgroundColor: "#f3f4f6", borderRadius: 4, overflow: "hidden" },
  fill: { height: "100%", backgroundColor: "#16a34a", borderRadius: 4 },
  progressTxt: { fontSize: 12, color: "#6b7280", textAlign: "right" },
});

const md = StyleSheet.create({
  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 20, paddingTop: 20, paddingBottom: 14,
    backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#f3f4f6",
  },
  headerTitle: { fontSize: 18, fontWeight: "700", color: "#111" },
  closeBtn: { padding: 6 },
  closeTxt: { fontSize: 18, color: "#9ca3af" },
  instructorCard: {
    flexDirection: "row", gap: 14, backgroundColor: "#fff",
    borderRadius: 14, padding: 16, marginBottom: 20,
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06, shadowRadius: 4, elevation: 2,
  },
  avatar: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: "#16a34a", alignItems: "center", justifyContent: "center",
    flexShrink: 0,
  },
  avatarTxt: { fontSize: 22, fontWeight: "700", color: "#fff" },
  instructorName: { fontSize: 17, fontWeight: "700", color: "#111" },
  instructorMeta: { fontSize: 13, color: "#6b7280" },
  instructorBio: { fontSize: 13, color: "#374151", lineHeight: 18, marginTop: 2 },
  sectionLabel: {
    fontSize: 13, fontWeight: "700", color: "#6b7280",
    marginBottom: 12, textTransform: "uppercase", letterSpacing: 0.6,
  },
  noData: { textAlign: "center", color: "#9ca3af", paddingTop: 20 },
  typeCard: {
    backgroundColor: "#fff", borderRadius: 12, padding: 14, marginBottom: 10,
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05, shadowRadius: 4, elevation: 2,
  },
  typeName: { fontSize: 15, fontWeight: "700", color: "#111", marginBottom: 8 },
  pillRow: { flexDirection: "row", gap: 6, flexWrap: "wrap", marginBottom: 4 },
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  pillTxt: { fontSize: 12, fontWeight: "600" },
  typeDesc: { fontSize: 13, color: "#6b7280", marginTop: 6, lineHeight: 18 },
});
