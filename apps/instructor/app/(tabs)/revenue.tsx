import { useEffect, useState, useCallback } from "react";
import { View, Text, ScrollView, RefreshControl, Pressable, Alert, Modal, TextInput, StyleSheet } from "react-native";
import { apiFetch } from "@/lib/api";
import type { PaymentRead, InstructorStats } from "@/types/api";

const METHODS = ["CASH", "TRANSFER", "TOSS", "KAKAO", "NAVER"];
const METHOD_LABEL: Record<string, string> = { CASH: "현금", TRANSFER: "계좌이체", TOSS: "토스", KAKAO: "카카오페이", NAVER: "네이버페이" };

export default function RevenueScreen() {
  const [stats, setStats] = useState<InstructorStats | null>(null);
  const [payments, setPayments] = useState<PaymentRead[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ customer_id: "", amount: "", method: "CASH", membership_id: "" });

  const load = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([
        apiFetch<InstructorStats>("/instructors/me/stats"),
        apiFetch<PaymentRead[]>("/payments"),
      ]);
      setStats(s);
      setPayments(p);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  async function recordPayment() {
    if (!form.customer_id || !form.amount) { Alert.alert("오류", "고객 ID와 금액을 입력해주세요."); return; }
    const amount = parseInt(form.amount);
    if (isNaN(amount) || amount <= 0) { Alert.alert("오류", "올바른 금액을 입력해주세요."); return; }
    try {
      const body: Record<string, unknown> = { customer_id: form.customer_id, amount, method: form.method };
      if (form.membership_id) body.membership_id = form.membership_id;
      await apiFetch("/payments", { method: "POST", body });
      setShowModal(false);
      setForm({ customer_id: "", amount: "", method: "CASH", membership_id: "" });
      await load();
    } catch (e: unknown) {
      Alert.alert("오류", e instanceof Error ? e.message : "등록 실패");
    }
  }

  const totalRevenue = payments.filter(p => p.status === "COMPLETED").reduce((sum, p) => sum + p.amount, 0);

  return (
    <View style={s.container}>
      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
        {/* 요약 */}
        {stats && (
          <View style={s.summaryCard}>
            <Text style={s.summaryLabel}>이번 달 총 매출 (완료)</Text>
            <Text style={s.summaryAmount}>{totalRevenue.toLocaleString()}원</Text>
            <Text style={s.summaryDetail}>결제 {payments.filter(p => p.status === "COMPLETED").length}건 · 담당 고객 {stats.customer_count}명</Text>
          </View>
        )}

        <View style={s.listHeader}>
          <Text style={s.listTitle}>결제 내역</Text>
          <Pressable style={s.addBtn} onPress={() => setShowModal(true)}>
            <Text style={s.addBtnText}>+ 수동 등록</Text>
          </Pressable>
        </View>

        {payments.length === 0
          ? <View style={s.empty}><Text style={s.emptyText}>결제 내역이 없습니다.</Text></View>
          : payments.map(p => (
            <View key={p.id} style={s.payCard}>
              <View style={s.payRow}>
                <Text style={s.payAmount}>{p.amount.toLocaleString()}원</Text>
                <View style={[s.statusBadge, p.status === "COMPLETED" ? s.statusOk : s.statusOther]}>
                  <Text style={s.statusText}>{p.status}</Text>
                </View>
              </View>
              <Text style={s.payMeta}>{METHOD_LABEL[p.method] ?? p.method} · {p.created_at.slice(0, 10)}</Text>
            </View>
          ))
        }
      </ScrollView>

      {/* 결제 등록 모달 */}
      <Modal visible={showModal} animationType="slide" presentationStyle="pageSheet">
        <View style={s.modal}>
          <View style={s.modalHeader}>
            <Text style={s.modalTitle}>결제 수동 등록</Text>
            <Pressable onPress={() => setShowModal(false)}><Text style={s.modalClose}>✕</Text></Pressable>
          </View>
          <ScrollView style={s.modalBody}>
            <Text style={s.label}>고객 ID (UUID)</Text>
            <TextInput value={form.customer_id} onChangeText={v => setForm(f => ({ ...f, customer_id: v }))}
              placeholder="고객 UUID 입력" style={s.input} autoCapitalize="none" />

            <Text style={s.label}>금액 (원)</Text>
            <TextInput value={form.amount} onChangeText={v => setForm(f => ({ ...f, amount: v }))}
              placeholder="100000" style={s.input} keyboardType="numeric" />

            <Text style={s.label}>결제 수단</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.methodRow}>
              {METHODS.map(m => (
                <Pressable key={m} onPress={() => setForm(f => ({ ...f, method: m }))}
                  style={[s.methodBtn, form.method === m && s.methodBtnSel]}>
                  <Text style={[s.methodText, form.method === m && s.methodTextSel]}>
                    {METHOD_LABEL[m]}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>

            <Text style={s.label}>수강권 ID (선택)</Text>
            <TextInput value={form.membership_id} onChangeText={v => setForm(f => ({ ...f, membership_id: v }))}
              placeholder="수강권 UUID (선택)" style={s.input} autoCapitalize="none" />

            <Pressable onPress={recordPayment} style={s.submitBtn}>
              <Text style={s.submitText}>등록</Text>
            </Pressable>
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  summaryCard: { backgroundColor: "#16a34a", margin: 16, borderRadius: 16, padding: 20 },
  summaryLabel: { color: "#bbf7d0", fontSize: 13 },
  summaryAmount: { color: "#fff", fontSize: 32, fontWeight: "700", marginVertical: 4 },
  summaryDetail: { color: "#bbf7d0", fontSize: 12 },
  listHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, paddingVertical: 10 },
  listTitle: { fontSize: 16, fontWeight: "600" },
  addBtn: { backgroundColor: "#f0fdf4", paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
  addBtnText: { color: "#16a34a", fontWeight: "600", fontSize: 13 },
  empty: { padding: 40, alignItems: "center" },
  emptyText: { color: "#9ca3af" },
  payCard: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8, borderRadius: 10, padding: 14, elevation: 1 },
  payRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  payAmount: { fontSize: 17, fontWeight: "700" },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  statusOk: { backgroundColor: "#d1fae5" },
  statusOther: { backgroundColor: "#f3f4f6" },
  statusText: { fontSize: 11, fontWeight: "600", color: "#374151" },
  payMeta: { fontSize: 12, color: "#9ca3af" },
  modal: { flex: 1, backgroundColor: "#fff" },
  modalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 20, borderBottomWidth: 1, borderColor: "#e5e7eb" },
  modalTitle: { fontSize: 18, fontWeight: "700" },
  modalClose: { fontSize: 20, color: "#6b7280" },
  modalBody: { padding: 20 },
  label: { fontSize: 13, fontWeight: "600", color: "#374151", marginBottom: 6, marginTop: 16 },
  input: { borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 8, padding: 12, fontSize: 15 },
  methodRow: { flexGrow: 0, marginBottom: 4 },
  methodBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: "#e5e7eb", marginRight: 8 },
  methodBtnSel: { borderColor: "#16a34a", backgroundColor: "#f0fdf4" },
  methodText: { fontSize: 13, color: "#6b7280" },
  methodTextSel: { color: "#16a34a", fontWeight: "600" },
  submitBtn: { backgroundColor: "#16a34a", padding: 14, borderRadius: 10, alignItems: "center", marginTop: 28, marginBottom: 40 },
  submitText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});
