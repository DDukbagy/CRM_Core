// app/booking/[id].tsx
import { useEffect, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  Alert,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import { apiFetch } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { config } from "@/lib/config";
import type { BookingRead } from "@/types/api";

const statusLabel: Record<string, string> = {
  REQUESTED: "신청됨",
  CONFIRMED: "확정",
  CANCELLED: "취소됨",
  COMPLETED: "완료",
};

const statusColor: Record<string, string> = {
  REQUESTED: "#f59e0b",
  CONFIRMED: "#10b981",
  CANCELLED: "#ef4444",
  COMPLETED: "#6b7280",
};

export default function BookingDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [booking, setBooking] = useState<BookingRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    apiFetch<BookingRead[]>("/bookings/me")
      .then((list) => {
        const found = (Array.isArray(list) ? list : []).find((b) => String(b.id) === id);
        setBooking(found ?? null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  async function handleCancel() {
    Alert.alert("예약 취소", "확정된 예약을 취소하시겠습니까?", [
      { text: "아니오", style: "cancel" },
      {
        text: "취소",
        style: "destructive",
        onPress: async () => {
          try {
            await apiFetch(`/bookings/${id}/cancel`, { method: "PATCH" });
            Alert.alert("완료", "예약이 취소되었습니다.");
            router.back();
          } catch (e: any) {
            Alert.alert("오류", e?.message ?? "취소 실패");
          }
        },
      },
    ]);
  }

  async function handleWithdraw() {
    Alert.alert("신청 철회", "예약 신청을 철회하시겠습니까?", [
      { text: "아니오", style: "cancel" },
      {
        text: "철회",
        style: "destructive",
        onPress: async () => {
          try {
            await apiFetch(`/bookings/${id}/withdraw`, { method: "PATCH" });
            Alert.alert("완료", "신청이 철회되었습니다.");
            router.back();
          } catch (e: any) {
            Alert.alert("오류", e?.message ?? "철회 실패");
          }
        },
      },
    ]);
  }

  async function handleDownloadIcs() {
    setDownloading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("로그인이 필요합니다");

      const url = `${config.apiBaseUrl}/bookings/${id}/download`;
      const dest = `${FileSystem.cacheDirectory}booking_${id}.ics`;

      const result = await FileSystem.downloadAsync(url, dest, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      if (result.status !== 200) throw new Error("다운로드 실패");

      const canShare = await Sharing.isAvailableAsync();
      if (!canShare) {
        Alert.alert("알림", "이 기기에서는 공유가 지원되지 않습니다.");
        return;
      }

      await Sharing.shareAsync(result.uri, {
        mimeType: "text/calendar",
        dialogTitle: "캘린더에 추가",
        UTI: "public.calendar-event",
      });
    } catch (e: any) {
      Alert.alert("오류", e?.message ?? "캘린더 다운로드 실패");
    } finally {
      setDownloading(false);
    }
  }

  if (loading) {
    return <View style={s.center}><ActivityIndicator size="large" /></View>;
  }

  if (!booking) {
    return (
      <View style={s.center}>
        <Text style={{ color: "#6b7280" }}>예약을 찾을 수 없습니다.</Text>
      </View>
    );
  }

  return (
    <ScrollView style={s.container}>
      {/* 상태 배너 */}
      <View style={[s.banner, { backgroundColor: statusColor[booking.status] ?? "#6b7280" }]}>
        <Text style={s.bannerStatus}>{statusLabel[booking.status]}</Text>
        <Text style={s.bannerDate}>{booking.when}</Text>
      </View>

      {/* 상세 정보 */}
      <View style={s.card}>
        {booking.topic ? <DetailRow label="주제" value={booking.topic} /> : null}
        <DetailRow label="종류" value={booking.type === "LESSON" ? "레슨" : "상담"} />
        <DetailRow label="날짜" value={booking.when} />
        {booking.description ? <DetailRow label="메모" value={booking.description} /> : null}
        {booking.cancel_reason ? (
          <DetailRow label="취소 사유" value={booking.cancel_reason} valueColor="#ef4444" />
        ) : null}
        <DetailRow label="예약 번호" value={`#${booking.id}`} />
        <DetailRow label="신청일" value={booking.created_at.slice(0, 10)} />
      </View>

      {/* 액션 버튼 */}
      <View style={s.actions}>
        {(booking.status === "CONFIRMED" || booking.status === "COMPLETED") && (
          <Pressable
            style={[s.btn, s.calBtn, downloading && { opacity: 0.6 }]}
            onPress={handleDownloadIcs}
            disabled={downloading}
          >
            <Text style={s.calBtnText}>
              {downloading ? "저장 중..." : "📅 캘린더에 추가"}
            </Text>
          </Pressable>
        )}

        {booking.status === "CONFIRMED" && (
          <Pressable style={[s.btn, s.cancelBtn]} onPress={handleCancel}>
            <Text style={s.cancelBtnText}>예약 취소</Text>
          </Pressable>
        )}

        {booking.status === "REQUESTED" && (
          <Pressable style={[s.btn, s.withdrawBtn]} onPress={handleWithdraw}>
            <Text style={s.withdrawBtnText}>신청 철회</Text>
          </Pressable>
        )}
      </View>
    </ScrollView>
  );
}

function DetailRow({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <View style={s.row}>
      <Text style={s.rowLabel}>{label}</Text>
      <Text style={[s.rowValue, valueColor ? { color: valueColor } : null]}>{value}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  banner: { padding: 24, alignItems: "center" },
  bannerStatus: { color: "#fff", fontSize: 18, fontWeight: "700" },
  bannerDate: { color: "rgba(255,255,255,0.85)", fontSize: 14, marginTop: 4 },
  card: { margin: 16, backgroundColor: "#fff", borderRadius: 12, overflow: "hidden", elevation: 2 },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#f3f4f6",
  },
  rowLabel: { fontSize: 14, color: "#6b7280" },
  rowValue: { fontSize: 14, color: "#111", fontWeight: "500", maxWidth: "60%", textAlign: "right" },
  actions: { marginHorizontal: 16, gap: 10 },
  btn: { padding: 14, borderRadius: 12 },
  calBtn: { backgroundColor: "#eff6ff", borderWidth: 1, borderColor: "#bfdbfe" },
  calBtnText: { color: "#1d4ed8", textAlign: "center", fontWeight: "600", fontSize: 15 },
  cancelBtn: { backgroundColor: "#fee2e2" },
  cancelBtnText: { color: "#ef4444", textAlign: "center", fontWeight: "600", fontSize: 15 },
  withdrawBtn: { backgroundColor: "#fef3c7" },
  withdrawBtnText: { color: "#d97706", textAlign: "center", fontWeight: "600", fontSize: 15 },
});
