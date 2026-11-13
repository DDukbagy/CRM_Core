// 푸시 알림: 권한 요청 → Expo 푸시 토큰 발급 → 서버 등록/해제, 알림 탭 시 화면 이동
import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import type { UserRead } from "@/types/api";
import { apiFetch } from "./api";

// app.json 의 expo-notifications 플러그인 defaultChannel 과 같은 이름
export const ANDROID_CHANNEL_ID = "default";

// 앱이 켜져 있을 때 받은 알림도 배너로 보여 준다
export function configureForegroundNotifications(): void {
  if (Platform.OS === "web") return;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldPlaySound: true,
      shouldSetBadge: false,
      shouldShowBanner: true,
      shouldShowList: true,
    }),
  });
}

// EAS projectId: getExpoPushTokenAsync 에 필요 (app.json extra.eas.projectId)
function getProjectId(): string | undefined {
  return Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId ?? undefined;
}

/**
 * 권한을 확인·요청하고 Expo 푸시 토큰을 돌려준다.
 * 웹, 권한 거부, 시뮬레이터(토큰 발급 불가)는 null.
 */
export async function getExpoPushToken(): Promise<string | null> {
  if (Platform.OS === "web") return null;

  // Android 13+ 는 채널이 있어야 권한 요청 창이 뜬다
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
      name: "기본 알림",
      importance: Notifications.AndroidImportance.HIGH,
    });
  }

  const current = await Notifications.getPermissionsAsync();
  let granted = current.granted;
  if (!granted && current.canAskAgain) {
    granted = (await Notifications.requestPermissionsAsync()).granted;
  }
  if (!granted) return null;

  const projectId = getProjectId();
  if (!projectId) {
    console.warn("[push] EAS projectId 가 없어 푸시 토큰을 발급할 수 없습니다 (app.json extra.eas.projectId).");
    return null;
  }

  try {
    return (await Notifications.getExpoPushTokenAsync({ projectId })).data;
  } catch (e) {
    // 시뮬레이터·네트워크 오류: 알림 없이 앱은 계속 쓴다
    console.warn("[push] 푸시 토큰 발급 실패:", e instanceof Error ? e.message : e);
    return null;
  }
}

// 로그인 상태가 되면 호출: 토큰을 서버(PUT /users/me/push-token)에 저장
export async function registerPushToken(): Promise<void> {
  try {
    // 고객이 아닌 계정은 로그인 화면에서 곧바로 로그아웃된다. 그 계정에 이 기기 토큰을 남기지 않는다
    const me = await apiFetch<UserRead>("/users/me");
    if (me.role !== "CUSTOMER") return;
    const token = await getExpoPushToken();
    if (!token) return;
    await apiFetch("/users/me/push-token", { method: "PUT", body: { token } });
  } catch (e) {
    console.warn("[push] 푸시 토큰 등록 실패:", e instanceof Error ? e.message : e);
  }
}

// 로그아웃 직전에 호출: 다른 계정으로 알림이 가지 않게 서버의 토큰을 지운다
export async function unregisterPushToken(): Promise<void> {
  if (Platform.OS === "web") return;
  try {
    await apiFetch("/users/me/push-token", { method: "DELETE" });
  } catch {
    // 세션이 이미 끝났으면 실패해도 로그아웃은 계속한다
  }
}

// 알림 data 에서 이동할 경로를 고른다 (백엔드 app/core/push.py 의 data 키와 맞춘다)
export function routeForNotificationData(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const bookingId = (data as Record<string, unknown>).booking_id;
  if (typeof bookingId === "number" || (typeof bookingId === "string" && bookingId !== "")) {
    return `/booking/${bookingId}`;
  }
  return null;
}

/**
 * 알림을 눌러 앱을 열었을 때(실행 중·백그라운드·종료 상태 모두) onRoute 로 경로를 넘긴다.
 * 반환값은 구독 해제 함수.
 */
export function subscribeNotificationTaps(onRoute: (route: string) => void): () => void {
  if (Platform.OS === "web") return () => {};

  const handle = (response: Notifications.NotificationResponse | null) => {
    if (!response) return;
    const route = routeForNotificationData(response.notification.request.content.data);
    if (route) onRoute(route);
    Notifications.clearLastNotificationResponseAsync().catch(() => {});
  };

  // 종료 상태에서 알림으로 앱을 연 경우
  Notifications.getLastNotificationResponseAsync().then(handle).catch(() => {});
  const sub = Notifications.addNotificationResponseReceivedListener(handle);
  return () => sub.remove();
}
