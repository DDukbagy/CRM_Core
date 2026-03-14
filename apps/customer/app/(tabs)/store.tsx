import { View, Text, StyleSheet } from "react-native";

export default function StoreScreen() {
  return (
    <View style={s.container}>
      <Text style={s.icon}>🛍️</Text>
      <Text style={s.title}>스토어</Text>
      <Text style={s.sub}>준비 중입니다</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#f9fafb", gap: 10 },
  icon: { fontSize: 52 },
  title: { fontSize: 20, fontWeight: "700", color: "#111" },
  sub: { fontSize: 14, color: "#9ca3af" },
});
