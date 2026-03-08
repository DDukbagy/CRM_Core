-- ============================================================
-- 개발용 테스트 데이터 seed
-- Supabase SQL Editor 또는 psql에서 실행하세요.
-- 멱등성: 이미 데이터가 있으면 건너뜁니다.
-- ============================================================


-- ── 1. 게시물 ────────────────────────────────────────────────
DO $$
DECLARE
  v_owner UUID;
  v_post1 UUID := gen_random_uuid();
  v_post2 UUID := gen_random_uuid();
  v_post3 UUID := gen_random_uuid();
  v_post4 UUID := gen_random_uuid();
  v_post5 UUID := gen_random_uuid();
  v_post6 UUID := gen_random_uuid();
  v_post7 UUID := gen_random_uuid();
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

  -- 이미 게시물이 충분하면 스킵
  IF (SELECT COUNT(*) FROM public.posts WHERE owner_user_id = v_owner) >= 5 THEN
    RAISE NOTICE '게시물이 이미 있습니다. 스킵합니다.';
    RETURN;
  END IF;

  INSERT INTO public.posts
    (id, owner_user_id, created_by_user_id, title, caption, post_type, status, is_consent_given, published_at, created_at, updated_at)
  VALUES
    -- 커뮤니티
    (v_post1, v_owner, v_owner,
     '드라이버 스윙 교정 포인트 3가지',
     '백스윙에서 왼쪽 어깨가 충분히 돌아가지 않는 분들이 많습니다. 오늘은 어깨 회전을 극대화하는 드릴을 소개합니다. 꾸준히 연습하면 비거리가 늘어납니다.',
     'COMMUNITY', 'PUBLIC', true, now() - interval '6 days', now() - interval '6 days', now()),

    -- 공지
    (v_post2, v_owner, v_owner,
     '[공지] 6월 레슨 스케줄 변경 안내',
     '6월 6일(현충일) 레슨이 휴무입니다. 해당 날짜 예약 고객분들은 일정 재조율 부탁드립니다. 문의는 카카오톡으로 연락해 주세요.',
     'NOTICE', 'PUBLIC', true, now() - interval '5 days', now() - interval '5 days', now()),

    -- 커뮤니티
    (v_post3, v_owner, v_owner,
     '퍼팅 거리 감각 기르는 방법',
     '퍼팅에서 방향보다 거리 감각이 훨씬 중요합니다. 눈을 감고 퍼팅하는 연습을 통해 근육 기억을 활성화하세요. 3주만 꾸준히 하면 3퍼팅이 눈에 띄게 줄어듭니다.',
     'COMMUNITY', 'PUBLIC', true, now() - interval '4 days', now() - interval '4 days', now()),

    -- 피드백
    (v_post4, v_owner, v_owner,
     '아이언 임팩트 개선 피드백 정리',
     '지난 달 레슨생분들의 공통적인 임팩트 문제를 정리했습니다. 클럽 페이스가 열린 채로 임팩트 되는 경우가 많았는데, 그립을 약하게 쥐는 것이 원인인 경우가 대부분입니다.',
     'FEEDBACK', 'PUBLIC', true, now() - interval '2 days', now() - interval '2 days', now()),

    -- 커뮤니티
    (v_post5, v_owner, v_owner,
     '필드 라운드 전 워밍업 루틴',
     '라운드 1시간 전 도착해서 퍼팅 → 어프로치 → 아이언 → 드라이버 순으로 워밍업하는 것을 추천합니다. 대부분의 아마추어는 드라이버부터 치다가 리듬을 잃습니다.',
     'COMMUNITY', 'PUBLIC', true, now() - interval '1 day', now() - interval '1 day', now()),

    -- 커뮤니티
    (v_post6, v_owner, v_owner,
     '하체 고정이 비거리를 만든다',
     '스윙 중 하체가 흔들리면 파워가 분산됩니다. 어드레스 때 발바닥 전체를 지면에 밀착하고, 다운스윙에서 왼 무릎이 흔들리지 않도록 의식적으로 고정해보세요. 비거리가 달라집니다.',
     'COMMUNITY', 'PUBLIC', true, now() - interval '12 hours', now() - interval '12 hours', now()),

    -- 공지
    (v_post7, v_owner, v_owner,
     '[안내] 레슨 예약 앱 업데이트',
     '앱이 업데이트되어 이제 원하는 날짜와 시간을 직접 선택해서 예약할 수 있습니다. 아직 담당 강사가 없으신 분들은 강사 매칭 탭을 이용해 주세요.',
     'NOTICE', 'PUBLIC', true, now(), now(), now());

  -- 이미지 첨부
  INSERT INTO public.post_media (post_id, media_type, url, s3_key_source, sort_order)
  VALUES
    (v_post1, 'IMAGE', 'https://images.unsplash.com/photo-1535131749006-b7f58c99034b?w=800', 'seed/golf-driver-swing.jpg', 0),
    (v_post3, 'IMAGE', 'https://images.unsplash.com/photo-1622673038559-a6b1c7e2cf16?w=800', 'seed/golf-putting.jpg', 0),
    (v_post5, 'IMAGE', 'https://images.unsplash.com/photo-1587174486073-ae5e5cff23aa?w=800', 'seed/golf-course.jpg', 0),
    (v_post6, 'IMAGE', 'https://images.unsplash.com/photo-1593111774240-d529f12cf4bb?w=800', 'seed/golf-iron.jpg', 0);

  RAISE NOTICE '게시물 7개 + 이미지 4개 생성 완료 (owner: %)', v_owner;
