// app/(auth)/login.tsx
import { useEffect, useState } from "react";
import { View, Text, TextInput, Pressable } from "react-native";
import { router } from "expo-router";
import { supabase } from "@/lib/supabase";
import { apiFetch } from "@/lib/api";
import type { UserRead } from "@/types/api";

// 네비게이션 이후에도 메시지를 유지하기 위한 모듈 변수
let pendingError: string | null = null;
let pendingWarning: string | null = null; // 역할 불일치 경고

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [warningMsg, setWarningMsg] = useState<string | null>(null);

  useEffect(() => {
    if (pendingWarning) {
      setWarningMsg(pendingWarning);
      pendingWarning = null;
    } else if (pendingError) {
      setErrorMsg(pendingError);
      pendingError = null;
    }
  }, []);

  async function onLogin() {
    if (!email || !password) {
      setErrorMsg("이메일/비밀번호를 입력해주세요.");
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setWarningMsg(null);
    let signedIn = false;
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      signedIn = true;

      // 역할 확인 - CUSTOMER가 아니면 로그아웃
      const me = await apiFetch<UserRead>("/users/me");
      if (me.role !== "CUSTOMER") {
        pendingWarning = "고객 전용 앱입니다.\n강사·관리자 계정은 웹 관리자 페이지를 이용해 주세요.";
        await supabase.auth.signOut();
        return;
      }

      router.replace("/(tabs)");
    } catch (e: any) {
      if (signedIn) {
        // signIn은 성공했지만 API 오류 → 보안상 로그아웃
        const isNetworkError =
          e?.message === "Failed to fetch" ||
          e?.message?.includes("Network request failed") ||
          e?.message?.includes("fetch");
        pendingError = isNetworkError
          ? "서버에 연결할 수 없습니다.\nAPI URL 설정을 확인하거나 잠시 후 다시 시도해 주세요."
          : (e?.message ?? "로그인 처리 중 오류가 발생했습니다.");
        await supabase.auth.signOut();
      } else {
        // signIn 자체 실패 (잘못된 이메일/비밀번호 등)
        const msg = e?.message ?? "";
        setErrorMsg(
          msg.includes("Invalid login credentials")
            ? "이메일 또는 비밀번호가 올바르지 않습니다."
            : msg || "알 수 없는 오류가 발생했습니다."
        );
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center", gap: 16 }}>
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 8 }}>
        골프 CRM
      </Text>
      <Text style={{ fontSize: 14, color: "#666", marginBottom: 16 }}>
        고객용 앱에 로그인하세요
      </Text>

      <TextInput
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        placeholder="이메일"
        style={{
          borderWidth: 1,
          borderColor: "#ddd",
          padding: 14,
          borderRadius: 10,
          fontSize: 16,
        }}
      />

      <TextInput
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        placeholder="비밀번호"
        style={{
          borderWidth: 1,
          borderColor: "#ddd",
          padding: 14,
          borderRadius: 10,
          fontSize: 16,
        }}
      />

      {/* 역할 불일치 경고 (주황) */}
      {warningMsg && (
        <View
          style={{
            backgroundColor: "#fffbeb",
            borderWidth: 1,
            borderColor: "#fcd34d",
            borderRadius: 8,
            padding: 14,
          }}
        >
          <Text style={{ color: "#92400e", fontSize: 14, fontWeight: "700", marginBottom: 2 }}>
            접근 불가
          </Text>
          <Text style={{ color: "#92400e", fontSize: 13, lineHeight: 20 }}>
            {warningMsg}
          </Text>
        </View>
      )}

      {/* 일반 오류 (빨강) */}
      {errorMsg && (
        <View
          style={{
            backgroundColor: "#fff0f0",
            borderWidth: 1,
            borderColor: "#ffcccc",
            borderRadius: 8,
            padding: 12,
          }}
        >
          <Text style={{ color: "#cc0000", fontSize: 14, lineHeight: 20 }}>
            {errorMsg}
          </Text>
        </View>
      )}

      <Pressable
        onPress={onLogin}
        disabled={loading}
        style={{
          backgroundColor: "#1a1a1a",
          padding: 14,
          borderRadius: 10,
          marginTop: 8,
          opacity: loading ? 0.6 : 1,
        }}
      >
        <Text style={{ color: "#fff", textAlign: "center", fontWeight: "600", fontSize: 16 }}>
          {loading ? "로그인 중..." : "로그인"}
        </Text>
      </Pressable>
    </View>
  );
}
