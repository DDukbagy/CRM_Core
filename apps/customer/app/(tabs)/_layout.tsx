// app/(tabs)/_layout.tsx
import { Tabs, useRouter } from "expo-router";
import { useRef, useState } from "react";
import {
  View, Text, Pressable, Animated, StyleSheet, Dimensions,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import type { BottomTabBarProps } from "@react-navigation/bottom-tabs";

const SCREEN_W = Dimensions.get("window").width;
const DRAWER_W = Math.min(SCREEN_W * 0.72, 280);
const TAB_H = 58;
const CENTER_SIZE = 58;
const CENTER_LIFT = 18; // how much the center button floats above the bar top

type TabDef = {
  name: string;
  label: string;
  icon: string;
  activeIcon: string;
  center?: boolean;
};

const TABS: TabDef[] = [
  { name: "chat",     label: "채팅",   icon: "chatbubble-ellipses-outline", activeIcon: "chatbubble-ellipses" },
  { name: "store",    label: "스토어",  icon: "bag-outline",                 activeIcon: "bag"                 },
  { name: "index",    label: "홈",     icon: "home-outline",                activeIcon: "home",   center: true },
  { name: "schedule", label: "달력",   icon: "calendar-outline",            activeIcon: "calendar"            },
  { name: "posts",    label: "게시물", icon: "newspaper-outline",           activeIcon: "newspaper"           },
];

// ─── Custom Tab Bar ──────────────────────────────────────────────────────────
function CustomTabBar({ state, navigation }: BottomTabBarProps) {
  return (
    <View style={tb.container}>
      <View style={tb.bar}>
        {TABS.map((tab) => {
          const route = state.routes.find((r) => r.name === tab.name);
          const isFocused = route ? state.index === state.routes.indexOf(route) : false;
          const color = isFocused ? "#16a34a" : "#9ca3af";

          const onPress = () => {
            if (!route) return;
            const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
            if (!isFocused && !event.defaultPrevented) {
              navigation.navigate(tab.name as never);
            }
          };

          if (tab.center) {
            return (
              <View key={tab.name} style={tb.centerWrap}>
                <Pressable onPress={onPress} style={[tb.centerBtn, isFocused && tb.centerBtnActive]}>
                  <Ionicons
                    name={(isFocused ? tab.activeIcon : tab.icon) as any}
                    size={26}
                    color="#fff"
                  />
                </Pressable>
                <Text style={[tb.label, { color }]}>{tab.label}</Text>
              </View>
            );
          }

          return (
            <Pressable key={tab.name} onPress={onPress} style={tb.item}>
              <Ionicons
                name={(isFocused ? tab.activeIcon : tab.icon) as any}
                size={22}
                color={color}
              />
              <Text style={[tb.label, { color }]}>{tab.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

// ─── Layout ──────────────────────────────────────────────────────────────────
export default function TabsLayout() {
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerAnim = useRef(new Animated.Value(-DRAWER_W)).current;

  const openDrawer = () => {
    setDrawerOpen(true);
    Animated.timing(drawerAnim, { toValue: 0, duration: 240, useNativeDriver: true }).start();
  };

  const closeDrawer = () => {
    Animated.timing(drawerAnim, { toValue: -DRAWER_W, duration: 200, useNativeDriver: true })
      .start(() => setDrawerOpen(false));
  };

  const DRAWER_ITEMS = [
    { label: "강사 찾기", icon: "search-outline" as const,    route: "/(tabs)/match"   },
    { label: "수강권",    icon: "card-outline"   as const,    route: "/(tabs)/passes"  },
  ];

  return (
    <View style={{ flex: 1 }}>
      <Tabs
        tabBar={(props) => <CustomTabBar {...props} />}
        screenOptions={{
          headerTitleAlign: "center",
          headerShadowVisible: false,
          headerStyle: { backgroundColor: "#fff" },
          headerLeft: () => (
            <Pressable onPress={openDrawer} style={{ marginLeft: 16, padding: 4 }}>
              <Ionicons name="menu-outline" size={26} color="#111" />
            </Pressable>
          ),
          headerRight: () => (
            <Pressable
              onPress={() => router.push("/(tabs)/profile" as any)}
              style={{ marginRight: 16 }}
            >
              <View style={hd.avatar}>
                <Ionicons name="person" size={18} color="#fff" />
              </View>
            </Pressable>
          ),
        }}
      >
        <Tabs.Screen name="index"    options={{ title: "홈" }} />
        <Tabs.Screen name="chat"     options={{ title: "채팅" }} />
        <Tabs.Screen name="store"    options={{ title: "스토어" }} />
        <Tabs.Screen name="schedule" options={{ title: "달력" }} />
        <Tabs.Screen name="posts"    options={{ title: "게시물" }} />
        <Tabs.Screen name="match"    options={{ href: null, title: "강사 찾기" }} />
        <Tabs.Screen name="passes"   options={{ href: null, title: "수강권" }} />
        <Tabs.Screen name="profile"  options={{ href: null, title: "내 정보" }} />
        <Tabs.Screen name="bookings" options={{ href: null }} />
      </Tabs>

      {/* Side Drawer */}
      {drawerOpen && (
        <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
          <Pressable style={dr.backdrop} onPress={closeDrawer} />
          <Animated.View style={[dr.panel, { transform: [{ translateX: drawerAnim }] }]}>
            <View style={dr.header}>
              <Text style={dr.headerTitle}>메뉴</Text>
              <Pressable onPress={closeDrawer} style={{ padding: 4 }}>
                <Ionicons name="close" size={22} color="#6b7280" />
              </Pressable>
            </View>
            {DRAWER_ITEMS.map((item) => (
              <Pressable
                key={item.label}
                style={dr.item}
                onPress={() => {
                  closeDrawer();
                  setTimeout(() => router.push(item.route as any), 220);
                }}
              >
                <View style={dr.itemIconWrap}>
                  <Ionicons name={item.icon} size={20} color="#16a34a" />
                </View>
                <Text style={dr.itemLabel}>{item.label}</Text>
                <Ionicons name="chevron-forward" size={16} color="#d1d5db" />
              </Pressable>
            ))}
          </Animated.View>
        </View>
      )}
    </View>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────
const tb = StyleSheet.create({
  container: {
    backgroundColor: "#fff",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#e5e7eb",
    overflow: "visible",
  },
  bar: {
    flexDirection: "row",
    height: TAB_H,
    alignItems: "flex-end",
    paddingBottom: 8,
    overflow: "visible",
  },
  item: {
    flex: 1,
    alignItems: "center",
    gap: 3,
    paddingBottom: 2,
  },
  label: { fontSize: 10, fontWeight: "600" },
  centerWrap: {
    flex: 1,
    alignItems: "center",
    justifyContent: "flex-end",
    paddingBottom: 2,
    overflow: "visible",
  },
  centerBtn: {
    width: CENTER_SIZE,
    height: CENTER_SIZE,
    borderRadius: CENTER_SIZE / 2,
    backgroundColor: "#16a34a",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 3,
    marginTop: -(CENTER_LIFT),
    shadowColor: "#16a34a",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 10,
  },
  centerBtnActive: { backgroundColor: "#15803d" },
});

const hd = StyleSheet.create({
  avatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: "#16a34a",
    alignItems: "center",
    justifyContent: "center",
  },
});

const dr = StyleSheet.create({
  backdrop: {
    position: "absolute",
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  panel: {
    position: "absolute",
    top: 0, left: 0, bottom: 0,
    width: DRAWER_W,
    backgroundColor: "#fff",
    paddingTop: 56,
    shadowColor: "#000",
    shadowOffset: { width: 4, height: 0 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 20,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#f3f4f6",
    marginBottom: 8,
  },
  headerTitle: { fontSize: 18, fontWeight: "700", color: "#111" },
  item: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#f9fafb",
  },
  itemIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: "#f0fdf4",
    alignItems: "center",
    justifyContent: "center",
  },
  itemLabel: { flex: 1, fontSize: 15, color: "#111", fontWeight: "600" },
});
