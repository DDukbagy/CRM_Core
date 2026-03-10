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

export interface BookingRead {
  id: number;
  when: string;
  topic: string | null;
  description: string | null;
  status: string;
  type: string;
  guest_id: string;
  time_slot_id: number;
  membership_id: string | null;
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

export interface PostRead {
  id: string;
  instructor_id: string;
  type: "PROMOTION" | "FEEDBACK";
  title: string | null;
  content: string | null;
  media_url: string | null;
  customer_id: string | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface UsersListResponse {
  items: UserRead[];
  total: number;
  limit: number;
  offset: number;
}
