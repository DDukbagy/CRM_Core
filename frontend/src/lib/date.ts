// 로컬(브라우저 시간대) 기준 YYYY-MM-DD. toISOString() 은 UTC 라 한국에서는 0~9시에 하루 전 날짜가 된다
export function toLocalDateStr(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
