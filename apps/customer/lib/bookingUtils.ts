/**
 * bookingUtils.ts — 예약/달력 공통 유틸
 *
 * 이 파일은 apps/instructor/lib/bookingUtils.ts 와 동일해야 한다.
 * 변경 시 두 파일을 함께 수정할 것.
 */
import type { BookingRead } from "@/types/api";

// 타입
export type SessionGroup = {
  bookings: BookingRead[];
  startTime: string | null;
  endTime: string | null;
};

// 예약 상태 표시
// 전체 상태 정의 (양쪽 앱 동일하게 사용)
export const STATUS_COLOR: Record<string, string> = {
  REQUESTED:       "#f59e0b",
  CONFIRMED:       "#3b82f6",
  CANCEL_REQUESTED:"#f97316",
  COMPLETED:       "#16a34a",
  CANCELLED:       "#9ca3af",
  NO_SHOW:         "#ef4444",
};

export const STATUS_LABEL: Record<string, string> = {
  REQUESTED:       "대기",
  CONFIRMED:       "확정",
  CANCEL_REQUESTED:"취소신청",
  COMPLETED:       "완료",
  CANCELLED:       "취소",
  NO_SHOW:         "노쇼",
};

// 고객앱 칩 배경색 (고객 뷰에서 사용)
export const CHIP_BG: Record<string, string> = {
  REQUESTED:       "#fff7ed",
  CONFIRMED:       "#eff6ff",
  CANCEL_REQUESTED:"#fff7ed",
  CANCELLED:       "#fef2f2",
  COMPLETED:       "#f0fdf4",
  NO_SHOW:         "#fef2f2",
};

// 날짜/시간 유틸
export function toDateStr(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

// 로컬(기기 시간대) 기준 YYYY-MM-DD. toISOString() 은 UTC 라 한국에서는 0~9시에 하루 전 날짜가 된다
export function toLocalDateStr(date: Date = new Date()): string {
  return toDateStr(date.getFullYear(), date.getMonth(), date.getDate());
}

export function fmtTime(t: string): string {
  return t.slice(0, 5);
}

export function parseTime(t: string): { h: number; m: number } {
  const [h, m] = t.split(":").map(Number);
  return { h, m };
}

/**
 * 시간 문자열 → Y 좌표 (타임라인 렌더링용)
 * @param startH  타임라인 시작 시간 (예: 6)
 * @param hourH   1시간의 픽셀 높이 (예: 64)
 */
export function timeToY(t: string, startH: number, hourH: number): number {
  const { h, m } = parseTime(t);
  return (h - startH) * hourH + (m / 60) * hourH;
}

/**
 * 두 시간 사이의 픽셀 높이
 * @param hourH   1시간의 픽셀 높이
 */
export function timeDiff(start: string, end: string, hourH: number): number {
  const s = parseTime(start), e = parseTime(end);
  return ((e.h - s.h) * 60 + (e.m - s.m)) / 60 * hourH;
}

// JS 요일(0=일) → Python 요일(0=월)
export function jsWeekdayToPy(jsDay: number): number {
  return (jsDay + 6) % 7;
}

// 휴무일 판단
/**
 * 해당 날짜가 "효과적으로 휴무"인지 판단.
 * - 정기 휴무 요일 + 슬롯 없음 + 예약 없음 → 휴무
 * - HOLIDAY 예약 → 휴무
 * - WORK_OVERRIDE가 있으면 (hasAvailability=true) 정기 휴무여도 휴무 아님
 */
export function isEffectiveOffDay({
  pyWeekday,
  recurringOffDays,
  hasAvailability,
  hasBookings,
  isHoliday,
}: {
  pyWeekday: number;
  recurringOffDays: number[];
  hasAvailability: boolean;
  hasBookings: boolean;
  isHoliday: boolean;
}): boolean {
  const recurring = recurringOffDays.includes(pyWeekday);
  return (recurring && !hasAvailability && !hasBookings) || isHoliday;
}

// 예약 목록을 화면에 그릴 묶음으로 바꾼다
/**
 * 예약 1건 = 레슨 1회이므로 묶음 하나에 예약 하나가 들어간다 (시작 시각 순).
 * 시작·끝 시각은 서버가 예약에 붙여 준 값을 쓴다 (2시간 레슨이면 10:00 ~ 12:00).
 */
export function makeBookingGroups(bks: BookingRead[]): SessionGroup[] {
  return [...bks]
    .sort((a, b) => (a.start_time ?? "").localeCompare(b.start_time ?? ""))
    .map(b => ({ bookings: [b], startTime: b.start_time, endTime: b.end_time }));
}
