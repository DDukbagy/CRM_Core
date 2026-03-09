"use client";

import { useEffect, useMemo, useState } from "react";

type TimeSlot = {
  id: number;
  calendar_id: number;
  start_time: string; // "10:00:00"
  end_time: string;   // "11:00:00"
  weekdays: number[]; // 0..6 (프로젝트 기준)
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
};

const WEEKDAY_LABEL: Record<number, string> = {
  0: "일",
  1: "월",
  2: "화",
  3: "수",
  4: "목",
  5: "금",
  6: "토",
};

function hhmm(t: string) {
  // "10:00:00" -> "10:00"
  return (t || "").slice(0, 5);
}

export default function SchedulePage() {
  const [slots, setSlots] = useState<TimeSlot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const today = new Date();
  // JS getDay(): 0=Sun..6=Sat  (백엔드 weekdays도 동일하다고 가정)
  const todayIdx = today.getDay();

  const fetchSlots = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/calendars/me/time-slots", { cache: "no-store" });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body?.error?.message || `HTTP ${res.status}`);
      }
      setSlots(Array.isArray(body) ? body : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load time-slots");
      setSlots([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSlots();
  }, []);

  const activeSlots = useMemo(() => slots.filter((s) => s.is_active), [slots]);

  const todaySlots = useMemo(
    () => activeSlots.filter((s) => Array.isArray(s.weekdays) && s.weekdays.includes(todayIdx)),
    [activeSlots, todayIdx]
  );

  const coveredWeekdays = useMemo(() => {
    const set = new Set<number>();
    for (const s of activeSlots) {
      for (const d of s.weekdays || []) set.add(d);
    }
    return Array.from(set).sort((a, b) => a - b);
  }, [activeSlots]);

  return (
    <div style={{ padding: 16, maxWidth: 920, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>스케줄(개발 MVP)</h1>
        <button
          onClick={fetchSlots}
          disabled={loading}
          style={{
            padding: "8px 12px",
            borderRadius: 10,
            border: "1px solid #ddd",
            background: loading ? "#f5f5f5" : "white",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "불러오는 중..." : "새로고침"}
        </button>
      </div>

      {/* 요약 카드 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div style={{ border: "1px solid #eee", borderRadius: 14, padding: 14 }}>
          <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>오늘 요약</div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>
            {WEEKDAY_LABEL[todayIdx]}요일 타임슬롯 {todaySlots.length}개
          </div>
          <div style={{ fontSize: 12, color: "#777", marginTop: 6 }}>
            (활성 슬롯 기준)
          </div>
        </div>

        <div style={{ border: "1px solid #eee", borderRadius: 14, padding: 14 }}>
          <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>주간 요약</div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>
            활성 슬롯 {activeSlots.length}개 · 커버 요일{" "}
            {coveredWeekdays.length ? coveredWeekdays.map((d) => WEEKDAY_LABEL[d]).join(", ") : "-"}
          </div>
          <div style={{ fontSize: 12, color: "#777", marginTop: 6 }}>
            다음 단계에서 캘린더 UI로 확장
          </div>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <div
          style={{
            border: "1px solid #f3c2c2",
            background: "#fff6f6",
            color: "#8a1f1f",
            borderRadius: 12,
            padding: 12,
            marginBottom: 14,
          }}
        >
          불러오기 실패: {error}
        </div>
      )}

      {/* 리스트 */}
      <div style={{ border: "1px solid #eee", borderRadius: 14, overflow: "hidden" }}>
        <div style={{ padding: 12, borderBottom: "1px solid #eee", fontWeight: 700 }}>
          타임슬롯 목록
          <span style={{ marginLeft: 8, fontWeight: 500, color: "#666" }}>
            (총 {slots.length}개)
          </span>
        </div>

        {slots.length === 0 && !loading ? (
          <div style={{ padding: 14, color: "#666" }}>등록된 타임슬롯이 없습니다.</div>
        ) : (
          <div>
            {slots.map((s) => (
              <div
                key={s.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: 12,
                  borderTop: "1px solid #f3f3f3",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ fontWeight: 700 }}>
                    {hhmm(s.start_time)} ~ {hhmm(s.end_time)}
                    <span style={{ marginLeft: 10, fontSize: 12, color: "#888" }}>
                      (calendar_id: {s.calendar_id}, id: {s.id})
                    </span>
                  </div>

                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {(s.weekdays || []).map((d) => (
                      <span
                        key={d}
                        style={{
                          fontSize: 12,
                          padding: "3px 8px",
                          borderRadius: 999,
                          border: "1px solid #ddd",
                          background: "#fafafa",
                        }}
                      >
                        {WEEKDAY_LABEL[d] ?? d}
                      </span>
                    ))}
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      fontSize: 12,
                      padding: "4px 8px",
                      borderRadius: 999,
                      border: "1px solid #ddd",
                      background: s.is_active ? "#f3fff6" : "#fff7f3",
                    }}
                  >
                    {s.is_active ? "활성" : "비활성"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 다음 단계 안내 */}
      <div style={{ marginTop: 14, color: "#666", fontSize: 12 }}>
        Step 13 다음: 하단 탭(5개) 레이아웃 뼈대 + 캘린더/예약 리스트 UI로 확장
      </div>
    </div>
  );
}