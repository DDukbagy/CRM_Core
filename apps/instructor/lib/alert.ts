// 알림·확인창: 폰은 기존 Alert.alert 그대로, 웹은 브라우저 창
// react-native-web 의 Alert.alert 는 아무것도 띄우지 않아, 브라우저에서 메시지가 안 보이고 확인 버튼이 있는 동작(취소·삭제 등)이 실행되지 않았다
import { Alert, Platform, type AlertButton } from "react-native";

export function appAlert(title: string, message?: string, buttons?: AlertButton[]): void {
  if (Platform.OS !== "web") {
    Alert.alert(title, message, buttons);
    return;
  }
  const text = message ? `${title}\n\n${message}` : title;
  const cancel = buttons?.find(b => b.style === "cancel");
  const action = buttons?.find(b => b.style !== "cancel");
  // 취소 + 실행 버튼 → 확인창, 그 밖(메시지만·확인 버튼 하나) → 알림창
  if (cancel && action) {
    if (window.confirm(text)) action.onPress?.();
    else cancel.onPress?.();
    return;
  }
  window.alert(text);
  (action ?? cancel)?.onPress?.();
}
