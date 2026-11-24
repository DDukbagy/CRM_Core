// 레슨노트 임시저장: 예약에 연결한 노트의 저장(= 레슨 완료)이 안 됐을 때 쓰던 글을 이 기기에 남겨 둔다
// 서버에는 저장하지 않는다. 기기를 바꾸거나 앱 데이터를 지우면 사라진다. 예약 하나에 임시저장 하나
import AsyncStorage from "@react-native-async-storage/async-storage";
import { supabase } from "./supabase";

export interface NoteDraft {
  booking_id: number;
  customer_id: string;
  customer_name: string;
  lesson: string;            // 화면에 보여 줄 수업 일시. 예) "11/20 (목) 10:00 ~ 12:00"
  title: string;
  content: string;
  is_shared: boolean;
  file_key: string | null;   // 이미 올린 PDF (다시 올리지 않는다)
  file_name: string | null;
  saved_at: string;          // ISO 시각
}

// 같은 기기에서 다른 강사가 로그인해도 섞이지 않게 강사별로 따로 둔다
async function storageKey(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user?.id ? `lesson-note-drafts:${session.user.id}` : null;
}

// 임시저장 목록 (최근에 저장한 것부터). 읽지 못하면 빈 목록
export async function listNoteDrafts(): Promise<NoteDraft[]> {
  try {
    const key = await storageKey();
    if (!key) return [];
    const raw = await AsyncStorage.getItem(key);
    const drafts = raw ? (JSON.parse(raw) as NoteDraft[]) : [];
    return Array.isArray(drafts) ? drafts.sort((a, b) => b.saved_at.localeCompare(a.saved_at)) : [];
  } catch {
    return [];
  }
}

// 임시저장 (같은 예약의 것이 있으면 바꾼다). 저장했으면 true
export async function saveNoteDraft(draft: NoteDraft): Promise<boolean> {
  try {
    const key = await storageKey();
    if (!key) return false;
    const others = (await listNoteDrafts()).filter(d => d.booking_id !== draft.booking_id);
    await AsyncStorage.setItem(key, JSON.stringify([draft, ...others]));
    return true;
  } catch {
    return false;
  }
}

export async function removeNoteDraft(bookingId: number): Promise<void> {
  try {
    const key = await storageKey();
    if (!key) return;
    const rest = (await listNoteDrafts()).filter(d => d.booking_id !== bookingId);
    await AsyncStorage.setItem(key, JSON.stringify(rest));
  } catch {
    // 지우지 못해도 화면 동작에는 영향이 없다 (다음에 목록에서 다시 지울 수 있다)
  }
}
