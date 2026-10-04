"use client";

// 강사 웹 레슨노트: 담당 고객에게 노트 작성 (글 또는 수기 노트 PDF). 강사 앱 레슨노트 탭과 같은 기능
// 피드백 게시물을 레슨노트로 통합 (2026-10-04)
import React, { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/axios";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { instructorNav } from "../page";
import { Loader2, Plus, X, FileText, Trash2 } from "lucide-react";

type LessonNote = {
  id: string;
  customer_id: string;
  booking_id: number | null;
  title: string | null;
  content: string | null;
  file_name: string | null;
  file_url: string | null;
  is_shared: boolean;
  customer_name: string | null;
  created_at: string;
};
type Customer = { id: string; display_name: string; role: string };

function fmtDate(iso: string) {
  const d = new Date(iso);
  return `${d.getFullYear()}.${d.getMonth() + 1}.${d.getDate()}`;
}

function errMsg(err: unknown, fallback: string) {
  const e = err as { response?: { data?: { error?: { message?: string }; detail?: string } }; message?: string };
  return e.response?.data?.error?.message ?? e.response?.data?.detail ?? e.message ?? fallback;
}

export default function LessonNotesPage() {
  const [notes, setNotes] = useState<LessonNote[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [filter, setFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<LessonNote | "new" | null>(null);

  const load = useCallback(async () => {
    try {
      const [n, u] = await Promise.all([api.get("/lesson-notes"), api.get("/users?limit=100")]);
      setNotes(n.data ?? []);
      setCustomers((u.data?.items ?? []).filter((c: Customer) => c.role === "CUSTOMER"));
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const shown = filter ? notes.filter(n => n.customer_id === filter) : notes;

  return (
    <DashboardLayout navItems={instructorNav} headerFallback="레슨노트">
      <div className="p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-gray-500">레슨노트</h2>
            <span className="text-xs bg-gray-100 text-gray-500 rounded-full px-2 py-0.5">{shown.length}</span>
          </div>
          <button
            onClick={() => setEditing("new")}
            className="flex items-center gap-1.5 rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800"
          >
            <Plus className="h-4 w-4" /> 노트 작성
          </button>
        </div>

        {/* 고객별 보기 */}
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setFilter(null)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-semibold ${!filter ? "bg-green-600 text-white" : "bg-gray-100 text-gray-600"}`}>
            전체
          </button>
          {customers.map(c => (
            <button key={c.id} onClick={() => setFilter(c.id)}
              className={`rounded-full px-3.5 py-1.5 text-xs font-semibold ${filter === c.id ? "bg-green-600 text-white" : "bg-gray-100 text-gray-600"}`}>
              {c.display_name}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
        ) : shown.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-gray-200 bg-white py-16 text-center">
            <p className="text-sm font-semibold text-gray-600">작성한 레슨노트가 없습니다</p>
            <p className="mt-1 text-xs text-gray-400">노트 작성을 눌러 담당 고객에게 노트를 남겨 보세요</p>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {shown.map(n => (
              <button key={n.id} onClick={() => setEditing(n)}
                className="rounded-2xl border border-gray-100 bg-white p-5 text-left shadow-sm hover:border-gray-200">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-bold text-green-600">{n.customer_name ?? "고객"}</span>
                  <span className="text-xs text-gray-400">{fmtDate(n.created_at)}</span>
                </div>
                {n.title && <p className="mb-1 text-sm font-bold text-gray-900">{n.title}</p>}
                {n.content && <p className="line-clamp-3 text-sm text-gray-600">{n.content}</p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  {n.file_name && (
                    <span className="flex items-center gap-1 rounded-md bg-blue-50 px-2 py-0.5 text-xs text-blue-600">
                      <FileText className="h-3 w-3" /> {n.file_name}
                    </span>
                  )}
                  {!n.is_shared && <span className="rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-500">고객 비공개</span>}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {editing && (
        <NoteModal
          target={editing}
          customers={customers}
          defaultCustomer={filter}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}
    </DashboardLayout>
  );
}

function NoteModal({
  target, customers, defaultCustomer, onClose, onSaved,
}: {
  target: LessonNote | "new";
  customers: Customer[];
  defaultCustomer: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const note = target === "new" ? null : target;
  const [customerId, setCustomerId] = useState<string | null>(note?.customer_id ?? defaultCustomer);
  const [title, setTitle] = useState(note?.title ?? "");
  const [content, setContent] = useState(note?.content ?? "");
  const [shared, setShared] = useState(note?.is_shared ?? true);
  const [file, setFile] = useState<File | null>(null);
  const [removeFile, setRemoveFile] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function uploadPdf(f: File): Promise<string> {
    const { data } = await api.post("/lesson-notes/upload-url", { filename: f.name, content_type: "application/pdf" });
    try {
      const res = await fetch(data.upload_url, { method: "PUT", headers: { "Content-Type": "application/pdf" }, body: f });
      if (!res.ok) throw new Error(`PDF 업로드 실패 (${res.status})`);
    } catch (e) {
      throw new Error(e instanceof Error && e.message.startsWith("PDF") ? e.message : "PDF 를 파일 저장소(S3)에 올리지 못했습니다. 네트워크와 저장소 설정을 확인하세요.");
    }
    return data.key;
  }

  async function save() {
    setError("");
    if (!note && !customerId) { setError("고객을 선택해주세요."); return; }
    const hasFile = !!file || (!!note?.file_name && !removeFile);
    if (!content.trim() && !hasFile) { setError("내용을 입력하거나 PDF 를 첨부해주세요."); return; }
    setBusy(true);
    try {
      let fileFields: { file_key?: string | null; file_name?: string | null } = {};
      if (file) fileFields = { file_key: await uploadPdf(file), file_name: file.name };
      else if (removeFile) fileFields = { file_key: null, file_name: null };
      const body = { title: title.trim() || null, content: content.trim() || null, is_shared: shared, ...fileFields };
      if (note) await api.patch(`/lesson-notes/${note.id}`, body);
      else await api.post("/lesson-notes", { customer_id: customerId, ...body });
      onSaved();
    } catch (e) {
      setError(errMsg(e, "저장하지 못했습니다."));
    } finally { setBusy(false); }
  }

  async function remove() {
    if (!note || !window.confirm("이 노트를 삭제할까요?")) return;
    try { await api.delete(`/lesson-notes/${note.id}`); onSaved(); }
    catch (e) { setError(errMsg(e, "삭제 실패")); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-base font-bold text-gray-900">{note ? "레슨노트" : "레슨노트 작성"}</h3>
          <button onClick={onClose} className="rounded-lg p-1 hover:bg-gray-100"><X className="h-5 w-5 text-gray-500" /></button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-gray-600">고객</label>
            {note ? (
              <p className="text-sm font-bold text-gray-900">{note.customer_name}</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {customers.length === 0 && <p className="text-xs text-gray-400">담당 고객이 없습니다.</p>}
                {customers.map(c => (
                  <button key={c.id} type="button" onClick={() => setCustomerId(c.id)}
                    className={`rounded-full border px-3.5 py-1.5 text-sm ${customerId === c.id ? "border-green-600 bg-green-600 font-semibold text-white" : "border-gray-200 text-gray-700"}`}>
                    {c.display_name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold text-gray-600">제목 (선택)</label>
            <input value={title} onChange={e => setTitle(e.target.value)} maxLength={200} placeholder="예: 3회차 레슨"
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold text-gray-600">내용</label>
            <textarea value={content} onChange={e => setContent(e.target.value)} rows={6} placeholder="레슨 내용, 피드백, 다음 레슨 목표..."
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900" />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold text-gray-600">수기 노트 (PDF)</label>
            <input type="file" accept="application/pdf" onChange={e => { setFile(e.target.files?.[0] ?? null); setRemoveFile(false); }}
              className="block w-full text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-gray-100 file:px-3 file:py-2 file:text-sm file:font-semibold" />
            {note?.file_name && !removeFile && !file && (
              <div className="mt-2 flex items-center justify-between rounded-xl bg-blue-50 px-3 py-2">
                <a href={note.file_url ?? "#"} target="_blank" rel="noreferrer" className="text-sm text-blue-600 underline">📄 {note.file_name}</a>
                <button type="button" onClick={() => setRemoveFile(true)} className="text-xs font-semibold text-red-600">삭제</button>
              </div>
            )}
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={shared} onChange={e => setShared(e.target.checked)} className="h-4 w-4 accent-green-600" />
            고객에게 보여주기
          </label>

          {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

          <div className="flex gap-2 pt-2">
            {note && (
              <button type="button" onClick={remove} className="flex items-center gap-1 rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-600">
                <Trash2 className="h-4 w-4" /> 삭제
              </button>
            )}
            <button type="button" onClick={save} disabled={busy}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gray-900 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
              {busy && <Loader2 className="h-4 w-4 animate-spin" />} 저장
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
