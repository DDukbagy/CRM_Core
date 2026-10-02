import { useEffect, useState } from "react";
import { View, Text, ScrollView, Pressable, TextInput, Alert, StyleSheet, ActivityIndicator, Platform } from "react-native";
import { useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { apiFetch } from "@/lib/api";
import type { UserRead } from "@/types/api";

// 0=월,1=화,...,6=일 (Python weekday 기준)
const WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];

export default function ProfileScreen() {
  const router = useRouter();
  const [me, setMe] = useState<UserRead | null>(null);
  const [editing, setEditing] = useState(false);
  const [offDaysSaving, setOffDaysSaving] = useState(false);
  // 정기 휴무 요일: "수정"을 눌러야 요일 버튼이 켜지고, "저장"을 눌러야 반영 (실수로 바로 바뀌지 않게)
  const [offDaysEditing, setOffDaysEditing] = useState(false);
  const [offDaysDraft, setOffDaysDraft] = useState<number[]>([]);
  const [form, setForm] = useState({
    display_name: "", phone: "", instructor_location: "",
    instructor_specialties: "", instructor_bio: "",
    career_years: "", certifications: "",
  });

  useEffect(() => {
    apiFetch<UserRead>("/users/me").then(u => {
      setMe(u);
      setForm({
        display_name: u.display_name ?? "",
        phone: u.phone ?? "",
        instructor_location: u.instructor_location ?? "",
        instructor_specialties: u.instructor_specialties ?? "",
        instructor_bio: u.instructor_bio ?? "",
        career_years: u.career_years?.toString() ?? "",
        certifications: u.certifications ?? "",
      });
    }).catch(() => {});
  }, []);

  async function save() {
    try {
      const body: Record<string, unknown> = {
        display_name: form.display_name || undefined,
        phone: form.phone || undefined,
        instructor_location: form.instructor_location || undefined,
        instructor_specialties: form.instructor_specialties || undefined,
        instructor_bio: form.instructor_bio || undefined,
        career_years: form.career_years ? parseInt(form.career_years) : undefined,
        certifications: form.certifications || undefined,
      };
      const updated = await apiFetch<UserRead>("/users/me", { method: "PATCH", body });
      setMe(updated);
      setEditing(false);
      Alert.alert("저장됨", "프로필이 저장됐습니다.");
    } catch (e: unknown) {
      Alert.alert("오류", e instanceof Error ? e.message : "저장 실패");
    }
  }

  if (!me) return <View style={s.center}><Text>불러오는 중...</Text></View>;

  const tierLabel = me.instructor_tier === "NAMED" ? "네임드 강사" : "일반 강사";

  // 회원 탈퇴: 개인정보는 지우고 결제·계약 기록은 법정 보존 기간(5년) 동안 남는다 (백엔드 POST /users/me/withdraw)
  async function handleWithdraw() {
    const title = "회원 탈퇴";
    const message =
      "탈퇴하면 이름·연락처 등 계정 정보가 삭제되고 다시 로그인할 수 없습니다.\n" +
      "결제·멤버십·수강권 기록은 관련 법(전자상거래법)에 따라 5년간 보관됩니다.";
    const doWithdraw = async () => {
      try {
        await apiFetch("/users/me/withdraw", { method: "POST" });
      } catch (e) {
        const msg = e instanceof Error ? e.message : "탈퇴 처리에 실패했습니다.";
        if (Platform.OS === "web") window.alert(msg); else Alert.alert("오류", msg);
        return;
      }
      await supabase.auth.signOut();
    };
    if (Platform.OS === "web") {
      if (!window.confirm(`${title}\n\n${message}`)) return;
      await doWithdraw();
    } else {
      Alert.alert(title, message, [
        { text: "취소", style: "cancel" },
        { text: "탈퇴", style: "destructive", onPress: doWithdraw },
      ]);
    }
  }

  return (
    <ScrollView style={s.container}>
      {/* 헤더 */}
      <View style={s.header}>
        <View style={s.avatar}>
          <Text style={s.avatarText}>{me.display_name.charAt(0)}</Text>
        </View>
        <Text style={s.name}>{me.display_name}</Text>
        <View style={[s.tierBadge, me.instructor_tier === "NAMED" && s.namedBadge]}>
          <Text style={[s.tierText, me.instructor_tier === "NAMED" && s.namedText]}>{tierLabel}</Text>
        </View>
      </View>

      {/* 기본 정보 */}
      <View style={s.card}>
        <Text style={s.cardTitle}>계정 정보</Text>
        <Row label="이메일" value={me.email ?? "-"} />
        <Row label="아이디" value={me.username} />
        <Row label="상태" value={me.status} />
      </View>

      {/* 강사 프로필 (편집) */}
      <View style={s.card}>
        <View style={s.cardHeaderRow}>
          <Text style={s.cardTitle}>강사 프로필</Text>
          <Pressable onPress={() => editing ? save() : setEditing(true)} style={s.editBtn}>
            <Text style={s.editBtnText}>{editing ? "저장" : "수정"}</Text>
          </Pressable>
        </View>

        {editing ? (
          <>
            <Field label="이름" value={form.display_name} onChange={v => setForm(f => ({ ...f, display_name: v }))} />
            <Field label="전화번호" value={form.phone} onChange={v => setForm(f => ({ ...f, phone: v }))} keyboardType="phone-pad" />
            <Field label="활동 지역" value={form.instructor_location} onChange={v => setForm(f => ({ ...f, instructor_location: v }))} placeholder="예: 서울 강남" />
            <Field label="전문 분야" value={form.instructor_specialties} onChange={v => setForm(f => ({ ...f, instructor_specialties: v }))} placeholder="예: 드라이버,퍼팅 (콤마 구분)" />
            <Field label="경력 (년)" value={form.career_years} onChange={v => setForm(f => ({ ...f, career_years: v }))} keyboardType="numeric" />
            <Field label="자격증" value={form.certifications} onChange={v => setForm(f => ({ ...f, certifications: v }))} />
            <Field label="소개글" value={form.instructor_bio} onChange={v => setForm(f => ({ ...f, instructor_bio: v }))} multiline />
            <Pressable onPress={() => setEditing(false)} style={s.cancelBtn}>
              <Text style={s.cancelText}>취소</Text>
            </Pressable>
          </>
        ) : (
          <>
            <Row label="전화번호" value={me.phone ?? "-"} />
            <Row label="활동 지역" value={me.instructor_location ?? "-"} />
            <Row label="전문 분야" value={me.instructor_specialties ?? "-"} />
            <Row label="경력" value={me.career_years ? `${me.career_years}년` : "-"} />
            <Row label="자격증" value={me.certifications ?? "-"} />
            {me.instructor_bio && <Text style={s.bio}>{me.instructor_bio}</Text>}
          </>
        )}
      </View>

      {/* 정기 휴무 요일 */}
      <View style={s.card}>
        <View style={s.cardHeaderRow}>
          <Text style={s.cardTitle}>정기 휴무 요일</Text>
          <Pressable
            disabled={offDaysSaving}
            onPress={async () => {
              if (!offDaysEditing) {
                setOffDaysDraft(me.recurring_off_days ?? []);
                setOffDaysEditing(true);
                return;
              }
              setOffDaysSaving(true);
              try {
                const updated = await apiFetch<UserRead>("/users/me", {
                  method: "PATCH", body: { recurring_off_days: [...offDaysDraft].sort() },
                });
                setMe(updated);
                setOffDaysEditing(false);
              } catch (e: unknown) {
                const msg = e instanceof Error ? e.message : "저장 실패";
                if (Platform.OS === "web") window.alert(msg); else Alert.alert("오류", msg);
              } finally {
                setOffDaysSaving(false);
              }
            }}
            style={s.editBtn}
          >
            <Text style={s.editBtnText}>{offDaysEditing ? "저장" : "수정"}</Text>
          </Pressable>
        </View>
        <Text style={s.offDayDesc}>레슨 없는 요일을 선택하면 고객 예약이 차단됩니다</Text>
        <View style={s.weekdayRow}>
          {WEEKDAY_LABELS.map((label, idx) => {
            const days = offDaysEditing ? offDaysDraft : (me.recurring_off_days ?? []);
            const isOff = days.includes(idx);
            return (
              <Pressable
                key={idx}
                style={[s.weekdayBtn, isOff && s.weekdayBtnOff, !offDaysEditing && s.weekdayBtnLocked]}
                disabled={!offDaysEditing || offDaysSaving}
                onPress={() => setOffDaysDraft(d => (d.includes(idx) ? d.filter(x => x !== idx) : [...d, idx]))}
              >
                <Text style={[s.weekdayTxt, isOff && s.weekdayTxtOff]}>{label}</Text>
                {isOff && <Text style={s.weekdayOffLabel}>휴무</Text>}
              </Pressable>
            );
          })}
        </View>
        {offDaysEditing && (
          <Pressable onPress={() => setOffDaysEditing(false)} disabled={offDaysSaving} style={s.cancelBtn}>
            <Text style={s.cancelText}>취소</Text>
          </Pressable>
        )}
        {offDaysSaving && <ActivityIndicator size="small" color="#6b7280" style={{ marginTop: 8 }} />}
      </View>

      {/* 수강권 관리 */}
      <Pressable style={s.menuBtn} onPress={() => router.push("/passes" as any)}>
        <Text style={s.menuBtnTxt}>🎫  수강권 관리</Text>
        <Text style={s.menuBtnArrow}>→</Text>
      </Pressable>

      {/* 로그아웃 */}
      <Pressable style={s.logoutBtn} onPress={() => {
        const doLogout = async () => {
          try { await apiFetch("/users/me/push-token", { method: "DELETE" }); } catch {}
          await supabase.auth.signOut();
        };
        // 웹(react-native-web)은 Alert.alert 가 아무것도 띄우지 않으므로 브라우저 확인창 사용 (고객 앱과 같은 방식)
        if (Platform.OS === "web") {
          if (window.confirm("로그아웃 하시겠습니까?")) doLogout();
          return;
        }
        Alert.alert("로그아웃", "로그아웃 하시겠습니까?", [
          { text: "취소", style: "cancel" },
          { text: "로그아웃", style: "destructive", onPress: doLogout },
        ]);
      }}>
        <Text style={s.logoutText}>로그아웃</Text>
      </Pressable>

      {/* 회원 탈퇴 */}
      <Pressable style={s.withdrawBtn} onPress={handleWithdraw}>
        <Text style={s.withdrawText}>회원 탈퇴</Text>
      </Pressable>
    </ScrollView>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={s.row}>
      <Text style={s.rowLabel}>{label}</Text>
      <Text style={s.rowValue}>{value}</Text>
    </View>
  );
}

