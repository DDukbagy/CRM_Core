import { useEffect, useState } from "react";
import { SafeAreaView, Text, View, Pressable, ScrollView } from "react-native";

const BASE = process.env.EXPO_PUBLIC_API_BASE_URL;

async function pingOpenApi() {
  if (!BASE) throw new Error("EXPO_PUBLIC_API_BASE_URL is missing (.env 확인)");
  const res = await fetch(`${BASE}/openapi.json`);
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`);
  return text;
}

export default function HomeScreen() {
  const [status, setStatus] = useState("Connecting...");
  const [detail, setDetail] = useState<string>("");

  const run = async () => {
    setStatus("Connecting...");
    setDetail("");
    try {
      const text = await pingOpenApi();
      setStatus("✅ Backend connected (/openapi.json OK)");
      setDetail(text.slice(0, 800)); // 너무 길어서 앞부분만
    } catch (e: any) {
      setStatus("❌ Backend connection failed");
      setDetail(String(e?.message ?? e));
    }
  };

  useEffect(() => {
    run();
  }, []);

  return (
    <SafeAreaView style={{ flex: 1, padding: 16 }}>
      <View style={{ gap: 12 }}>
        <Text style={{ fontSize: 20, fontWeight: "600" }}>{status}</Text>

        <Pressable
          onPress={run}
          style={{
            paddingVertical: 12,
            paddingHorizontal: 14,
            borderWidth: 1,
            borderRadius: 10,
            alignSelf: "flex-start",
          }}
        >
          <Text>Retry</Text>
        </Pressable>

        <ScrollView style={{ borderWidth: 1, borderRadius: 10, padding: 12 }}>
          <Text selectable style={{ fontSize: 12 }}>
            BASE: {BASE ?? "(missing)"} {"\n\n"}
            {detail}
          </Text>
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}