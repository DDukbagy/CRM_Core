"use client";

import React, { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/axios";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { instructorNav } from "../page";
import { Loader2, Save, Check } from "lucide-react";

const LOCATIONS = ["서울", "경기", "인천", "부산", "대구", "대전", "광주", "기타"];
const SPECIALTIES = ["초보자 맞춤", "비거리 향상", "스윙 교정", "퍼팅", "코스 매니지먼트", "멘탈 코칭"];
const WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];

type UserRead = {
  id: string;
  display_name: string;
  username: string;
  email: string | null;
  phone: string | null;
  status: string;
  instructor_tier: string | null;
  instructor_location: string | null;
  instructor_specialties: string | null;
  instructor_bio: string | null;
  career_years: number | null;
  certifications: string | null;
  recurring_off_days: number[] | null;
};

type Form = {
  display_name: string;
  phone: string;
  instructor_location: string;
  instructor_specialties: string;
  instructor_bio: string;
  career_years: string;
  certifications: string;
};

export default function InstructorProfilePage() {
  const [me, setMe] = useState<UserRead | null>(null);
  const [form, setForm] = useState<Form>({
    display_name: "", phone: "", instructor_location: "",
    instructor_specialties: "", instructor_bio: "",
    career_years: "", certifications: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offDaysSaving, setOffDaysSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/users/me");
      const d: UserRead = res.data;
      setMe(d);
      setForm({
        display_name: d.display_name ?? "",
        phone: d.phone ?? "",
        instructor_location: d.instructor_location ?? "",
        instructor_specialties: d.instructor_specialties ?? "",
        instructor_bio: d.instructor_bio ?? "",
        career_years: d.career_years?.toString() ?? "",
        certifications: d.certifications ?? "",
      });
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const selectedSpecs = form.instructor_specialties
    ? form.instructor_specialties.split(",").map(s => s.trim()).filter(Boolean)
    : [];

  const toggleSpec = (sp: string) => {
    const next = selectedSpecs.includes(sp)
      ? selectedSpecs.filter(s => s !== sp)
      : [...selectedSpecs, sp];
    setForm(f => ({ ...f, instructor_specialties: next.join(",") }));
  };

  const handleSave = async () => {
    if (!form.display_name.trim()) { setError("이름을 입력해 주세요."); return; }
    setSaving(true); setError(null);
    try {
      const res = await api.patch("/users/me", {
        display_name: form.display_name.trim(),
        phone: form.phone.trim() || null,
        instructor_location: form.instructor_location || null,
        instructor_specialties: form.instructor_specialties || null,
        instructor_bio: form.instructor_bio.trim() || null,
        career_years: form.career_years ? parseInt(form.career_years) : null,
        certifications: form.certifications.trim() || null,
      });
      setMe(res.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("저장에 실패했습니다. 다시 시도해 주세요.");
    } finally { setSaving(false); }
  };

  const toggleOffDay = async (idx: number) => {
    if (!me) return;
    const current = me.recurring_off_days ?? [];
    const next = current.includes(idx)
      ? current.filter(d => d !== idx)
      : [...current, idx].sort((a, b) => a - b);
    setOffDaysSaving(true);
    try {
      const res = await api.patch("/users/me", { recurring_off_days: next });
      setMe(res.data);
    } catch { /* ignore */ } finally { setOffDaysSaving(false); }
  };

  if (loading) {
    return (
      <DashboardLayout navItems={instructorNav} headerFallback="내 정보">
        <div className="flex justify-center py-24"><Loader2 className="animate-spin text-gray-400" size={28} /></div>
      </DashboardLayout>
    );
  }

  const tierLabel = me?.instructor_tier === "NAMED" ? "네임드 강사" : "일반 강사";

  return (
    <DashboardLayout navItems={instructorNav} headerFallback="내 정보">
      <div className="max-w-2xl mx-auto space-y-6">

        {/* 프로필 헤더 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm flex items-center gap-5">
          <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center shrink-0">
            <span className="text-2xl font-bold text-green-600">{me?.display_name.charAt(0)}</span>
          </div>
          <div>
            <p className="text-xl font-bold text-gray-900">{me?.display_name}</p>
            <p className="text-sm text-gray-400 mt-0.5">@{me?.username}</p>
            <span className={`inline-block mt-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${
              me?.instructor_tier === "NAMED" ? "bg-yellow-100 text-yellow-800" : "bg-gray-100 text-gray-600"
            }`}>
              {tierLabel}
            </span>
          </div>
        </div>

        {/* 계정 정보 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">계정 정보</h2>
          <div className="space-y-3">
            <InfoRow label="이메일" value={me?.email ?? "-"} />
            <InfoRow label="아이디" value={me?.username ?? "-"} />
            <InfoRow label="상태" value={me?.status ?? "-"} />
          </div>
        </div>

        {/* 강사 프로필 편집 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-5">강사 프로필</h2>
          <div className="space-y-5">

            <Field label="이름 *">
              <input
                value={form.display_name}
                onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                placeholder="김프로"
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
              />
            </Field>

            <Field label="전화번호">
              <input
                type="tel"
                value={form.phone}
                onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                placeholder="010-1234-5678"
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
              />
            </Field>

            <Field label="경력 (년)">
              <input
                type="number"
                value={form.career_years}
                onChange={e => setForm(f => ({ ...f, career_years: e.target.value }))}
                placeholder="5"
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
              />
            </Field>

            <Field label="자격증">
              <input
                value={form.certifications}
                onChange={e => setForm(f => ({ ...f, certifications: e.target.value }))}
                placeholder="예: KGA 프로, KPGA 티칭프로"
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
              />
            </Field>

            <Field label="활동 지역">
              <div className="flex flex-wrap gap-2">
                {LOCATIONS.map(loc => (
                  <button
                    key={loc}
                    onClick={() => setForm(f => ({ ...f, instructor_location: f.instructor_location === loc ? "" : loc }))}
                    className={`px-4 py-1.5 rounded-full text-sm font-medium border transition ${
                      form.instructor_location === loc
                        ? "bg-gray-900 text-white border-gray-900"
                        : "bg-white text-gray-600 border-gray-300 hover:border-gray-500"
                    }`}
                  >
                    {loc}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="전문 분야 (복수 선택)">
              <div className="flex flex-wrap gap-2">
                {SPECIALTIES.map(sp => (
                  <button
                    key={sp}
                    onClick={() => toggleSpec(sp)}
                    className={`px-4 py-1.5 rounded-full text-sm font-medium border transition ${
                      selectedSpecs.includes(sp)
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                    }`}
                  >
                    {sp}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="소개글">
              <textarea
                rows={4}
                value={form.instructor_bio}
                onChange={e => setForm(f => ({ ...f, instructor_bio: e.target.value }))}
                placeholder="고객에게 보여질 강사 소개글을 입력하세요."
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 resize-none"
              />
              <span className="text-xs text-gray-400">{form.instructor_bio.length} / 300자</span>
            </Field>
          </div>

          {error && <p className="mt-4 text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">{error}</p>}

          <button
            onClick={handleSave}
            disabled={saving}
            className="mt-6 w-full py-3 rounded-xl bg-gray-900 text-white font-semibold hover:bg-gray-800 transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {saving ? <><Loader2 size={16} className="animate-spin" /> 저장 중...</>
              : saved ? <><Check size={16} /> 저장됨</>
              : <><Save size={16} /> 저장하기</>}
          </button>
        </div>

        {/* 정기 휴무 요일 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-1">정기 휴무 요일</h2>
          <p className="text-xs text-gray-400 mb-4">선택한 요일은 고객 예약이 차단됩니다.</p>
          <div className="flex gap-2 flex-wrap">
            {WEEKDAY_LABELS.map((label, idx) => {
              const isOff = (me?.recurring_off_days ?? []).includes(idx);
              return (
                <button
                  key={idx}
                  disabled={offDaysSaving}
                  onClick={() => toggleOffDay(idx)}
                  className={`w-12 h-14 rounded-xl flex flex-col items-center justify-center text-sm font-bold border transition ${
                    isOff
                      ? "bg-red-50 border-red-300 text-red-600"
                      : "bg-green-50 border-green-200 text-green-600 hover:border-green-400"
                  } disabled:opacity-50`}
                >
                  <span>{label}</span>
                  {isOff && <span className="text-[9px] font-semibold text-red-500 mt-0.5">휴무</span>}
                </button>
              );
            })}
          </div>
          {offDaysSaving && (
            <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
              <Loader2 size={12} className="animate-spin" /> 저장 중...
            </div>
          )}
        </div>

      </div>
    </DashboardLayout>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-semibold text-gray-700">{label}</label>
      {children}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 text-xs text-gray-400 shrink-0">{label}</span>
      <span className="text-sm text-gray-800">{value}</span>
    </div>
  );
}