function Field({ label, value, onChange, placeholder, keyboardType, multiline }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; keyboardType?: "default" | "phone-pad" | "numeric"; multiline?: boolean;
}) {
  return (
    <View style={s.field}>
      <Text style={s.fieldLabel}>{label}</Text>
      <TextInput value={value} onChangeText={onChange} placeholder={placeholder} keyboardType={keyboardType ?? "default"}
        multiline={multiline} style={[s.fieldInput, multiline && { height: 80, textAlignVertical: "top" }]} />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { backgroundColor: "#fff", alignItems: "center", padding: 24, borderBottomWidth: 1, borderColor: "#e5e7eb" },
  avatar: { width: 64, height: 64, borderRadius: 32, backgroundColor: "#d1fae5", alignItems: "center", justifyContent: "center", marginBottom: 10 },
  avatarText: { fontSize: 28, fontWeight: "700", color: "#16a34a" },
  name: { fontSize: 20, fontWeight: "700", marginBottom: 6 },
  tierBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: "#f3f4f6" },
  namedBadge: { backgroundColor: "#fef3c7" },
  tierText: { fontSize: 12, color: "#6b7280", fontWeight: "600" },
  namedText: { color: "#92400e" },
  card: { backgroundColor: "#fff", margin: 16, marginBottom: 8, borderRadius: 12, padding: 16, elevation: 1 },
  cardHeaderRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  cardTitle: { fontSize: 15, fontWeight: "700", marginBottom: 10 },
  editBtn: { backgroundColor: "#f0fdf4", paddingHorizontal: 14, paddingVertical: 6, borderRadius: 8 },
  editBtnText: { color: "#16a34a", fontWeight: "600", fontSize: 13 },
  row: { flexDirection: "row", marginBottom: 8 },
  rowLabel: { width: 80, fontSize: 13, color: "#6b7280" },
  rowValue: { flex: 1, fontSize: 13, color: "#111" },
  bio: { fontSize: 13, color: "#374151", lineHeight: 20, marginTop: 8 },
  field: { marginBottom: 12 },
  fieldLabel: { fontSize: 12, color: "#6b7280", marginBottom: 4 },
  fieldInput: { borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 8, padding: 10, fontSize: 15 },
  cancelBtn: { marginTop: 8, padding: 10, alignItems: "center" },
  cancelText: { color: "#9ca3af", fontSize: 14 },
  menuBtn: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", margin: 16, marginBottom: 8, padding: 14, backgroundColor: "#fff", borderRadius: 10, borderWidth: 1, borderColor: "#e5e7eb" },
  menuBtnTxt: { fontSize: 15, fontWeight: "600", color: "#111" },
  menuBtnArrow: { fontSize: 15, color: "#9ca3af" },
  logoutBtn: { margin: 16, marginTop: 8, padding: 14, backgroundColor: "#fff", borderRadius: 10, alignItems: "center", borderWidth: 1, borderColor: "#fecaca" },
  logoutText: { color: "#dc2626", fontWeight: "600", fontSize: 15 },
  withdrawBtn: { marginHorizontal: 16, marginTop: 4, marginBottom: 24, padding: 10, alignItems: "center" },
  withdrawText: { color: "#9ca3af", fontSize: 13, textDecorationLine: "underline" },
  offDayDesc: { fontSize: 12, color: "#9ca3af", marginBottom: 12, marginTop: -4 },
  weekdayRow: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  weekdayBtn: { width: 40, height: 52, borderRadius: 10, backgroundColor: "#f0fdf4", borderWidth: 1, borderColor: "#bbf7d0", alignItems: "center", justifyContent: "center" },
  weekdayBtnOff: { backgroundColor: "#fee2e2", borderColor: "#fca5a5" },
  weekdayBtnLocked: { opacity: 0.55 },  // 수정 전: 눌리지 않는 상태
  weekdayTxt: { fontSize: 14, fontWeight: "700", color: "#16a34a" },
  weekdayTxtOff: { color: "#dc2626" },
  weekdayOffLabel: { fontSize: 9, color: "#dc2626", fontWeight: "600", marginTop: 2 },
});
