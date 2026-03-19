"use client";

import React, { useEffect, useState, useCallback } from "react";
import Image from "next/image";
import { api } from "@/lib/axios";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { instructorNav } from "../page";
import { Loader2, Plus, Trash2, Edit2, X, Image as ImageIcon, Send } from "lucide-react";

type MediaItem = { id?: number; url: string; media_type: "IMAGE" | "VIDEO"; sort_order?: number };
type Post = {
  id: string;
  type: "PROMOTION" | "FEEDBACK";
  title: string | null;
  content: string | null;
  media_items: MediaItem[];
  customer_id: string | null;
  customer_name: string | null;
  is_public: boolean;
  created_at: string;
};
type Comment = { id: number; user_name: string | null; content: string; created_at: string };
type Customer = { id: string; display_name: string };

export default function PostsPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);

  // 글 작성/수정 모달
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Post | null>(null);
  const [formType, setFormType] = useState<"PROMOTION" | "FEEDBACK">("PROMOTION");
  const [formContent, setFormContent] = useState("");
  const [formCustomerId, setFormCustomerId] = useState("");
  const [formMedia, setFormMedia] = useState<MediaItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  // 타입 선택
  const [typeSelectOpen, setTypeSelectOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const [postsRes, usersRes] = await Promise.allSettled([
        api.get("/instructor-posts"),
        api.get("/users?role=CUSTOMER&limit=100"),
      ]);
      if (postsRes.status === "fulfilled") setPosts(postsRes.value.data ?? []);
      if (usersRes.status === "fulfilled") setCustomers(usersRes.value.data?.items ?? []);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  function openCreate(type: "PROMOTION" | "FEEDBACK") {
    setEditTarget(null);
    setFormType(type);
    setFormContent("");
    setFormCustomerId("");
    setFormMedia([]);
    setFormError("");
    setTypeSelectOpen(false);
    setFormOpen(true);
  }

  function openEdit(post: Post) {
    setEditTarget(post);
    setFormType(post.type);
    setFormContent(post.content ?? "");
    setFormCustomerId(post.customer_id ?? "");
    setFormMedia(post.media_items ?? []);
    setFormError("");
    setFormOpen(true);
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    setUploading(true);
    try {
      const uploaded: MediaItem[] = [];
      for (const file of files) {
        const isVideo = file.type.startsWith("video/");
        const { data } = await api.post("/instructor-posts/upload-url", {
          filename: file.name,
          content_type: file.type,
        });
        await fetch(data.upload_url, { method: "PUT", headers: { "Content-Type": file.type }, body: file });
        uploaded.push({ url: data.public_url, media_type: isVideo ? "VIDEO" : "IMAGE" });
      }
      setFormMedia(prev => [...prev, ...uploaded]);
    } catch { setFormError("파일 업로드 실패"); }
    finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleSubmit() {
    if (!formContent && formMedia.length === 0) { setFormError("내용을 입력하거나 미디어를 추가해주세요."); return; }
    if (formType === "FEEDBACK" && !formCustomerId) { setFormError("피드백 대상 고객을 선택해주세요."); return; }
    setSubmitting(true);
    setFormError("");
    try {
      if (editTarget) {
        await api.patch(`/instructor-posts/${editTarget.id}`, {
          content: formContent || null,
          media_items: formMedia.map((m, i) => ({ url: m.url, media_type: m.media_type, sort_order: i })),
        });
      } else {
        await api.post("/instructor-posts", {
          type: formType,
          title: formType === "PROMOTION" ? "게시글" : null,
          content: formContent || null,
          media_items: formMedia.map((m, i) => ({ url: m.url, media_type: m.media_type, sort_order: i })),
          customer_id: formType === "FEEDBACK" ? formCustomerId : undefined,
        });
      }
      setFormOpen(false);
      await load();
    } catch { setFormError("저장 실패. 다시 시도해주세요."); }
    finally { setSubmitting(false); }
  }

  async function handleDelete(id: string) {
    if (!confirm("게시물을 삭제하시겠습니까?")) return;
    try { await api.delete(`/instructor-posts/${id}`); await load(); }
    catch { alert("삭제 실패"); }
  }

  return (
    <DashboardLayout navItems={instructorNav} headerFallback="게시물">
      <div>
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider">
            게시물 <span className="ml-1 bg-gray-100 text-gray-600 text-xs font-bold px-2 py-0.5 rounded-full">{posts.length}</span>
          </h2>
          <button
            onClick={() => setTypeSelectOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-gray-900 text-white rounded-xl text-sm font-semibold hover:bg-gray-800 transition"
          >
            <Plus size={16} /> 글 작성
          </button>
        </div>

        {/* 게시물 목록 */}
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gray-400" /></div>
        ) : posts.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center">
            <p className="text-3xl mb-3">📭</p>
            <p className="text-gray-400 text-sm">등록된 게시물이 없습니다</p>
          </div>
        ) : (
          <div className="space-y-4">
            {posts.map(post => (
              <PostCard
                key={post.id}
                post={post}
                onEdit={() => openEdit(post)}
                onDelete={() => handleDelete(post.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* 타입 선택 모달 */}
      {typeSelectOpen && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40" onClick={() => setTypeSelectOpen(false)}>
          <div className="bg-white rounded-t-2xl w-full max-w-lg p-6 pb-10" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-bold text-center text-gray-900 mb-5">어떤 글을 올리시겠어요?</h3>
            <div className="grid grid-cols-2 gap-3">
              {([
                { key: "PROMOTION" as const, icon: "📝", label: "게시글", sub: "홍보·소식" },
                { key: "FEEDBACK" as const, icon: "💬", label: "피드백", sub: "고객 피드백" },
              ]).map(t => (
                <button
                  key={t.key}
                  onClick={() => openCreate(t.key)}
                  className="flex flex-col items-center p-5 rounded-2xl border border-gray-200 hover:border-gray-400 hover:shadow-sm transition gap-1"
                >
                  <span className="text-3xl">{t.icon}</span>
                  <span className="font-bold text-gray-900">{t.label}</span>
                  <span className="text-xs text-gray-400">{t.sub}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 글 작성/수정 모달 */}
      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
              <h3 className="font-bold text-gray-900">
                {editTarget ? "글 수정" : formType === "PROMOTION" ? "📝 게시글" : "💬 피드백"}
              </h3>
              <button onClick={() => setFormOpen(false)} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <div className="p-6 space-y-4">
              {/* 미디어 업로드 */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-2">사진 / 동영상</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {formMedia.map((m, i) => (
                    <div key={i} className="relative w-20 h-20 rounded-xl overflow-hidden bg-gray-100">
                      {m.media_type === "IMAGE"
                        ? <Image src={m.url} alt="" fill className="object-cover" unoptimized />
                        : <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs">동영상</div>
                      }
                      <button
                        onClick={() => setFormMedia(prev => prev.filter((_, idx) => idx !== i))}
                        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/60 text-white text-xs flex items-center justify-center"
                      >✕</button>
                    </div>
                  ))}
                  <label className={`w-20 h-20 rounded-xl border-2 border-dashed border-gray-300 flex flex-col items-center justify-center cursor-pointer hover:border-gray-500 transition ${uploading ? "opacity-50 pointer-events-none" : ""}`}>
                    {uploading ? <Loader2 size={18} className="animate-spin text-gray-400" /> : <><ImageIcon size={18} className="text-gray-400" /><span className="text-xs text-gray-400 mt-1">추가</span></>}
                    <input type="file" accept="image/*,video/*" multiple className="hidden" onChange={handleFileUpload} disabled={uploading} />
                  </label>
                </div>
              </div>

              {/* FEEDBACK 고객 선택 */}
              {formType === "FEEDBACK" && !editTarget && (
                <div>
                  <label className="block text-xs font-semibold text-gray-500 mb-1.5">피드백 대상 고객 *</label>
                  <select
                    value={formCustomerId}
                    onChange={e => setFormCustomerId(e.target.value)}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  >
                    <option value="">고객 선택</option>
                    {customers.map(c => <option key={c.id} value={c.id}>{c.display_name}</option>)}
                  </select>
                </div>
              )}

              {/* 내용 */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1.5">내용</label>
                <textarea
                  rows={5}
                  value={formContent}
                  onChange={e => setFormContent(e.target.value)}
                  placeholder="내용을 입력하세요..."
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-gray-900"
                />
              </div>

              {formError && <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">{formError}</p>}

              <div className="flex gap-3 pt-1">
                <button onClick={() => setFormOpen(false)} className="flex-1 py-3 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 transition">취소</button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || uploading}
                  className="flex-1 py-3 rounded-xl bg-gray-900 text-white text-sm font-bold hover:bg-gray-800 transition disabled:opacity-40 flex items-center justify-center gap-2"
                >
                  {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />} {editTarget ? "수정" : "등록"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

function PostCard({ post, onEdit, onDelete }: { post: Post; onEdit: () => void; onDelete: () => void }) {
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentInput, setCommentInput] = useState("");
  const [sending, setSending] = useState(false);

  async function loadComments() {
    try { const res = await api.get(`/instructor-posts/${post.id}/comments`); setComments(res.data ?? []); }
    catch { /* ignore */ }
  }

  function toggleComments() {
    if (!commentsOpen) loadComments();
    setCommentsOpen(v => !v);
  }

  async function sendComment() {
    if (!commentInput.trim()) return;
    setSending(true);
    try {
      const res = await api.post(`/instructor-posts/${post.id}/comments`, { content: commentInput.trim() });
      setComments(prev => [...prev, res.data]);
      setCommentInput("");
    } catch { /* ignore */ } finally { setSending(false); }
  }

  const isFeedback = post.type === "FEEDBACK";

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
      <div className="flex">
        {/* 미디어 */}
        {post.media_items.length > 0 && (
          <div className="w-40 shrink-0 bg-gray-900">
            {post.media_items[0].media_type === "IMAGE"
              ? <div className="relative w-full h-44"><Image src={post.media_items[0].url} alt="" fill className="object-cover" unoptimized /></div>
              : <div className="w-full h-44 flex items-center justify-center text-gray-400 text-xs">동영상</div>
            }
          </div>
        )}
        {/* 내용 */}
        <div className="flex-1 p-4 flex flex-col justify-between min-h-[120px]">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${isFeedback ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-600"}`}>
                {isFeedback ? "💬 피드백" : "📝 게시글"}
              </span>
              {post.is_public && <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-green-100 text-green-700">공개</span>}
              {isFeedback && post.customer_name && (
                <span className="text-xs text-gray-500">👤 {post.customer_name}</span>
              )}
            </div>
            <p className="text-sm text-gray-700 line-clamp-3">{post.content ?? ""}</p>
          </div>
          <div className="flex items-center justify-between mt-3">
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-400">{new Date(post.created_at).toLocaleDateString("ko-KR")}</span>
              <button onClick={toggleComments} className="text-xs text-gray-400 hover:text-gray-600">
                💬 댓글 {commentsOpen ? "접기" : "보기"}
              </button>
            </div>
            <div className="flex gap-2">
              <button onClick={onEdit} className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition">
                <Edit2 size={14} />
              </button>
              <button onClick={onDelete} className="p-1.5 rounded-lg border border-red-100 text-red-400 hover:bg-red-50 transition">
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 댓글 */}
      {commentsOpen && (
        <div className="border-t border-gray-50 bg-gray-50 px-4 py-3 space-y-2">
          {comments.length === 0 ? (
            <p className="text-xs text-gray-400 italic">댓글이 없습니다</p>
          ) : comments.map(c => (
            <div key={c.id} className="bg-white rounded-lg p-2.5">
              <p className="text-xs font-bold text-gray-700 mb-0.5">{c.user_name ?? "알 수 없음"}</p>
              <p className="text-xs text-gray-600">{c.content}</p>
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <input
              value={commentInput}
              onChange={e => setCommentInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendComment()}
              placeholder="댓글 입력..."
              className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-gray-400"
            />
            <button
              onClick={sendComment}
              disabled={sending}
              className="px-3 py-2 bg-gray-900 text-white rounded-lg text-xs font-semibold disabled:opacity-40"
            >
              {sending ? "..." : "전송"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
