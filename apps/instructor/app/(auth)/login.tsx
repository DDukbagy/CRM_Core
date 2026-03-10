import { useEffect, useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet } from "react-native";
import { router } from "expo-router";
import { supabase } from "@/lib/supabase";
import { apiFetch } from "@/lib/api";
import type { UserRead } from "@/types/api";

let pendingError: string | null = null;
let pendingWarning: string | null = null;

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [warningMsg, setWarningMsg] = useState<string | null>(null);

  useEffect(() => {
    if (pendingWarning) { setWarningMsg(pendingWarning); pendingWarning = null; }
    else if (pendingError) { setErrorMsg(pendingError); pendingError = null; }
  }, []);

  async function onLogin() {
    if (!email || !password) { setErrorMsg("이메일/비밀번호를 입력해주세요."); return; }
    setLoading(true); setErrorMsg(null); setWarningMsg(null);
    let signedIn = false;
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      signedIn = true;

      const me = await apiFetch<UserRead>("/users/me");
      if (me.role !== "INSTRUCTOR" && me.role !== "ADMIN") {
        pendingWarning = "강사 전용 앱입니다.\n고객은 고객용 앱을 이용해 주세요.";
        await supabase.auth.signOut();
        return;
      }

      router.replace("/(tabs)");
    } catch (e: unknown) {
      if (signedIn) {
        const msg = e instanceof Error ? e.message : "";
        const isNetwork = msg.includes("fetch") || msg.includes("Network");
        pendingError = isNetwork
          ? "서버에 연결할 수 없습니다.\nAPI URL 설정을 확인해주세요."
          : (msg || "로그인 처리 중 오류가 발생했습니다.");
        await supabase.auth.signOut();
      } else {
        const msg = e instanceof Error ? e.message : "";
        setErrorMsg(msg.includes("Invalid login credentials")
          ? "이메일 또는 비밀번호가 올바르지 않습니다."
          : msg || "알 수 없는 오류가 발생했습니다.");
      }
    } finally { setLoading(false); }
  }

  return (
    <View style={s.container}>
      <Text style={s.title}>골프 CRM</Text>
      <Text style={s.sub}>강사용 앱에 로그인하세요</Text>

      <TextInput value={email} onChangeText={setEmail} autoCapitalize="none"
        keyboardType="email-address" placeholder="이메일" style={s.input} />
      <TextInput value={password} onChangeText={setPassword} secureTextEntry
        placeholder="비밀번호" style={s.input} />

      {warningMsg && (
        <View style={s.warnBox}>
          <Text style={s.warnTitle}>접근 불가</Text>
          <Text style={s.warnText}>{warningMsg}</Text>
        </View>
      )}
      {errorMsg && (
        <View style={s.errBox}>
          <Text style={s.errText}>{errorMsg}</Text>
        </View>
      )}

      <Pressable onPress={onLogin} disabled={loading} style={[s.btn, loading && { opacity: 0.6 }]}>
        <Text style={s.btnText}>{loading ? "로그인 중..." : "로그인"}</Text>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, padding: 24, justifyContent: "center", gap: 16 },
  title: { fontSize: 26, fontWeight: "700", marginBottom: 4 },
  sub: { fontSize: 14, color: "#666", marginBottom: 12 },
  input: { borderWidth: 1, borderColor: "#ddd", padding: 14, borderRadius: 10, fontSize: 16 },
  warnBox: { backgroundColor: "#fffbeb", borderWidth: 1, borderColor: "#fcd34d", borderRadius: 8, padding: 14 },
  warnTitle: { color: "#92400e", fontSize: 14, fontWeight: "700", marginBottom: 2 },
  warnText: { color: "#92400e", fontSize: 13, lineHeight: 20 },
  errBox: { backgroundColor: "#fff0f0", borderWidth: 1, borderColor: "#ffcccc", borderRadius: 8, padding: 12 },
  errText: { color: "#cc0000", fontSize: 14, lineHeight: 20 },
  btn: { backgroundColor: "#16a34a", padding: 14, borderRadius: 10, marginTop: 8 },
  btnText: { color: "#fff", textAlign: "center", fontWeight: "600", fontSize: 16 },
});
