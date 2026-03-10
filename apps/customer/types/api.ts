// types/api.ts

export type UserRole = "CUSTOMER" | "INSTRUCTOR" | "CONTENT_MANAGER" | "ADMIN";

export interface UserRead {
  id: string;
  email: string;
  username: string;
  display_name: string;
  phone: string | null;
  role: UserRole;
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
  created_at: string;
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
export type BookingType = "LESSON";

export interface BookingRead {
  id: number;
  when: string; // date string YYYY-MM-DD
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

export type PostType = "NOTICE" | "COMMUNITY" | "FEEDBACK";
export type PostStatus = "PUBLIC" | "MEMBERS" | "PRIVATE";

export interface PostMediaResponse {
  id: string;
  url: string;
  media_type: "IMAGE" | "VIDEO";
  sort_order: number;
}

export interface CommentRead {
  id: string;
  post_id: string;
  user_id: string;
  content: string;
  parent_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface PostResponse {
  id: string;
  owner_user_id: string;
  instructor_id: string | null;
  title: string | null;
  caption: string | null;
  post_type: PostType;
  status: PostStatus;
  is_consent_given: boolean;
  when: string | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  media: PostMediaResponse[];
  like_count: number;
  comment_count: number;
  is_liked: boolean;
}
