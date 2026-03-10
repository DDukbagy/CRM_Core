import { useEffect, useState, useCallback } from "react";
import { View, Text, ScrollView, Pressable, TextInput, RefreshControl, StyleSheet } from "react-native";
import { router } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UsersListResponse, UserRead } from "@/types/api";

export default function CustomersScreen() {
  const [customers, setCustomers] = useState<UserRead[]>([]);
  const [search, setSearch] = useState("");
  const [refreshing, setRefreshing] = useState(false);

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
});
