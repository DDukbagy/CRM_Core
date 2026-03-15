export interface UserRead {
  id: string;
  username: string;
  email: string | null;
  display_name: string;
  phone: string | null;
  role: string;
  status: string;
  is_active: boolean;
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
  feedback_consent: boolean;
  recurring_off_days: number[];
  created_at: string;
  updated_at: string;
}

export interface MembershipRead {
  id: string;
  customer_id: string;
  instructor_id: string;
  type: "TIMES" | "PERIOD";
  total_count: number | null;
  remaining_count: number | null;
  started_at: string | null;
  expires_at: string | null;
  is_active: boolean;
  notes: string | null;
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
  membership_id: string | null;
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

export interface PaymentRead {
  id: string;
  customer_id: string;
  membership_id: string | null;
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

export interface PostRead {
  id: string;
  instructor_id: string;
  type: "PROMOTION" | "FEEDBACK";
  title: string | null;
  content: string | null;
  media_items: MediaItemRead[];
  customer_id: string | null;
  customer_name: string | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface CommentRead {
  id: number;
  post_id: string;
  user_id: string;
  user_name: string | null;
  content: string;
  created_at: string;
}

export interface UsersListResponse {
  items: UserRead[];
  total: number;
  limit: number;
  offset: number;
}
