// app/(auth)/login.tsx
import { useState } from "react";
import { View, Text, TextInput, Pressable, Alert } from "react-native";
import { useRouter } from "expo-router";
import { setAccessToken } from "@/lib/api";
import { config } from "@/lib/config";

export default function LoginScreen() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onLogin() {
    if (!email || !password) {
      Alert.alert("확인", "이메일/비밀번호를 입력해줘.");
      return;
    }

    setLoading(true);
    try {
      // FastAPI OAuth2PasswordRequestForm 스타일이면 form-encoded가 필요함
      const body = new URLSearchParams();
      body.append("username", email);
      body.append("password", password);

      const res = await fetch(`${config.apiBaseUrl}/users/login/access-token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail ?? `Login failed (${res.status})`);
      }

      // 보통 { access_token, token_type }
      await setAccessToken(data.access_token);
      router.replace("/(tabs)");
    } catch (e: any) {
      Alert.alert("로그인 실패", e?.message ?? "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={{ flex: 1, padding: 20, justifyContent: "center", gap: 12 }}>
      <Text style={{ fontSize: 22, fontWeight: "700" }}>CRM 고객앱 로그인</Text>

      <TextInput
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        placeholder="email"
        style={{ borderWidth: 1, borderColor: "#ddd", padding: 12, borderRadius: 10 }}
      />

      <TextInput
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        placeholder="password"
        style={{ borderWidth: 1, borderColor: "#ddd", padding: 12, borderRadius: 10 }}
      />

      <Pressable
        onPress={onLogin}
        disabled={loading}
        style={{
          backgroundColor: "#111",
          padding: 12,
          borderRadius: 10,
          opacity: loading ? 0.6 : 1,
        }}
      >
        <Text style={{ color: "#fff", textAlign: "center", fontWeight: "600" }}>
          {loading ? "로그인 중..." : "로그인"}
        </Text>
      </Pressable>
    </View>
  );
}