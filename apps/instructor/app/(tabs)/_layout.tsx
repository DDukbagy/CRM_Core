import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Pressable } from "react-native";
import { useCustomerRegister } from "@/lib/customerRegisterContext";

export default function TabsLayout() {
  const { openModal } = useCustomerRegister();

  return (
    <Tabs screenOptions={{ headerTitleAlign: "center", tabBarActiveTintColor: "#16a34a", tabBarStyle: { height: 72, paddingBottom: 12 } }}>
      <Tabs.Screen
        name="index"
        options={{ title: "대시보드", tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" size={size} color={color} /> }}
      />
      <Tabs.Screen
        name="customers"
        options={{
          title: "고객 관리",
          tabBarIcon: ({ color, size }) => <Ionicons name="people-outline" size={size} color={color} />,
          headerRight: () => (
            <Pressable onPress={openModal} style={{ marginRight: 16 }}>
              <Ionicons name="person-add-outline" size={24} color="#16a34a" />
            </Pressable>
          ),
        }}
      />
      <Tabs.Screen
        name="schedule"
        options={{ title: "스케줄", tabBarIcon: ({ color, size }) => <Ionicons name="calendar-outline" size={size} color={color} /> }}
      />
      <Tabs.Screen
        name="chat"
        options={{ title: "채팅", tabBarIcon: ({ color, size }) => <Ionicons name="chatbubble-outline" size={size} color={color} /> }}
      />
      <Tabs.Screen
        name="posts"
        options={{ title: "글쓰기", tabBarIcon: ({ color, size }) => <Ionicons name="create-outline" size={size} color={color} /> }}
      />
      <Tabs.Screen
        name="revenue"
        options={{ title: "매출", tabBarIcon: ({ color, size }) => <Ionicons name="bar-chart-outline" size={size} color={color} /> }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: "내 정보", tabBarIcon: ({ color, size }) => <Ionicons name="person-outline" size={size} color={color} /> }}
      />
    </Tabs>
  );
}
