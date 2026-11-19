"""부하 테스트용 더미 데이터: 로컬 Postgres 에만 넣는다

- 강사 20명, 고객 500명(강사마다 25명 담당), 수강권 약 700개, 예약 약 1만 건(지난 90일 + 앞으로 30일)
- 현실적인 분포: 지난 예약은 완료·노쇼·취소, 앞으로의 예약은 신청·확정·취소요청, 정기 휴무(일요일)·임시 휴무, 소진·만료된 수강권
- 고정 seed 라 같은 날 다시 실행하면 같은 상태가 된다 (날짜는 실행한 날의 한국 날짜 기준)
- 사람 ID 는 번호로 정해진다 (loadtest/people.py). locustfile.py 가 같은 ID 로 토큰을 만든다

실행: make loadseed  (DB 를 지우고 새로 만든 뒤 넣는다)
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.domains.booking.models import Booking  # noqa: E402
from app.domains.calendar.models import Calendar, CalendarBlock, TimeSlot  # noqa: E402
from app.domains.passes.models import CustomerPass, LessonPassType  # noqa: E402
from app.domains.users.models import User  # noqa: E402
from people import CUSTOMERS_PER_INSTRUCTOR, N_INSTRUCTORS, SLOT_HOURS, customer_id, instructor_id  # noqa: E402

PAST_DAYS = 90
FUTURE_DAYS = 30
BOOKED_RATIO = 0.6  # 열려 있는 슬롯 중 예약이 잡힌 비율
SEED = 42

KST = ZoneInfo("Asia/Seoul")


def _db_url() -> str:
    url = os.environ["DATABASE_URL"]
    if "127.0.0.1" not in url and "localhost" not in url:
        raise SystemExit("로컬 DB 에만 넣습니다 (DATABASE_URL 이 로컬이 아님)")
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def build(today: date) -> dict[str, list[dict]]:
    rnd = random.Random(SEED)
    now = datetime.now(timezone.utc)
    rows: dict[str, list[dict]] = defaultdict(list)

    def ts(d: date) -> datetime:
        return datetime.combine(d, time(9), tzinfo=KST)

    slot_id = 0
    pass_id = 0
    for i in range(N_INSTRUCTORS):
        host = instructor_id(i)
        rows["users"].append(dict(
            id=host, username=f"load_host_{i:02d}", email=f"load-host-{i:02d}@example.com",
            display_name=f"강사{i:02d}", role="INSTRUCTOR", status="ACTIVE",
            recurring_off_days=[6], created_at=now, updated_at=now,
        ))
        cal_id = i + 1
        rows["calendars"].append(dict(
            id=cal_id, topics=["스윙", "퍼팅"], description=f"강사{i:02d} 레슨", host_id=host,
            created_at=now, updated_at=now,
        ))
        slots = []
        for h in SLOT_HOURS:
            slot_id += 1
            # 대부분 월~토, 일부 강사는 수요일 오후를 비운다
            weekdays = [0, 1, 3, 4, 5] if (i % 4 == 0 and h >= 13) else [0, 1, 2, 3, 4, 5]
            rows["time_slots"].append(dict(
                id=slot_id, start_time=time(h), end_time=time(h + 1), weekdays=weekdays,
                is_active=True, calendar_id=cal_id, created_at=now, updated_at=now,
            ))
            slots.append((slot_id, set(weekdays)))

        # 임시 휴무: 강사마다 2~4일 (지난날·앞날 섞어서)
        closed: set[date] = set()
        for _ in range(rnd.randint(2, 4)):
            d = today + timedelta(days=rnd.randint(-PAST_DAYS, FUTURE_DAYS))
            closed.add(d)
            rows["calendar_blocks"].append(dict(
                calendar_id=cal_id, start_date=d, end_date=d, time_slot_id=None,
                kind="CLOSE", reason="개인 사정", created_at=now, updated_at=now,
            ))

        for p, (name, count, price) in enumerate([("10회권", 10, 500_000), ("20회권", 20, 900_000)]):
            rows["lesson_pass_types"].append(dict(
                id=i * 2 + p + 1, instructor_id=host, name=name, duration_hours=1,
                session_count=count, price=price, is_active=True, created_at=now, updated_at=now,
            ))

        customers = [i * CUSTOMERS_PER_INSTRUCTOR + c for c in range(CUSTOMERS_PER_INSTRUCTOR)]
        for c in customers:
            rows["users"].append(dict(
                id=customer_id(c), username=f"load_cust_{c:03d}", email=f"load-cust-{c:03d}@example.com",
                display_name=f"고객{c:03d}", role="CUSTOMER", status="ACTIVE", manager_id=host,
                created_at=now, updated_at=now,
            ))

        used: dict[int, int] = defaultdict(int)  # 고객별 차감된 횟수 (완료 + 노쇼)
        active: dict[int, list[dict]] = defaultdict(list)  # 고객별 진행 중 예약 (수강권을 고정해야 함)
        for offset in range(-PAST_DAYS, FUTURE_DAYS + 1):
            d = today + timedelta(days=offset)
            if d in closed or d.weekday() == 6:
                continue
            for sid, wds in slots:
                if d.weekday() not in wds or rnd.random() >= BOOKED_RATIO:
                    continue
                c = rnd.choice(customers)
                r = rnd.random()
                if offset < 0:
                    status = "COMPLETED" if r < 0.80 else "NO_SHOW" if r < 0.85 else "CANCELLED"
                else:
                    status = "CONFIRMED" if r < 0.60 else "REQUESTED" if r < 0.90 else "CANCEL_REQUESTED" if r < 0.95 else "CANCELLED"
                if status in ("COMPLETED", "NO_SHOW"):
                    used[c] += 1
                created = ts(d - timedelta(days=rnd.randint(1, 14)))
                row = dict(
                    when=d, topic="레슨", type="LESSON", status=status,
                    cancel_reason="일정 변경" if status == "CANCELLED" else None,
                    time_slot_id=sid, guest_id=customer_id(c), created_at=created, updated_at=created,
                )
                rows["bookings"].append(row)
                if status in ("REQUESTED", "CONFIRMED", "CANCEL_REQUESTED"):
                    active[c].append(row)

        # 수강권: 차감된 횟수를 앞 수강권부터 채운다. 다 쓴 것은 COMPLETED, 마지막 것은 남은 횟수가 있는 ACTIVE.
        # 진행 중 예약은 마지막(ACTIVE) 수강권에 고정하고, 그 수강권의 남은 횟수가 진행 중 예약 수 이상이 되게 한다
        # (예약할 때 "남은 횟수 − 진행 중 예약 수 > 0" 을 확인하므로)
        for c in customers:
            left = used[c]
            k = 0
            while True:
                p = rnd.choice([0, 1])
                count = (10, 20)[p]
                take = min(left, count)
                left -= take
                done = take == count
                if left == 0 and not done:
                    count = max(count, take + len(active[c]))  # 마지막 수강권: 진행 중 예약을 모두 받을 만큼
                pass_id += 1
                if left == 0 and not done:
                    for row in active[c]:
                        row["customer_pass_id"] = pass_id
                rows["customer_passes"].append(dict(
                    id=pass_id, pass_type_id=i * 2 + p + 1, customer_id=customer_id(c), instructor_id=host,
                    pass_name=("10회권", "20회권")[p], duration_hours=1, sessions_total=count,
                    sessions_used=take, price_paid=(500_000, 900_000)[p],
                    status="COMPLETED" if done else "ACTIVE",
                    created_at=ts(today - timedelta(days=PAST_DAYS + 7 - k * 30)), updated_at=now,
                ))
                k += 1
                if left == 0 and not done:
                    break
            # 고객 10명 중 1명은 예전에 기간이 끝난 수강권이 하나 더 있다
            if rnd.random() < 0.1:
                pass_id += 1
                rows["customer_passes"].append(dict(
                    id=pass_id, pass_type_id=i * 2 + 1, customer_id=customer_id(c), instructor_id=host,
                    pass_name="10회권", duration_hours=1, sessions_total=10, sessions_used=rnd.randint(3, 8),
                    price_paid=500_000, status="EXPIRED", created_at=ts(today - timedelta(days=200)), updated_at=now,
                ))
    return rows


TABLES = [
    ("users", User), ("calendars", Calendar), ("time_slots", TimeSlot), ("calendar_blocks", CalendarBlock),
    ("lesson_pass_types", LessonPassType), ("customer_passes", CustomerPass), ("bookings", Booking),
]


async def main() -> None:
    today = datetime.now(KST).date()
    rows = build(today)
    engine = create_async_engine(_db_url(), connect_args={"ssl": None})
    async with engine.begin() as conn:
        for name, model in TABLES:
            data = rows[name]
            # 한 번에 넣는 행들은 칸이 같아야 한다 (강사만 가진 칸·고객만 가진 칸은 None 으로 채운다)
            keys = {k for r in data for k in r}
            data = [{k: r.get(k) for k in keys} for r in data]
            for start in range(0, len(data), 2000):
                await conn.execute(insert(model.__table__), data[start:start + 2000])
        # id 를 직접 넣은 표는 다음 번호를 맞춘다 (부하 테스트 중 새 행이 겹치지 않게)
        for table in ("calendars", "time_slots", "lesson_pass_types", "customer_passes"):
            await conn.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT max(id) FROM {table}))"
            ))
        await conn.execute(text("ANALYZE"))
    await engine.dispose()
    print(f"기준일 {today} (한국 날짜)")
    for name, _ in TABLES:
        print(f"  {name}: {len(rows[name])}")


if __name__ == "__main__":
    asyncio.run(main())
