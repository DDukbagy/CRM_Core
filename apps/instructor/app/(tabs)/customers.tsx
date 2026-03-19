import { useEffect, useState, useCallback } from "react";
import {
  View, Text, ScrollView, Pressable, TextInput,
  RefreshControl, StyleSheet, Modal, ActivityIndicator, Alert,
} from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { apiFetch } from "@/lib/api";
import { useCustomerRegister } from "@/lib/customerRegisterContext";
import type { UsersListResponse, UserRead } from "@/types/api";

export default function CustomersScreen() {
  const [customers, setCustomers] = useState<UserRead[]>([]);
  const [search, setSearch] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  // 고객 등록 모달
  const { isOpen, close } = useCustomerRegister();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await apiFetch<UsersListResponse>("/users?limit=100");
      setCustomers(res.items.filter(u => u.role === "CUSTOMER"));
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const filtered = customers.filter(c =>
    c.display_name.includes(search) ||
    (c.phone ?? "").includes(search) ||
    (c.email ?? "").includes(search)
  );

  const handleClose = () => { setEmail(""); setErrorMsg(""); close(); };

  const handleRegister = async () => {
    const trimmed = email.trim();
    if (!trimmed) { setErrorMsg("이메일을 입력해주세요."); return; }

    const alreadyMine = customers.some(c => c.email?.toLowerCase() === trimmed.toLowerCase());
    if (alreadyMine) {
      setErrorMsg("이미 담당 고객으로 등록되어 있습니다.");
      return;
    }

    setLoading(true);
    setErrorMsg("");
    try {
      const customer = await apiFetch<UserRead>("/users/me/customers", {
        method: "POST",
        body: { email: trimmed },
      });
      await load();
      handleClose();
      Alert.alert("등록 완료", `${customer.display_name}님이 담당 고객으로 등록되었습니다.`);
    } catch (e: any) {
      if (e?.status === 404) {
        setErrorMsg("해당 고객을 찾을 수 없습니다.");
      } else {
        const detail = (e?.body as any)?.detail ?? e?.message ?? "오류가 발생했습니다.";
        setErrorMsg(detail);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={s.container}>
      <TextInput
        value={search} onChangeText={setSearch}
        placeholder="이름 / 전화번호 / 이메일 검색"
        style={s.searchInput}
      />
      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
        {filtered.length === 0 ? (
          <View style={s.empty}><Text style={s.emptyText}>담당 고객이 없습니다.</Text></View>
        ) : filtered.map(c => (
          <Pressable key={c.id} style={s.card} onPress={() => router.push(`/customer/${c.id}` as never)}>
            <View style={s.avatar}>
              <Text style={s.avatarText}>{c.display_name.charAt(0)}</Text>
            </View>
            <View style={s.info}>
              <Text style={s.name}>{c.display_name}</Text>
              {c.phone && <Text style={s.detail}>{c.phone}</Text>}
              {c.email && <Text style={s.detail}>{c.email}</Text>}
              {c.lesson_purpose && <Text style={s.purpose} numberOfLines={1}>{c.lesson_purpose}</Text>}
            </View>
            <Text style={s.arrow}>›</Text>
          </Pressable>
        ))}
      </ScrollView>

      {/* 고객 등록 모달 */}
      <Modal visible={isOpen} transparent animationType="fade" onRequestClose={handleClose}>
        <Pressable style={s.overlay} onPress={handleClose}>
          <Pressable style={s.sheet} onPress={() => {}}>
            <View style={s.sheetHeader}>
              <Text style={s.sheetTitle}>고객 등록</Text>
              <Pressable onPress={handleClose}>
                <Ionicons name="close" size={22} color="#6b7280" />
              </Pressable>
            </View>

            <Text style={s.label}>고객 이메일</Text>
            <TextInput
              style={s.input}
              placeholder="customer@example.com"
              value={email}
              onChangeText={t => { setEmail(t); setErrorMsg(""); }}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              editable={!loading}
            />

            {errorMsg ? <Text style={s.error}>{errorMsg}</Text> : null}

            <Pressable
              style={[s.btn, loading && s.btnDisabled]}
              onPress={handleRegister}
              disabled={loading}
            >
              {loading
                ? <ActivityIndicator color="#fff" size="small" />
                : <Text style={s.btnText}>등록</Text>
              }
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  searchInput: { margin: 16, padding: 12, backgroundColor: "#fff", borderRadius: 10, borderWidth: 1, borderColor: "#e5e7eb", fontSize: 15 },
  empty: { padding: 40, alignItems: "center" },
  emptyText: { color: "#9ca3af" },
  card: { backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8, borderRadius: 12, padding: 14, flexDirection: "row", alignItems: "center", gap: 12, elevation: 1 },
  avatar: { width: 44, height: 44, borderRadius: 22, backgroundColor: "#d1fae5", alignItems: "center", justifyContent: "center" },
  avatarText: { fontSize: 18, fontWeight: "700", color: "#16a34a" },
  info: { flex: 1 },
  name: { fontSize: 16, fontWeight: "600", color: "#111" },
  detail: { fontSize: 13, color: "#6b7280", marginTop: 1 },
  purpose: { fontSize: 12, color: "#9ca3af", marginTop: 3 },
  arrow: { fontSize: 20, color: "#d1d5db" },
  // 모달
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", alignItems: "center" },
  sheet: { width: "88%", backgroundColor: "#fff", borderRadius: 16, padding: 24 },
  sheetHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 20 },
  sheetTitle: { fontSize: 18, fontWeight: "700", color: "#111" },
  label: { fontSize: 13, fontWeight: "600", color: "#374151", marginBottom: 6 },
  input: { borderWidth: 1, borderColor: "#d1d5db", borderRadius: 10, padding: 12, fontSize: 15, marginBottom: 8 },
  error: { fontSize: 13, color: "#ef4444", marginBottom: 8 },
  btn: { backgroundColor: "#16a34a", borderRadius: 10, padding: 14, alignItems: "center", marginTop: 4 },
  btnDisabled: { opacity: 0.6 },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 15 },
});
