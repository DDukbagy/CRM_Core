import { useCallback, useState } from "react";
import {
  View, Text, ScrollView, Pressable, Modal, Alert,
  StyleSheet, ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { CustomerPassRead, PassTypeRead, UserRead } from "@/types/api";

const STATUS_COLOR: Record<string, string> = {
  ACTIVE: "#16a34a", COMPLETED: "#6b7280", EXPIRED: "#f97316", CANCELLED: "#ef4444",
};
const STATUS_LABEL: Record<string, string> = {
  ACTIVE: "진행중", COMPLETED: "완료", EXPIRED: "만료", CANCELLED: "취소",
};

export default function PassesScreen() {
  const [passes, setPasses] = useState<CustomerPassRead[]>([]);
  const [managerId, setManagerId] = useState<string | null>(null);
  const [instructorInfo, setInstructorInfo] = useState<UserRead | null>(null);
  const [availableTypes, setAvailableTypes] = useState<PassTypeRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalPass, setModalPass] = useState<CustomerPassRead | null>(null);

  useFocusEffect(useCallback(() => { load(); }, []));

  async function load() {
    setLoading(true);
    try {
      const [passData, meData] = await Promise.all([
        apiFetch<CustomerPassRead[]>("/passes/me"),
        apiFetch<UserRead>("/users/me"),
      ]);
      const myPasses = Array.isArray(passData) ? passData : [];
      setPasses(myPasses);

      const mid = meData.manager_id ?? null;
      setManagerId(mid);

      if (mid) {
        const [types, instructor] = await Promise.all([
          apiFetch<PassTypeRead[]>(`/passes/instructor/${mid}/types`),
          apiFetch<UserRead>(`/users/${mid}`),
        ]);
        setAvailableTypes(Array.isArray(types) ? types.filter(t => t.is_active) : []);
        setInstructorInfo(instructor ?? null);
      } else {
        setAvailableTypes([]);
        setInstructorInfo(null);
      }
    } catch (e) {
      console.error("수강권 로드 실패:", e);
    } finally {
      setLoading(false);
    }
  }

  const activePass = passes.find(p => p.status === "ACTIVE") ?? null;

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color="#16a34a" />
      </View>
    );
  }

  if (!managerId) {
    return (
      <View style={s.center}>
        <Text style={s.emptyIcon}>🎫</Text>
        <Text style={s.emptyTitle}>담당 강사가 없습니다</Text>
        <Text style={s.emptySub}>강사에게 문의하여 수강권을 발급받으세요</Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: "#f9fafb" }}>
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>

        {/* 현재 받고 있는 레슨 */}
        {activePass && (
          <>
            <Text style={s.section}>현재 받고 있는 레슨</Text>
            <View style={s.activeCard}>
              <View style={s.activeTop}>
                <Text style={s.activeName}>{activePass.pass_name}</Text>
                <View style={s.activeBadge}>
                  <Text style={s.activeBadgeTxt}>진행중</Text>
                </View>
              </View>
              <Pressable onPress={() => setModalPass(activePass)} style={s.instructorRow}>
                <View style={s.dot} />
                <Text style={s.instructorRowName}>
                  {activePass.instructor?.display_name ?? "강사"}
                </Text>
                {activePass.instructor?.instructor_location ? (
                  <Text style={s.instructorRowLoc} numberOfLines={1}>
                    {activePass.instructor.instructor_location}
                  </Text>
                ) : null}
                <Text style={s.arrow}>상세 →</Text>
              </Pressable>
              <Text style={s.activeDuration}>회당 {activePass.duration_hours}시간 레슨</Text>
              <View style={s.progressWrap}>
                <View style={s.track}>
                  <View style={[s.fill, {
                    width: `${activePass.sessions_total > 0
                      ? Math.min((activePass.sessions_used / activePass.sessions_total) * 100, 100)
                      : 0}%`
                  }]} />
                </View>
                <Text style={s.progressTxt}>
                  {activePass.sessions_used} / {activePass.sessions_total}회 · 남은 횟수 {activePass.sessions_remaining}회
                </Text>
              </View>
            </View>
            <Pressable
              style={s.renewBtn}
              onPress={() =>
                Alert.alert("갱신 준비 중", "결제 기능 연동 후 이용 가능합니다.", [{ text: "확인" }])
              }
            >
              <Text style={s.renewBtnTxt}>갱신하기</Text>
            </Pressable>
          </>
        )}

        {/* 강사 프로필 */}
        <Text style={s.section}>강사 수강권</Text>
        {instructorInfo && (
          <View style={s.instructorCard}>
            <View style={s.avatar}>
              <Text style={s.avatarTxt}>{instructorInfo.display_name.charAt(0)}</Text>
            </View>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={s.instructorName}>{instructorInfo.display_name} 강사</Text>
              {instructorInfo.instructor_location ? (
                <Text style={s.instructorMeta}>📍 {instructorInfo.instructor_location}</Text>
              ) : null}
              {instructorInfo.instructor_specialties ? (
                <Text style={s.instructorMeta}>⛳ {instructorInfo.instructor_specialties}</Text>
              ) : null}
              {instructorInfo.instructor_bio ? (
                <Text style={s.instructorBio}>{instructorInfo.instructor_bio}</Text>
              ) : null}
            </View>
          </View>
        )}

        {/* 수강권 상품 목록 */}
        {availableTypes.length === 0 ? (
          <View style={s.noTypesWrap}>
            <Text style={s.noTypesTxt}>등록된 수강권 상품이 없습니다</Text>
          </View>
        ) : (
          availableTypes.map((pt, idx) => (
            <View
              key={pt.id}
              style={[
                s.typeRow,
                idx === 0 && s.typeRowFirst,
                idx === availableTypes.length - 1 && s.typeRowLast,
              ]}
            >
              <View style={s.typeLeft}>
                <Text style={s.typeRowName}>{pt.name}</Text>
                <Text style={s.typeRowMeta}>
                  {`${pt.session_count}회 · 회당 ${pt.duration_hours}시간`}
                </Text>
                {pt.description ? (
                  <Text style={s.typeRowDesc}>{pt.description}</Text>
                ) : null}
              </View>
              {pt.price !== null && (
                <Text style={s.typeRowPrice}>{pt.price.toLocaleString()}원</Text>
              )}
            </View>
          ))
        )}

        {/* 결제 버튼 (수강권 목록 바로 아래) */}
        {availableTypes.length > 0 && (
          <Pressable
            style={s.buyBtn}
            onPress={() =>
              Alert.alert(
                "결제 준비 중",
                "현재 결제 기능을 준비하고 있습니다.\n강사에게 직접 문의해주세요.",
                [{ text: "확인" }]
              )
            }
          >
            <Text style={s.buyBtnTxt}>수강권 결제하기</Text>
          </Pressable>
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
            {modalPass?.instructor && (
              <View style={md.instructorCard}>
                <View style={md.avatar}>
                  <Text style={md.avatarTxt}>
                    {modalPass.instructor.display_name.charAt(0)}
                  </Text>
                </View>
                <View style={{ flex: 1, gap: 6 }}>
                  <Text style={md.instructorName}>{modalPass.instructor.display_name}</Text>
                  {modalPass.instructor.instructor_location ? (
                    <Text style={md.instructorMeta}>📍 {modalPass.instructor.instructor_location}</Text>
                  ) : null}
                  {modalPass.instructor.instructor_specialties ? (
                    <Text style={md.instructorMeta}>⛳ {modalPass.instructor.instructor_specialties}</Text>
                  ) : null}
                  {modalPass.instructor.instructor_bio ? (
                    <Text style={md.instructorBio}>{modalPass.instructor.instructor_bio}</Text>
                  ) : null}
                </View>
              </View>
            )}
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  emptyIcon: { fontSize: 52 },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: "#111" },
  emptySub: { fontSize: 14, color: "#9ca3af", textAlign: "center", paddingHorizontal: 40 },
  section: {
    fontSize: 13, fontWeight: "700", color: "#6b7280",
    paddingHorizontal: 16, paddingTop: 20, paddingBottom: 10,
    textTransform: "uppercase", letterSpacing: 0.6,
  },
  // 현재 수강권 카드
  activeCard: {
    backgroundColor: "#fff", borderRadius: 16, padding: 18,
    marginHorizontal: 16, marginBottom: 10,
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07, shadowRadius: 6, elevation: 3,
  },
  activeTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
  activeName: { fontSize: 18, fontWeight: "800", color: "#111", flex: 1 },
  activeBadge: { backgroundColor: "#dcfce7", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  activeBadgeTxt: { fontSize: 12, fontWeight: "700", color: "#16a34a" },
  instructorRow: {
    flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 8,
    backgroundColor: "#f9fafb", borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7,
  },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: "#16a34a" },
  instructorRowName: { fontSize: 14, fontWeight: "600", color: "#111" },
  instructorRowLoc: { fontSize: 12, color: "#9ca3af", flex: 1 },
  arrow: { fontSize: 12, color: "#16a34a", fontWeight: "700" },
  activeDuration: { fontSize: 13, color: "#6b7280", marginBottom: 10 },
  progressWrap: { gap: 6 },
  track: { height: 8, backgroundColor: "#f3f4f6", borderRadius: 4, overflow: "hidden" },
  fill: { height: "100%", backgroundColor: "#16a34a", borderRadius: 4 },
  progressTxt: { fontSize: 12, color: "#6b7280", textAlign: "right" },
  // 갱신 버튼
  renewBtn: {
    marginHorizontal: 16, marginBottom: 4,
    borderWidth: 1.5, borderColor: "#16a34a", borderRadius: 12,
    paddingVertical: 12, alignItems: "center",
  },
  renewBtnTxt: { fontSize: 14, fontWeight: "700", color: "#16a34a" },
  // 강사 프로필 카드
  instructorCard: {
    flexDirection: "row", gap: 12,
    backgroundColor: "#fff", borderRadius: 14, padding: 14,
    marginHorizontal: 16, marginBottom: 2,
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06, shadowRadius: 4, elevation: 2,
  },
  avatar: {
    width: 48, height: 48, borderRadius: 24,
    backgroundColor: "#16a34a", alignItems: "center", justifyContent: "center",
    flexShrink: 0,
  },
  avatarTxt: { fontSize: 20, fontWeight: "700", color: "#fff" },
  instructorName: { fontSize: 15, fontWeight: "700", color: "#111" },
  instructorMeta: { fontSize: 12, color: "#6b7280" },
  instructorBio: { fontSize: 12, color: "#374151", lineHeight: 17, marginTop: 2 },
  // 수강권 목록 (리스트 형태)
  typeRow: {
    flexDirection: "row", alignItems: "flex-start",
    backgroundColor: "#fff", paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: "#f3f4f6",
    marginHorizontal: 16,
  },
  typeRowFirst: { borderTopLeftRadius: 12, borderTopRightRadius: 12, marginTop: 8 },
  typeRowLast: { borderBottomLeftRadius: 12, borderBottomRightRadius: 12, borderBottomWidth: 0 },
  typeLeft: { flex: 1, gap: 3 },
  typeRowName: { fontSize: 15, fontWeight: "700", color: "#111" },
  typeRowMeta: { fontSize: 12, color: "#6b7280" },
  typeRowDesc: { fontSize: 12, color: "#9ca3af", marginTop: 2, lineHeight: 16 },
  typeRowPrice: { fontSize: 16, fontWeight: "800", color: "#16a34a", marginLeft: 12 },
  noTypesWrap: { alignItems: "center", paddingVertical: 24, marginHorizontal: 16 },
  noTypesTxt: { fontSize: 14, color: "#9ca3af" },
  buyBtn: {
    backgroundColor: "#1a1a1a", borderRadius: 12,
    paddingVertical: 14, alignItems: "center",
    marginHorizontal: 16, marginTop: 12, marginBottom: 8,
  },
  buyBtnTxt: { color: "#fff", fontSize: 16, fontWeight: "700" },
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
});
