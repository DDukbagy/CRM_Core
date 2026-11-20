"""부하 시나리오: 고객이 강사의 빈 시간을 보고 예약하고, 강사는 예약 목록을 본다

- 사람은 loadtest/seed.py 가 넣은 고객 500명·강사 20명 중에서 고른다. 토큰은 make apiverify 처럼 로컬 더미 비밀값으로 직접 서명한다
- 조회가 쓰기보다 훨씬 자주 일어나도록 비중(@task 숫자)을 둔다
- 실행: make apiload 가 부른다
"""
from __future__ import annotations

import os
import random
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from jose import jwt
from locust import HttpUser, between, task # type: ignore[import]

sys.path.insert(0, os.path.dirname(__file__))
from people import CUSTOMERS_PER_INSTRUCTOR, N_INSTRUCTORS, SLOT_HOURS, customer_id, instructor_id  # noqa: E402

KST = ZoneInfo("Asia/Seoul")


def _token(sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub, "email": email, "aud": os.environ["SUPABASE_JWT_AUDIENCE"],
            "iss": os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1", "iat": now, "exp": now + 3 * 3600,
        },
        os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256",
    )


def _today() -> date:
    return datetime.now(KST).date()


class Customer(HttpUser):
    """고객 앱: 담당 강사 빈 시간 조회 → 가끔 예약, 내 예약·수강권 확인"""

    weight = 4
    wait_time = between(0.5, 1.5)

    def on_start(self) -> None:
        n = random.randrange(N_INSTRUCTORS * CUSTOMERS_PER_INSTRUCTOR)
        self.host_id = str(instructor_id(n // CUSTOMERS_PER_INSTRUCTOR))
        # 시간 슬롯 id: 강사 i 의 슬롯은 i*8+1 ~ i*8+8 (seed.py 가 순서대로 넣음)
        first = (n // CUSTOMERS_PER_INSTRUCTOR) * len(SLOT_HOURS) + 1
        self.slot_ids = list(range(first, first + len(SLOT_HOURS)))
        self.client.headers["Authorization"] = f"Bearer {_token(str(customer_id(n)), f'load-cust-{n:03d}@example.com')}"

    # 비중: 빈 시간 조회가 가장 잦고, 예약 생성(쓰기)은 드물다
    @task(5)
    def availability(self) -> None:
        start = _today()
        self.client.get(
            f"/calendars/{self.host_id}/availability",
            params={"start": start.isoformat(), "end": (start + timedelta(days=13)).isoformat()},
            name="GET /calendars/{host}/availability",
        )

    @task(3)
    def my_bookings(self) -> None:
        self.client.get("/bookings/me", name="GET /bookings/me")

    @task(2)
    def my_passes(self) -> None:
        self.client.get("/passes/me", name="GET /passes/me")

    @task(1)
    def create_booking(self) -> None:
        when = _today() + timedelta(days=random.randint(1, 30))
        body = {"time_slot_ids": [random.choice(self.slot_ids)], "when": when.isoformat(), "topic": "부하 테스트"}
        with self.client.post("/bookings", json=body, name="POST /bookings", catch_response=True) as res:
            # 빈 시간을 고르지 않고 아무 날짜·슬롯이나 고르므로, 이미 찬 시간(409)이나 휴무일(400)도 정상적인 거절이다
            # 예상한 코드만 성공으로 센다. 서버 오류(5xx)나 예상 못 한 코드는 실패 → 실패율이 진짜 이상을 잡는다
            if res.status_code in (201, 400, 409):
                res.success()
            else:
                res.failure(f"Unexpected status code: {res.status_code}")


class Instructor(HttpUser):
    """강사 앱·웹: 이번 주 예약 목록과 내 시간 슬롯"""

    weight = 1
    wait_time = between(0.5, 1.5)

    def on_start(self) -> None:
        i = random.randrange(N_INSTRUCTORS)
        self.client.headers["Authorization"] = f"Bearer {_token(str(instructor_id(i)), f'load-host-{i:02d}@example.com')}"

    @task(3)
    def week_bookings(self) -> None:
        start = _today()
        self.client.get(
            "/calendars/me/bookings",
            params={"start": start.isoformat(), "end": (start + timedelta(days=6)).isoformat()},
            name="GET /calendars/me/bookings",
        )

    @task(1)
    def my_slots(self) -> None:
        self.client.get("/calendars/me/time-slots", name="GET /calendars/me/time-slots")
