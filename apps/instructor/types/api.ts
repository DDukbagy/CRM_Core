export interface UserRead {
  id: string;
  username: string;
  email: string | null;
  display_name: string;
  phone: string | null;
  role: string;
  status: string; // ACTIVE | PENDING | SUSPENDED | WITHDRAWN(탈퇴)
  is_active: boolean;
  withdrawn_at?: string | null; // 탈퇴 처리 시각
  manager_id: string | null;
  instructor_tier: string | null;
  instructor_location: string | null;
  instructor_specialties: string | null;
  instructor_bio: string | null;
  career_years: number | null;
  certifications: string | null;
  birth_date: string | null;
  gender: string | null;
  lesson_purpose: string | null;
  recurring_off_days: number[];
  created_at: string;
  updated_at: string;
}

export type BookingStatus = "REQUESTED" | "CONFIRMED" | "CANCEL_REQUESTED" | "CANCELLED" | "COMPLETED" | "NO_SHOW";
export type BookingType = "LESSON" | "HOLIDAY" | "WORK_OVERRIDE";

export interface BookingRead {
  id: number;
  when: string;
  topic: string | null;
  description: string | null;
  status: BookingStatus;
  type: BookingType;
  guest_id: string;
  time_slot_id: number;
  cancel_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimeSlotRead {
  id: number;
  calendar_id: number;
  start_time: string;
  end_time: string;
  weekdays: number[];
  is_active: boolean;
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

export interface PaymentRead {
  id: string;
  customer_id: string;
  amount: number;
  method: string;
  status: string;
  pg_payment_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface InstructorStats {
  customer_count: number;
  booking_counts: {
    total: number;
    completed: number;
    no_show: number;
    confirmed: number;
    requested: number;
    cancelled: number;
  };
  attendance_rate: number | null;
}

export interface MediaItemRead {
  id: number;
  url: string;
  media_type: "IMAGE" | "VIDEO";
  sort_order: number;
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
  customer_name: string | null;
}

export type PostType = "PROMOTION" | "NOTICE" | "FEEDBACK" | "COMMUNITY";

export interface PostRead {
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

export interface UsersListResponse {
  items: UserRead[];
  total: number;
  limit: number;
  offset: number;
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

// 강사 매출·운영 대시보드 (GET /instructors/me/dashboard)
export interface InstructorDashboard {
  months: { month: string; amount: number; count: number }[];
  this_month: number;
  last_month: number;
  period_total: number;
  by_method: { method: string; amount: number }[];
  by_pass: { pass_name: string; amount: number }[];
  customers: { total: number; new_this_month: number };
  passes: { active: number; remaining_sessions: number; completed: number };
  lessons_completed_this_month: number;
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
