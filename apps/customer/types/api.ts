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
  created_at: string;
}

export interface UserUpdate {
  display_name?: string;
  username?: string;
  phone?: string;
}

export type BookingStatus = "REQUESTED" | "CONFIRMED" | "CANCELLED" | "COMPLETED";
export type BookingType = "LESSON" | "CONSULTATION";

export interface BookingRead {
  id: number;
  when: string; // date string YYYY-MM-DD
  topic: string;
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
  topic: string;
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

export type PostType = "NOTICE" | "COMMUNITY" | "FEEDBACK";
export type PostStatus = "PUBLIC" | "MEMBERS" | "PRIVATE";

export interface PostMediaResponse {
  id: string;
  url: string;
  media_type: "IMAGE" | "VIDEO";
  sort_order: number;
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
