// types/api.ts

export type UserRole = "CUSTOMER" | "INSTRUCTOR" | "CONTENT_MANAGER" | "ADMIN";

export interface UserRead {
  id: string;
  email: string;
  username: string;
  display_name: string;
  phone: string | null;
  role: UserRole;
  status: string; // ACTIVE | PENDING | SUSPENDED | WITHDRAWN(탈퇴)
  is_active: boolean;
  withdrawn_at?: string | null; // 탈퇴 처리 시각
  feedback_consent?: boolean;   // 피드백 공개 동의
  manager_id: string | null;
  // 강사 필드
  instructor_tier: string | null;
  instructor_location: string | null;
  instructor_specialties: string | null;
  instructor_bio: string | null;
  career_years: number | null;
  certifications: string | null;
  // 고객 필드
  birth_date: string | null;
  gender: string | null;
  lesson_purpose: string | null;
  recurring_off_days: number[];
  created_at: string;
  updated_at: string;
}

export interface UserUpdate {
  display_name?: string;
  username?: string;
  phone?: string;
  // 강사 프로필
  instructor_location?: string | null;
  instructor_specialties?: string | null;
  instructor_bio?: string | null;
  career_years?: number | null;
  certifications?: string | null;
  // 고객 프로필
  birth_date?: string | null;
  gender?: string | null;
  lesson_purpose?: string | null;
  feedback_consent?: boolean;
}

export type BookingStatus = "REQUESTED" | "CONFIRMED" | "CANCEL_REQUESTED" | "CANCELLED" | "COMPLETED" | "NO_SHOW";
// HOLIDAY: 강사가 지정한 휴무일, WORK_OVERRIDE: 휴무 요일에 특정 슬롯만 오픈
export type BookingType = "LESSON" | "HOLIDAY" | "WORK_OVERRIDE";

export interface BookingRead {
  id: number;
  when: string; // YYYY-MM-DD
  topic: string | null;
  status: BookingStatus;
  type: BookingType;
  description: string | null;
  cancel_reason: string | null;
  time_slot_id: number;
  guest_id: string;
  created_at: string;
  updated_at: string;
}

export interface BookingCreate {
  time_slot_id: number;
  when: string; // date string YYYY-MM-DD
  topic?: string;
  description?: string;
  type?: BookingType;
}

export interface AvailabilitySlot {
  time_slot_id: number;
  start_time: string; // HH:MM:SS
  end_time: string;
}

export interface AvailabilityDay {
  date: string; // YYYY-MM-DD
  slots: AvailabilitySlot[];
  is_holiday?: boolean; // 임시 휴무일
  // 휴무 종류: RECURRING(강사의 정기 휴무일) / TEMPORARY(임시 휴무일) / null(영업일)
  off_type?: "RECURRING" | "TEMPORARY" | null;
}

export interface AvailabilityResponse {
  host_id: string;
  start: string;
  end: string;
  days: AvailabilityDay[];
}

// ── 강사 매칭 ────────────────────────────────────────────────
export type InstructorTier = "NORMAL" | "NAMED";
export type MatchStatus = "PENDING" | "ACCEPTED" | "REJECTED" | "CANCELLED";

export interface InstructorPublicRead {
  id: string;
  display_name: string;
  username: string;
  instructor_tier: InstructorTier;
  match_fee: number;
  is_active: boolean;
  location: string | null;
  specialties: string[];
  bio: string | null;
  career_years?: number | null;
  certifications?: string | null;
}

export type MatchRequestType = "MATCH" | "CONSULTATION";

export interface MatchRequestRead {
  id: string;
  customer_id: string;
  instructor_id: string;
  request_type: MatchRequestType;
  status: MatchStatus;
  fee: number;
  note: string | null;
  instructor_name: string | null;
  customer_name: string | null;
  created_at: string;
  updated_at: string;
}

// ── 강사 게시물 ──────────────────────────────────────────────
export interface MediaItemRead {
  id: number;
  url: string;
  media_type: "IMAGE" | "VIDEO";
  sort_order: number;
}

export type PostType = "PROMOTION" | "NOTICE" | "FEEDBACK" | "COMMUNITY";

export interface InstructorPostRead {
  id: string;
  instructor_id: string;
  created_by_user_id: string | null;
  type: PostType;
  title: string | null;
  content: string | null;
  media_items: MediaItemRead[];
  customer_id: string | null;
  customer_name: string | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  like_count: number;
  comment_count: number;
  is_liked: boolean;
}

// ── 수강권 ────────────────────────────────────────────────────
export interface PassTypeRead {
  id: number;
  instructor_id: string;
  name: string;
  duration_hours: number;
  session_count: number;
  price: number | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InstructorBrief {
  id: string;
  display_name: string;
  instructor_location: string | null;
  instructor_bio: string | null;
  instructor_specialties: string | null;
}

export interface CustomerPassRead {
  id: number;
  pass_type_id: number;
  customer_id: string;
  instructor_id: string;
  pass_name: string;
  duration_hours: number;
  sessions_total: number;
  sessions_used: number;
  sessions_remaining: number;
  price_paid: number | null;
  status: "ACTIVE" | "COMPLETED" | "EXPIRED" | "CANCELLED";
  note: string | null;
  created_at: string;
  updated_at: string;
  instructor: InstructorBrief | null;
  pass_type: PassTypeRead | null;
}

export interface CommentRead {
  id: number;
  post_id: string;
  user_id: string;
  user_name: string | null;
  parent_id: number | null;
  content: string; // 삭제된 댓글이면 "삭제된 댓글입니다"
  created_at: string;
  updated_at: string | null;
  is_deleted: boolean;
}

// 특정 날짜에만 적용되는 예외 (time_slot_id 가 null 이면 그 날 전체)
export interface CalendarBlockRead {
  id: number;
  calendar_id: number;
  start_date: string;
  end_date: string;
  time_slot_id: number | null;
  // CLOSE: 닫기(시간 없으면 임시 휴무일) / OPEN: 정기 휴무일 중 그날 열기
  kind: "CLOSE" | "OPEN";
  reason: string | null;
  created_at: string;
}

// 레슨 노트 (피드백 게시물을 통합, 2026-10-04). file_url 은 첨부 PDF 서명 주소
export interface LessonNoteRead {
  id: string;
  customer_id: string;
  booking_id: number | null;
  instructor_id: string;
  title: string | null;
  content: string | null;
  file_name: string | null;
  file_url: string | null;
  is_shared: boolean;
  customer_name: string | null;
  instructor_name: string | null;
  created_at: string;
  updated_at: string;
}

// 할인·이벤트 프로모션 (프로토타입, 결제 연동 전 안내용)
export interface PromotionRead {
  id: number;
  instructor_id: string;
  pass_type_id: number | null;
  pass_type_name: string | null;
  pass_price: number | null;
  discounted_price: number | null;
  title: string;
  description: string | null;
  discount_type: "PERCENT" | "AMOUNT" | "NONE";
  discount_value: number;
  start_date: string;
  end_date: string;
  is_active: boolean;
  status: "SCHEDULED" | "ONGOING" | "ENDED" | "PAUSED";
  created_at: string;
  updated_at: string;
}