END $$;


-- ── 2. 강사 프로필 업데이트 ──────────────────────────────────
DO $$
DECLARE
  v_instrs UUID[];
BEGIN
  SELECT array_agg(id ORDER BY created_at)
  INTO v_instrs
  FROM public.users
  WHERE role = 'INSTRUCTOR' AND is_active = true;

  IF v_instrs IS NULL THEN
    RAISE NOTICE '강사 계정이 없습니다.';
    RETURN;
  END IF;

  -- 첫 번째 강사: Named / 서울
  IF array_length(v_instrs, 1) >= 1 THEN
    UPDATE public.users SET
      instructor_tier         = 'NAMED',
      instructor_location     = '서울',
      instructor_specialties  = '스윙 교정,비거리 향상,초보자 맞춤',
      instructor_bio          = '10년 경력 KPGA 정회원 프로. 체계적인 스윙 분석과 영상 피드백으로 빠른 실력 향상을 도와드립니다.'
    WHERE id = v_instrs[1];
  END IF;

  -- 두 번째 강사: Normal / 경기 (있다면)
  IF array_length(v_instrs, 1) >= 2 THEN
    UPDATE public.users SET
      instructor_tier         = 'NORMAL',
      instructor_location     = '경기',
      instructor_specialties  = '퍼팅,코스 매니지먼트,멘탈 코칭',
      instructor_bio          = '필드 라운드 중심의 실전 레슨 전문. 스코어를 빠르게 줄이고 싶은 분께 추천합니다.'
    WHERE id = v_instrs[2];
  END IF;

  -- 세 번째 강사: Normal / 부산 (있다면)
  IF array_length(v_instrs, 1) >= 3 THEN
    UPDATE public.users SET
      instructor_tier         = 'NORMAL',
      instructor_location     = '부산',
      instructor_specialties  = '비거리 향상,스윙 교정',
      instructor_bio          = '부산/경남 지역 레슨 전문. 야외 필드 위주의 실전 레슨을 진행합니다.'
    WHERE id = v_instrs[3];
  END IF;

  RAISE NOTICE '강사 프로필 업데이트 완료 (%명)', array_length(v_instrs, 1);
END $$;


-- ── 3. 캘린더 + 타임슬롯 + 고객 매핑 + 예약 ────────────────
DO $$
DECLARE
  v_instr     UUID;
  v_customer  UUID;
  v_cal_id    INT;
  v_slot1     INT;
  v_slot2     INT;
  v_slot3     INT;
