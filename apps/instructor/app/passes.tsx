/**
 * 강사 수강권 관리 화면
 * - 수강권 상품 CRUD (생성/수정/삭제/비활성화)
 * - 고객 수강권 현황 조회 및 서비스 횟수 추가
 */
import { useCallback, useEffect, useState } from "react";
import {
  View, Text, ScrollView, Pressable, Modal, TextInput,
  Alert, StyleSheet, ActivityIndicator, Switch,
} from "react-native";
import { useRouter } from "expo-router";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { PassTypeRead, CustomerPassRead } from "@/types/api";

const PASS_STATUS_COLOR: Record<string, string> = {
  ACTIVE: "#16a34a", COMPLETED: "#6b7280", EXPIRED: "#f97316", CANCELLED: "#ef4444",
};
const PASS_STATUS_LABEL: Record<string, string> = {
  ACTIVE: "진행중", COMPLETED: "완료", EXPIRED: "만료", CANCELLED: "취소",
};

// ─── 수강권 상품 폼 모달 ──────────────────────────────────────────────────────
function PassTypeFormModal({
  visible,
  initial,
  onClose,
  onSave,
}: {
  visible: boolean;
  initial: Partial<PassTypeRead> | null;
  onClose: () => void;
  onSave: () => void;
}) {
  const isEdit = initial !== null && initial.id !== undefined;
  const [name, setName] = useState(initial?.name ?? "");
  const [durationHours, setDurationHours] = useState(
    initial?.duration_hours?.toString() ?? "1"
  );
  const [sessionCount, setSessionCount] = useState(
    initial?.session_count?.toString() ?? ""
  );
  const [price, setPrice] = useState(initial?.price?.toString() ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [saving, setSaving] = useState(false);

  // initial 변경 시 폼 초기화
  const resetForm = useCallback(() => {
    setName(initial?.name ?? "");
    setDurationHours(initial?.duration_hours?.toString() ?? "1");
    setSessionCount(initial?.session_count?.toString() ?? "");
    setPrice(initial?.price?.toString() ?? "");
    setDescription(initial?.description ?? "");
    setIsActive(initial?.is_active ?? true);
  }, [initial]);

  useEffect(() => {
    if (visible) resetForm();
  }, [visible]);

  async function handleSave() {
    if (!name.trim() || !sessionCount.trim()) {
      Alert.alert("오류", "수강권명과 총 횟수는 필수입니다.");
      return;
    }
    setSaving(true);
    try {
      const body = {
        name: name.trim(),
        duration_hours: parseInt(durationHours) || 1,
        session_count: parseInt(sessionCount) || 1,
        price: price.trim() ? parseInt(price) : null,
        description: description.trim() || null,
        ...(isEdit ? { is_active: isActive } : {}),
      };
      if (isEdit && initial?.id) {
        await apiFetch(`/passes/types/${initial.id}`, { method: "PATCH", body });
      } else {
        await apiFetch("/passes/types", { method: "POST", body });
      }
      onSave();
      onClose();
    } catch (e: any) {
      Alert.alert("오류", e?.message ?? "저장 실패");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet">
      <View style={{ flex: 1, backgroundColor: "#f9fafb" }}>
        <View style={fm.header}>
          <Pressable onPress={onClose} style={fm.cancelBtn}>
            <Text style={fm.cancelTxt}>취소</Text>
          </Pressable>
          <Text style={fm.title}>{isEdit ? "수강권 수정" : "수강권 추가"}</Text>
          <Pressable
            onPress={handleSave}
            disabled={saving}
            style={[fm.saveBtn, saving && { opacity: 0.5 }]}
          >
            <Text style={fm.saveTxt}>{saving ? "저장중..." : "저장"}</Text>
          </Pressable>
        </View>

        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
          <Field label="수강권명 *">
            <TextInput
              style={fm.input}
              value={name}
              onChangeText={setName}
              placeholder="예: Short권"
              placeholderTextColor="#9ca3af"
            />
          </Field>
          <View style={{ flexDirection: "row", gap: 12 }}>
            <View style={{ flex: 1 }}>
              <Field label="회당 시간 (시간) *">
                <TextInput
                  style={fm.input}
                  value={durationHours}
                  onChangeText={setDurationHours}
                  keyboardType="number-pad"
                  placeholder="1"
                  placeholderTextColor="#9ca3af"
                />
              </Field>
            </View>
            <View style={{ flex: 1 }}>
              <Field label="총 횟수 *">
                <TextInput
                  style={fm.input}
                  value={sessionCount}
                  onChangeText={setSessionCount}
                  keyboardType="number-pad"
                  placeholder="30"
                  placeholderTextColor="#9ca3af"
                />
              </Field>
            </View>
          </View>
          <Field label="가격 (원, 선택)">
            <TextInput
              style={fm.input}
              value={price}
              onChangeText={setPrice}
              keyboardType="number-pad"
              placeholder="미입력 시 미설정"
              placeholderTextColor="#9ca3af"
            />
          </Field>
          <Field label="설명 (선택)">
            <TextInput
              style={[fm.input, { height: 80, textAlignVertical: "top" }]}
              value={description}
              onChangeText={setDescription}
              multiline
              placeholder="수강권 설명..."
              placeholderTextColor="#9ca3af"
            />
          </Field>
          {isEdit && (
            <View style={fm.switchRow}>
              <Text style={fm.switchLabel}>활성화</Text>
              <Switch
                value={isActive}
                onValueChange={setIsActive}
                trackColor={{ true: "#16a34a" }}
              />
            </View>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={fm.label}>{label}</Text>
      {children}
    </View>
  );
}

// ─── 서비스 횟수 추가 모달 ───────────────────────────────────────────────────
function AddSessionsModal({
  visible,
  cp,
  onClose,
  onSave,
}: {
  visible: boolean;
  cp: CustomerPassRead | null;
  onClose: () => void;
  onSave: () => void;
}) {
  const [sessions, setSessions] = useState("1");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  function reset() { setSessions("1"); setNote(""); }

  async function handleAdd() {
    const count = parseInt(sessions);
    if (!cp || isNaN(count) || count < 1) {
      Alert.alert("오류", "추가할 횟수를 1 이상 입력해주세요.");
      return;
    }
    setSaving(true);
    try {
      await apiFetch(`/passes/customer-passes/${cp.id}/add-sessions`, {
        method: "POST",
        body: { sessions: count, note: note.trim() || null },
      });
      onSave();
      reset();
      onClose();
    } catch (e: any) {
      Alert.alert("오류", e?.message ?? "처리 실패");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet">
      <View style={{ flex: 1, backgroundColor: "#f9fafb" }}>
        <View style={fm.header}>
          <Pressable onPress={() => { reset(); onClose(); }}>
            <Text style={fm.cancelTxt}>취소</Text>
          </Pressable>
          <Text style={fm.title}>서비스 횟수 추가</Text>
          <Pressable onPress={handleAdd} disabled={saving} style={[{ padding: 4 }, saving && { opacity: 0.5 }]}>
            <Text style={fm.saveTxt}>{saving ? "처리중..." : "추가"}</Text>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
          {cp && (
            <View style={am.selectedBadge}>
              <Text style={am.selectedTxt}>{cp.customer_name} · {cp.pass_name}</Text>
              <Text style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
                현재 {cp.sessions_used}/{cp.sessions_total}회 · 남은 {cp.sessions_remaining}회
              </Text>
            </View>
          )}
          <Field label="추가할 횟수 *">
            <TextInput
              style={fm.input}
              value={sessions}
              onChangeText={setSessions}
              keyboardType="number-pad"
              placeholder="1"
              placeholderTextColor="#9ca3af"
            />
          </Field>
          <Field label="메모 (선택)">
            <TextInput
              style={[fm.input, { height: 70, textAlignVertical: "top" }]}
              value={note}
              onChangeText={setNote}
              multiline
              placeholder="서비스 사유 등..."
              placeholderTextColor="#9ca3af"
            />
          </Field>
        </ScrollView>
      </View>
    </Modal>
  );
}

// ─── 메인 화면 ────────────────────────────────────────────────────────────────
export default function InstructorPassesScreen() {
  const router = useRouter();
  const [passTypes, setPassTypes] = useState<PassTypeRead[]>([]);
  const [customerPasses, setCustomerPasses] = useState<CustomerPassRead[]>([]);
  const [loading, setLoading] = useState(true);

  // 모달 상태
  const [formModal, setFormModal] = useState<{ open: boolean; target: Partial<PassTypeRead> | null }>({
    open: false, target: null,
  });
  const [addSessionsModal, setAddSessionsModal] = useState<CustomerPassRead | null>(null);

  useFocusEffect(useCallback(() => { load(); }, []));

  async function load() {
    setLoading(true);
    try {
      const [typesRes, passesRes] = await Promise.allSettled([
        apiFetch<PassTypeRead[]>("/passes/types"),
        apiFetch<CustomerPassRead[]>("/passes/customer-passes"),
      ]);
      if (typesRes.status === "fulfilled") setPassTypes(Array.isArray(typesRes.value) ? typesRes.value : []);
      if (passesRes.status === "fulfilled") setCustomerPasses(Array.isArray(passesRes.value) ? passesRes.value : []);
    } finally {
      setLoading(false);
    }
  }

  async function deletePassType(pt: PassTypeRead) {
    Alert.alert(
      "수강권 상품 삭제",
      `"${pt.name}"을(를) 삭제할까요?\n활성 수강권이 있으면 삭제되지 않습니다.`,
      [
        { text: "취소", style: "cancel" },
        {
          text: "삭제",
          style: "destructive",
          onPress: async () => {
            try {
              await apiFetch(`/passes/types/${pt.id}`, { method: "DELETE" });
              await load();
            } catch (e: any) {
              Alert.alert("삭제 실패", e?.message ?? "오류가 발생했습니다.");
            }
          },
        },
      ]
    );
  }

  async function cancelCustomerPass(cp: CustomerPassRead) {
    Alert.alert(
      "수강권 취소",
      `${cp.customer_name}의 "${cp.pass_name}"을(를) 취소할까요?`,
      [
        { text: "취소", style: "cancel" },
        {
          text: "수강권 취소",
          style: "destructive",
          onPress: async () => {
            try {
              await apiFetch(`/passes/customer-passes/${cp.id}`, {
                method: "PATCH",
                body: { status: "CANCELLED" },
              });
              await load();
            } catch (e: any) {
              Alert.alert("오류", e?.message ?? "처리 실패");
            }
          },
        },
      ]
    );
  }

  const activePasses = customerPasses.filter((p) => p.status === "ACTIVE");
  const pastPasses = customerPasses.filter((p) => p.status !== "ACTIVE");

  return (
    <View style={{ flex: 1, backgroundColor: "#f3f4f6" }}>
      {/* 헤더 */}
      <View style={s.header}>
        <Pressable onPress={() => router.canGoBack() ? router.back() : router.replace("/(tabs)")} style={s.backBtn}>
          <Text style={s.backTxt}>← 뒤로</Text>
        </Pressable>
        <Text style={s.headerTitle}>수강권 관리</Text>
        <View style={{ width: 70 }} />
      </View>

      {loading ? (
        <View style={s.center}>
          <ActivityIndicator size="large" color="#16a34a" />
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
          {/* ── 수강권 상품 섹션 ──────────────────────────────── */}
          <View style={s.sectionHeader}>
            <Text style={s.sectionTitle}>수강권 상품</Text>
            <Pressable
              style={s.addBtn}
              onPress={() => setFormModal({ open: true, target: null })}
            >
              <Text style={s.addBtnTxt}>+ 추가</Text>
            </Pressable>
          </View>

          {passTypes.length === 0 ? (
            <View style={s.emptyBox}>
              <Text style={s.emptyTxt}>등록된 수강권 상품이 없습니다</Text>
            </View>
          ) : (
            passTypes.map((pt) => (
              <View key={pt.id} style={[s.typeCard, !pt.is_active && s.typeCardDim]}>
                <View style={s.typeTop}>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                      <Text style={s.typeName}>{pt.name}</Text>
                      {!pt.is_active && (
                        <View style={s.inactiveBadge}>
                          <Text style={s.inactiveTxt}>비활성</Text>
                        </View>
                      )}
                    </View>
                    <Text style={s.typeMeta}>
                      회당 {pt.duration_hours}시간 · 총 {pt.session_count}회
                      {pt.price !== null ? ` · ${pt.price.toLocaleString()}원` : ""}
                    </Text>
                    {pt.description ? (
                      <Text style={s.typeDesc} numberOfLines={2}>{pt.description}</Text>
                    ) : null}
                  </View>
                  <View style={s.typeBtns}>
                    <Pressable
                      style={s.editBtn}
                      onPress={() => setFormModal({ open: true, target: pt })}
                    >
                      <Text style={s.editTxt}>수정</Text>
                    </Pressable>
                    <Pressable style={s.deleteBtn} onPress={() => deletePassType(pt)}>
                      <Text style={s.deleteTxt}>삭제</Text>
                    </Pressable>
                  </View>
                </View>
              </View>
            ))
          )}

          {/* ── 수강권 현황 섹션 ────────────────────────────────── */}
          <View style={s.sectionHeader}>
            <Text style={s.sectionTitle}>수강권 현황</Text>
          </View>

          {customerPasses.length === 0 ? (
            <View style={s.emptyBox}>
              <Text style={s.emptyTxt}>수강권이 없습니다</Text>
            </View>
          ) : (
            <>
              {activePasses.length > 0 && (
                <>
                  <Text style={s.subSection}>진행중</Text>
                  {activePasses.map((cp) => (
                    <CustomerPassCard
                      key={cp.id}
                      cp={cp}
                      onAddSessions={() => setAddSessionsModal(cp)}
                      onCancel={() => cancelCustomerPass(cp)}
                    />
                  ))}
                </>
              )}
              {pastPasses.length > 0 && (
                <>
                  <Text style={s.subSection}>종료된 수강권</Text>
                  {pastPasses.map((cp) => (
                    <CustomerPassCard key={cp.id} cp={cp} />
                  ))}
                </>
              )}
            </>
          )}
        </ScrollView>
      )}

      {/* 수강권 상품 폼 모달 */}
      <PassTypeFormModal
        visible={formModal.open}
        initial={formModal.target}
        onClose={() => setFormModal({ open: false, target: null })}
        onSave={load}
      />

      {/* 서비스 횟수 추가 모달 */}
      <AddSessionsModal
        visible={addSessionsModal !== null}
        cp={addSessionsModal}
        onClose={() => setAddSessionsModal(null)}
        onSave={load}
      />
    </View>
  );
}

// ─── 고객 수강권 카드 ─────────────────────────────────────────────────────────
function CustomerPassCard({
  cp,
  onAddSessions,
  onCancel,
}: {
  cp: CustomerPassRead;
  onAddSessions?: () => void;
  onCancel?: () => void;
}) {
  const sc = PASS_STATUS_COLOR[cp.status] ?? "#9ca3af";
  const sl = PASS_STATUS_LABEL[cp.status] ?? cp.status;
  const pct =
    cp.sessions_total > 0
      ? Math.min((cp.sessions_used / cp.sessions_total) * 100, 100)
      : 0;

  return (
    <View style={[cp_s.card, cp.status !== "ACTIVE" && cp_s.dim]}>
      <View style={cp_s.top}>
        <View style={{ flex: 1 }}>
          <Text style={cp_s.customerName}>{cp.customer_name ?? "알 수 없음"}</Text>
          <Text style={cp_s.passName}>{cp.pass_name}</Text>
          <Text style={cp_s.meta}>회당 {cp.duration_hours}h</Text>
        </View>
        <View style={[cp_s.statusPill, { backgroundColor: sc + "22" }]}>
          <Text style={[cp_s.statusTxt, { color: sc }]}>{sl}</Text>
        </View>
      </View>

      {/* 진도 */}
      <View style={cp_s.progressWrap}>
        <View style={cp_s.track}>
          <View style={[cp_s.fill, { width: `${pct}%` }]} />
        </View>
        <Text style={cp_s.progressTxt}>
          {cp.sessions_used} / {cp.sessions_total}회 · 남은 {cp.sessions_remaining}회
        </Text>
      </View>

      {/* 액션 버튼 (ACTIVE만) */}
      {cp.status === "ACTIVE" && (onAddSessions || onCancel) && (
        <View style={cp_s.actions}>
          {onAddSessions && (
            <Pressable style={cp_s.useBtn} onPress={onAddSessions}>
              <Text style={cp_s.useTxt}>서비스 횟수 추가</Text>
            </Pressable>
          )}
          {onCancel && (
            <Pressable style={cp_s.cancelBtn} onPress={onCancel}>
              <Text style={cp_s.cancelTxt}>취소</Text>
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingTop: 56, paddingBottom: 16,
    backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#f3f4f6",
  },
  backBtn: { padding: 4 },
  backTxt: { fontSize: 15, color: "#16a34a", fontWeight: "600" },
  headerTitle: { fontSize: 18, fontWeight: "700", color: "#111" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  sectionHeader: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8,
  },
  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  addBtn: {
    backgroundColor: "#16a34a", paddingHorizontal: 14, paddingVertical: 7,
    borderRadius: 20,
  },
  addBtnTxt: { color: "#fff", fontSize: 13, fontWeight: "700" },
  subSection: {
    fontSize: 12, fontWeight: "700", color: "#9ca3af",
    paddingHorizontal: 16, paddingTop: 8, paddingBottom: 4,
    textTransform: "uppercase", letterSpacing: 0.5,
  },
  emptyBox: {
    marginHorizontal: 16, padding: 20, backgroundColor: "#fff",
    borderRadius: 12, alignItems: "center",
  },
  emptyTxt: { color: "#9ca3af", fontSize: 14 },

  // Pass Type Card
  typeCard: {
    backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8,
    borderRadius: 12, padding: 14,
  },
  typeCardDim: { opacity: 0.65 },
  typeTop: { flexDirection: "row", gap: 10 },
  typeName: { fontSize: 16, fontWeight: "700", color: "#111" },
  typeMeta: { fontSize: 12, color: "#6b7280", marginTop: 3 },
  typeDesc: { fontSize: 12, color: "#374151", marginTop: 4 },
  inactiveBadge: {
    backgroundColor: "#f3f4f6", paddingHorizontal: 7, paddingVertical: 2, borderRadius: 10,
  },
  inactiveTxt: { fontSize: 10, color: "#9ca3af", fontWeight: "600" },
  typeBtns: { gap: 6 },
  editBtn: {
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8,
    borderWidth: 1, borderColor: "#e5e7eb", alignItems: "center",
  },
  editTxt: { fontSize: 12, color: "#374151", fontWeight: "600" },
  deleteBtn: {
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8,
    backgroundColor: "#fee2e2", alignItems: "center",
  },
  deleteTxt: { fontSize: 12, color: "#ef4444", fontWeight: "600" },
});

const cp_s = StyleSheet.create({
  card: {
    backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8,
    borderRadius: 12, padding: 14,
  },
  dim: { opacity: 0.6 },
  top: { flexDirection: "row", alignItems: "flex-start", marginBottom: 10 },
  customerName: { fontSize: 15, fontWeight: "700", color: "#111" },
  passName: { fontSize: 13, color: "#16a34a", fontWeight: "600", marginTop: 1 },
  meta: { fontSize: 12, color: "#9ca3af", marginTop: 2 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  statusTxt: { fontSize: 12, fontWeight: "700" },
  progressWrap: { gap: 4, marginBottom: 10 },
  track: { height: 6, backgroundColor: "#f3f4f6", borderRadius: 3, overflow: "hidden" },
  fill: { height: "100%", backgroundColor: "#16a34a", borderRadius: 3 },
  progressTxt: { fontSize: 11, color: "#6b7280", textAlign: "right" },
  actions: { flexDirection: "row", gap: 8 },
  useBtn: {
    flex: 1, backgroundColor: "#16a34a", paddingVertical: 9,
    borderRadius: 8, alignItems: "center",
  },
  useTxt: { color: "#fff", fontSize: 13, fontWeight: "700" },
  cancelBtn: {
    paddingHorizontal: 14, paddingVertical: 9, borderRadius: 8,
    backgroundColor: "#f3f4f6", alignItems: "center",
  },
  cancelTxt: { color: "#6b7280", fontSize: 13, fontWeight: "600" },
});

const fm = StyleSheet.create({
  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 16, paddingTop: 20, paddingBottom: 14,
    backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#f3f4f6",
  },
  title: { fontSize: 17, fontWeight: "700", color: "#111" },
  cancelBtn: { padding: 4 },
  cancelTxt: { fontSize: 15, color: "#6b7280" },
  saveBtn: { padding: 4 },
  saveTxt: { fontSize: 15, color: "#16a34a", fontWeight: "700" },
  label: { fontSize: 13, fontWeight: "600", color: "#374151" },
  input: {
    backgroundColor: "#fff", borderWidth: 1, borderColor: "#e5e7eb",
    borderRadius: 10, padding: 12, fontSize: 15, color: "#111",
  },
  switchRow: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "center", backgroundColor: "#fff",
    borderRadius: 10, padding: 14,
  },
  switchLabel: { fontSize: 15, color: "#111" },
});

const am = StyleSheet.create({
  selectedBadge: {
    backgroundColor: "#f0fdf4", borderRadius: 8, padding: 10,
    marginBottom: 8,
  },
  selectedTxt: { fontSize: 14, fontWeight: "600", color: "#16a34a" },
});
