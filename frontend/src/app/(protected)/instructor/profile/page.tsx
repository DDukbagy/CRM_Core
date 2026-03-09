// frontend/src/app/(protected)/instructor/profile/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/axios";
import { ArrowLeft, Save, Loader2, Check } from "lucide-react";

const LOCATIONS = ["서울", "경기", "인천", "부산", "대구", "대전", "광주", "기타"];
const SPECIALTIES = ["초보자 맞춤", "비거리 향상", "스윙 교정", "퍼팅", "코스 매니지먼트", "멘탈 코칭"];

type Profile = {
  display_name: string;
  phone: string;
  instructor_location: string;
  instructor_specialties: string;   // comma-separated
  instructor_bio: string;
};

export default function InstructorProfilePage() {
  const router = useRouter();
  const [form, setForm] = useState<Profile>({
    display_name: "",
    phone: "",
    instructor_location: "",
    instructor_specialties: "",
    instructor_bio: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 선택된 전문분야 배열
  const selectedSpecs: string[] = form.instructor_specialties
    ? form.instructor_specialties.split(",").map((s) => s.trim()).filter(Boolean)
    : [];

  useEffect(() => {
    api.get("/users/me").then((res) => {
      const d = res.data;
      setForm({
        display_name: d.display_name ?? "",
        phone: d.phone ?? "",
        instructor_location: d.instructor_location ?? "",
        instructor_specialties: d.instructor_specialties ?? "",
        instructor_bio: d.instructor_bio ?? "",
      });
    }).finally(() => setLoading(false));
  }, []);

  const toggleSpec = (sp: string) => {
    const next = selectedSpecs.includes(sp)
      ? selectedSpecs.filter((s) => s !== sp)
      : [...selectedSpecs, sp];
    setForm((f) => ({ ...f, instructor_specialties: next.join(",") }));
  };

  const handleSave = async () => {
    if (!form.display_name.trim()) { setError("이름을 입력해 주세요."); return; }
    setSaving(true);
    setError(null);
    try {
      await api.patch("/users/me", {
        display_name: form.display_name.trim(),
        phone: form.phone.trim() || null,
        instructor_location: form.instructor_location || null,
        instructor_specialties: form.instructor_specialties || null,
        instructor_bio: form.instructor_bio.trim() || null,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("저장에 실패했습니다. 다시 시도해 주세요.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="animate-spin text-gray-400" size={28} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="max-w-xl mx-auto space-y-6">

        {/* 헤더 */}
        <div className="flex items-center gap-3">
          <button onClick={() => router.back()} className="p-2 rounded-xl hover:bg-gray-200 transition">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-bold text-gray-900">프로필 편집</h1>
        </div>

        {/* 폼 */}
        <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm space-y-6">

          {/* 이름 */}
          <Field label="이름 *">
            <input
              className="input"
              value={form.display_name}
              onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))}
              placeholder="김프로"
            />
          </Field>

          {/* 전화번호 */}
          <Field label="전화번호">
            <input
              className="input"
              type="tel"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              placeholder="010-1234-5678"
            />
          </Field>

          {/* 지역 */}
          <Field label="활동 지역">
            <div className="flex flex-wrap gap-2">
              {LOCATIONS.map((loc) => (
                <button
                  key={loc}
                  type="button"
                  onClick={() => setForm((f) => ({
                    ...f,
                    instructor_location: f.instructor_location === loc ? "" : loc,
                  }))}
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

          {/* 전문 분야 */}
          <Field label="전문 분야 (복수 선택)">
            <div className="flex flex-wrap gap-2">
              {SPECIALTIES.map((sp) => (
                <button
                  key={sp}
                  type="button"
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

          {/* 소개글 */}
          <Field label="소개글">
            <textarea
              className="input resize-none"
              rows={4}
              value={form.instructor_bio}
              onChange={(e) => setForm((f) => ({ ...f, instructor_bio: e.target.value }))}
              placeholder="고객에게 보여질 강사 소개글을 입력하세요."
            />
            <span className="text-xs text-gray-400">{form.instructor_bio.length} / 300자</span>
          </Field>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-xl px-4 py-3">{error}</p>
          )}

          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full py-3 rounded-xl bg-gray-900 text-white font-semibold hover:bg-gray-800 transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {saving ? (
              <><Loader2 size={18} className="animate-spin" /> 저장 중...</>
            ) : saved ? (
              <><Check size={18} /> 저장됨</>
            ) : (
              <><Save size={18} /> 저장하기</>
            )}
          </button>
        </div>
      </div>

      <style jsx>{`
        .input {
          width: 100%;
          border: 1px solid #d1d5db;
          border-radius: 0.75rem;
          padding: 0.625rem 1rem;
          font-size: 0.875rem;
          outline: none;
          transition: border-color 0.15s;
        }
        .input:focus {
          border-color: #111;
          box-shadow: 0 0 0 2px rgba(17,17,17,0.08);
        }
      `}</style>
    </div>
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