BEGIN
  -- 첫 번째 강사
  SELECT id INTO v_instr
  FROM public.users
  WHERE role = 'INSTRUCTOR' AND is_active = true
  ORDER BY created_at
  LIMIT 1;

  -- 첫 번째 고객
  SELECT id INTO v_customer
  FROM public.users
  WHERE role = 'CUSTOMER' AND is_active = true
  ORDER BY created_at
  LIMIT 1;

  IF v_instr IS NULL THEN
    RAISE NOTICE '강사 계정이 없습니다.'; RETURN;
  END IF;

  IF v_customer IS NULL THEN
    RAISE NOTICE '고객 계정이 없습니다.'; RETURN;
  END IF;

  -- 캘린더 생성 (없으면)
  INSERT INTO public.calendars (host_id, topics, description, created_at, updated_at)
  VALUES (
    v_instr,
    '["드라이버", "아이언", "퍼팅", "어프로치", "번커샷"]',
    '체계적인 스윙 분석과 영상 피드백으로 빠른 실력 향상을 도와드립니다. 초보부터 싱글까지 맞춤 레슨 진행.',
    now(), now()
  )
  ON CONFLICT (host_id) DO NOTHING;

  SELECT id INTO v_cal_id
  FROM public.calendars
  WHERE host_id = v_instr;

  IF v_cal_id IS NULL THEN
    RAISE NOTICE '캘린더 생성 실패'; RETURN;
  END IF;

  -- 타임슬롯 생성 (각 시간대별로 없으면 추가)
  -- weekdays 0=월 1=화 2=수 3=목 4=금 5=토 6=일 (Python weekday() 기준)
  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '07:00', '08:00', '[1,3,4,5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '07:00:00');

  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '09:00', '10:00', '[1,3,4,5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '09:00:00');

  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '10:00', '11:00', '[1,3,4,5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '10:00:00');

  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '11:00', '12:00', '[1,3,4,5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '11:00:00');

  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '13:00', '14:00', '[1,3,4,5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '13:00:00');

  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '14:00', '15:00', '[1,3,4,5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '14:00:00');

  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '15:00', '16:00', '[1,3,4,5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '15:00:00');

  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '16:00', '17:00', '[1,3,4,5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '16:00:00');

  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '18:00', '19:00', '[1,3,4,5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '18:00:00');

  INSERT INTO public.time_slots (calendar_id, start_time, end_time, weekdays, is_active, created_at, updated_at)
  SELECT v_cal_id, '19:00', '20:00', '[5,6]'::jsonb, true, now(), now()
  WHERE NOT EXISTS (SELECT 1 FROM public.time_slots WHERE calendar_id = v_cal_id AND start_time = '19:00:00');

  RAISE NOTICE '타임슬롯 확인/추가 완료 (calendar: %)', v_cal_id;

  -- 슬롯 ID 조회
  SELECT id INTO v_slot1 FROM public.time_slots WHERE calendar_id = v_cal_id ORDER BY start_time LIMIT 1 OFFSET 0;
  SELECT id INTO v_slot2 FROM public.time_slots WHERE calendar_id = v_cal_id ORDER BY start_time LIMIT 1 OFFSET 1;
  SELECT id INTO v_slot3 FROM public.time_slots WHERE calendar_id = v_cal_id ORDER BY start_time LIMIT 1 OFFSET 2;

  -- 고객의 담당 강사 설정
  UPDATE public.users
  SET manager_id = v_instr
  WHERE id = v_customer AND (manager_id IS NULL OR manager_id = v_instr);

  -- 예약 생성 (없으면)
  IF NOT EXISTS (SELECT 1 FROM public.bookings WHERE guest_id = v_customer) THEN
    INSERT INTO public.bookings
      ("when", topic, type, status, description, time_slot_id, guest_id, created_at, updated_at)
    VALUES
      -- 미래 예약
      (CURRENT_DATE + 2,  '드라이버 비거리 향상',  'LESSON', 'CONFIRMED',
       '백스윙 턴 위주로 교정 요청. 지난 라운드에서 슬라이스가 심했음.',
       v_slot1, v_customer, now(), now()),

      (CURRENT_DATE + 5,  '아이언 임팩트 교정',    'LESSON', 'REQUESTED',
       '임팩트 시 뒤땅이 자주 남. 체중이동 패턴 점검 요청.',
       v_slot2, v_customer, now(), now()),

      (CURRENT_DATE + 9,  '퍼팅 루틴 점검',        'LESSON', 'REQUESTED',
       null,
       v_slot1, v_customer, now(), now()),

      (CURRENT_DATE + 14, '번커샷 집중 연습',       'LESSON', 'REQUESTED',
       '필드에서 번커가 제일 어렵습니다. 집중 레슨 부탁드립니다.',
       v_slot3, v_customer, now(), now()),

      -- 과거 완료 예약
      (CURRENT_DATE - 3,  '어드레스 & 셋업 점검',  'LESSON', 'COMPLETED',
       '스탠스 너비와 볼 포지션 교정. 큰 개선 있었음.',
       v_slot2, v_customer, now() - interval '3 days', now()),

      (CURRENT_DATE - 8,  '하체 회전 드릴',         'LESSON', 'COMPLETED',
       '하체 고정 후 상체 회전 극대화 훈련. 비거리 10야드 향상.',
       v_slot1, v_customer, now() - interval '8 days', now()),

      (CURRENT_DATE - 15, '첫 번째 진단 레슨',      'LESSON', 'COMPLETED',
       '전반적인 스윙 진단 및 교정 방향 설정.',
       v_slot2, v_customer, now() - interval '15 days', now()),

      -- 취소된 예약 (unique constraint 대상 아님)
      (CURRENT_DATE - 22, '그립 교정',              'LESSON', 'CANCELLED',
       '개인 사정으로 취소.',
       v_slot1, v_customer, now() - interval '22 days', now());

    RAISE NOTICE '예약 8개 생성 완료 (customer: %, slot1: %, slot2: %, slot3: %)',
      v_customer, v_slot1, v_slot2, v_slot3;
  ELSE
    RAISE NOTICE '예약이 이미 있습니다. 스킵합니다.';
  END IF;

END $$;
