// 예약 한 건을 화면에 보여 줄 한 줄로 바꾼다
import type { BookingRead } from "@/types/api";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

// "11/20 (목) 10:00 ~ 12:00"
export function lessonLine(b: Pick<BookingRead, "when" | "start_time" | "end_time">): string {
  const [, m, d] = b.when.split("-").map(Number);
  const day = WEEKDAYS[new Date(b.when + "T00:00:00").getDay()];
  const time = b.start_time && b.end_time ? ` ${b.start_time.slice(0, 5)} ~ ${b.end_time.slice(0, 5)}` : "";
  return `${m}/${d} (${day})${time}`;
}
