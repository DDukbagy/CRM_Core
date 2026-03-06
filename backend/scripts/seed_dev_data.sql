-- ============================================================
-- 개발용 테스트 데이터 seed
-- Supabase SQL Editor 또는 psql에서 실행하세요.
-- ============================================================

-- ── 게시물 (PUBLIC) ─────────────────────────────────────────
-- owner: INSTRUCTOR 또는 ADMIN 역할 유저 중 첫 번째
DO $$
DECLARE
  v_owner UUID;
  v_post1 UUID := gen_random_uuid();
  v_post2 UUID := gen_random_uuid();
  v_post3 UUID := gen_random_uuid();
  v_post4 UUID := gen_random_uuid();
  v_post5 UUID := gen_random_uuid();
BEGIN
  SELECT id INTO v_owner
  FROM public.users
  WHERE role IN ('INSTRUCTOR', 'ADMIN')
  ORDER BY created_at
  LIMIT 1;

  IF v_owner IS NULL THEN
    RAISE NOTICE '강사/관리자 계정이 없어 게시물을 생성할 수 없습니다.';
    RETURN;
  END IF;

  INSERT INTO public.posts
    (id, owner_user_id, created_by_user_id, title, caption, post_type, status, is_consent_given, published_at, created_at, updated_at)
  VALUES
    (v_post1, v_owner, v_owner,
     '드라이버 스윙 교정 포인트 3가지',
     '백스윙에서 왼쪽 어깨가 충분히 돌아가지 않는 분들이 많습니다. 오늘은 어깨 회전을 극대화하는 드릴을 소개합니다. 꾸준히 연습하면 비거리가 늘어납니다.',
     'COMMUNITY', 'PUBLIC', true, now(), now(), now()),

    (v_post2, v_owner, v_owner,
     '[공지] 5월 레슨 스케줄 변경 안내',
     '5월 5일(어린이날) 레슨이 휴무입니다. 해당 날짜 예약 고객분들은 일정 재조율 부탁드립니다. 문의는 카카오톡으로 연락해 주세요.',
     'NOTICE', 'PUBLIC', true, now(), now(), now()),

    (v_post3, v_owner, v_owner,
     '퍼팅 거리 감각 기르는 방법',
     '퍼팅에서 방향보다 거리 감각이 훨씬 중요합니다. 눈을 감고 퍼팅하는 연습을 통해 근육 기억을 활성화하세요. 3주만 꾸준히 하면 3퍼팅이 눈에 띄게 줄어듭니다.',
     'COMMUNITY', 'PUBLIC', true, now(), now(), now()),

    (v_post4, v_owner, v_owner,
     '아이언 임팩트 개선 피드백 정리',
     '지난 달 레슨생분들의 공통적인 임팩트 문제를 정리했습니다. 클럽 페이스가 열린 채로 임팩트 되는 경우가 많았는데, 그립을 약하게 쥐는 것이 원인인 경우가 대부분입니다.',
     'FEEDBACK', 'PUBLIC', true, now(), now(), now()),

    (v_post5, v_owner, v_owner,
     '필드 라운드 전 워밍업 루틴',
     '라운드 1시간 전 도착해서 퍼팅 → 어프로치 → 아이언 → 드라이버 순으로 워밍업하는 것을 추천합니다. 대부분의 아마추어는 드라이버부터 치다가 리듬을 잃습니다.',
     'COMMUNITY', 'PUBLIC', true, now(), now(), now());

  RAISE NOTICE '게시물 5개 생성 완료 (owner: %)', v_owner;
END $$;


-- ── 예약 (CUSTOMER → INSTRUCTOR 캘린더) ─────────────────────
DO $$
DECLARE
  v_customer  UUID;
  v_slot_id   INT;
BEGIN
  -- 테스트용 CUSTOMER 계정
  SELECT id INTO v_customer
  FROM public.users
  WHERE role = 'CUSTOMER'
  ORDER BY created_at
  LIMIT 1;

  -- 활성화된 time_slot 중 첫 번째
  SELECT ts.id INTO v_slot_id
  FROM public.time_slots ts
  JOIN public.calendars c ON c.id = ts.calendar_id
  WHERE ts.is_active = true
  LIMIT 1;

  IF v_customer IS NULL THEN
    RAISE NOTICE '고객 계정이 없어 예약을 생성할 수 없습니다.';
    RETURN;
  END IF;

  IF v_slot_id IS NULL THEN
    RAISE NOTICE 'time_slot이 없어 예약을 생성할 수 없습니다. 강사 캘린더를 먼저 설정하세요.';
    RETURN;
  END IF;

  INSERT INTO public.bookings
    ("when", topic, type, status, description, time_slot_id, guest_id, created_at, updated_at)
  VALUES
    (CURRENT_DATE + 3,  '드라이버 비거리 향상', 'LESSON', 'CONFIRMED',  '백스윙 턴 위주로 교정 요청', v_slot_id, v_customer, now(), now()),
    (CURRENT_DATE + 7,  '아이언 임팩트 교정',   'LESSON', 'REQUESTED',  '임팩트 시 뒤땅이 자주 남',   v_slot_id, v_customer, now(), now()),
    (CURRENT_DATE + 14, '퍼팅 루틴 점검',        'LESSON', 'REQUESTED',  null,                          v_slot_id, v_customer, now(), now()),
    (CURRENT_DATE - 7,  '라운드 전 체크',        'LESSON', 'COMPLETED',  '필드 라운드 준비 점검',       v_slot_id, v_customer, now(), now()),
    (CURRENT_DATE - 14, '그립 교정',             'LESSON', 'CANCELLED',  '개인 사정으로 취소',          v_slot_id, v_customer, now(), now());

  RAISE NOTICE '예약 5개 생성 완료 (customer: %, slot: %)', v_customer, v_slot_id;
END $$;
