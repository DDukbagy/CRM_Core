// app/(tabs)/bookings.tsx
import { View, Text } from "react-native";

export default function BookingsScreen() {
  return (
    <View style={{ flex: 1, padding: 20 }}>
      <Text style={{ fontSize: 18, fontWeight: "700" }}>예약</Text>
      <Text>예약 리스트/취소/상세 UI 들어갈 자리</Text>
    </View>
  );
}