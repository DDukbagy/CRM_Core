from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domains.booking.models import Booking
from app.domains.calendar.models import Calendar, TimeSlot
from app.domains.calendar.repository import CalendarRepository
from app.domains.passes.repository import PassRepository
from app.domains.payment.repository import PaymentRepository
from app.domains.instructor.models import InstructorStaff
from app.domains.users.models import User


def _attendance(counts: dict[str, int]) -> dict:
    """상태별 예약 수 → 응답용 집계 + 출석률(완료 / (완료 + 노쇼), 데이터 없으면 None)"""
    completed = counts.get("COMPLETED", 0)
    no_show = counts.get("NO_SHOW", 0)
    attended_base = completed + no_show
    return {
        "booking_counts": {
            "total": sum(counts.values()),
            "completed": completed,
            "no_show": no_show,
            "confirmed": counts.get("CONFIRMED", 0),
            "requested": counts.get("REQUESTED", 0),
            "cancelled": counts.get("CANCELLED", 0),
        },
        "attendance_rate": round(completed / attended_base * 100, 1) if attended_base > 0 else None,
    }


class InstructorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 스태프 (콘텐츠 매니저 등 대리 작성자) ─────────────────────────────────

    async def add_staff(self, instructor_id: UUID, staff_email: str) -> None:
        staff_user = (await self.session.execute(select(User).where(User.email == staff_email))).scalar_one_or_none()
        if not staff_user:
            raise HTTPException(status_code=404, detail="Staff user not found")
        if staff_user.id == instructor_id:
            raise HTTPException(status_code=400, detail="Cannot add yourself as staff")
        try:
            self.session.add(InstructorStaff(instructor_id=instructor_id, staff_user_id=staff_user.id))
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Staff already assigned")

    async def remove_staff(self, instructor_id: UUID, staff_user_id: UUID) -> None:
        entry = (
            await self.session.execute(
                select(InstructorStaff).where(
                    and_(InstructorStaff.instructor_id == instructor_id, InstructorStaff.staff_user_id == staff_user_id)
                )
            )
        ).scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="Staff relation not found")
        await self.session.delete(entry)
        await self.session.commit()

    async def list_staff(self, instructor_id: UUID) -> list:
        res = await self.session.execute(
            select(
                InstructorStaff.staff_user_id,
                InstructorStaff.created_at,
                User.email,
                User.username,
                User.display_name,
            )
            .join(User, User.id == InstructorStaff.staff_user_id)
            .where(InstructorStaff.instructor_id == instructor_id)
            .order_by(InstructorStaff.created_at.desc())
        )
        return list(res)

    # ── 강사 신청·승인 ───────────────────────────────────────────────────────

    async def apply(self, user_id: UUID) -> User:
        """CUSTOMER → INSTRUCTOR(PENDING). 이미 강사면 그대로"""
        db_user = (await self.session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        role = (db_user.role or "").upper()
        if role == "INSTRUCTOR":
            return db_user
        if role != "CUSTOMER":
            raise HTTPException(status_code=400, detail="Invalid role transition")
        db_user.role = "INSTRUCTOR"
        db_user.status = "PENDING"
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user

    async def list_pending(self) -> list[User]:
        res = await self.session.execute(
            select(User)
            .where(and_(User.role == "INSTRUCTOR", User.status == "PENDING", User.is_active == True))  # noqa: E712
            .order_by(User.created_at.asc())
        )
        return list(res.scalars().all())

    async def approve(self, user_id: UUID) -> User:
        if settings.SUPER_ADMIN_USER_ID and str(user_id) == str(settings.SUPER_ADMIN_USER_ID):
            raise HTTPException(status_code=403, detail="Cannot modify super admin")
        target = (
            await self.session.execute(select(User).where(and_(User.id == user_id, User.role == "INSTRUCTOR")))
        ).scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="Pending instructor not found")
        target.status = "ACTIVE"
        self.session.add(target)
        await self.session.commit()
        # 승인된 강사는 기본 캘린더(매일 07~20시 1시간 슬롯)를 바로 쓸 수 있어야 한다
        await CalendarRepository(self.session).ensure_default(target.id)
        await self.session.refresh(target)
        return target

    # ── 공개 목록 ────────────────────────────────────────────────────────────

    async def list_public(
        self, location: Optional[str], specialty: Optional[str], name: Optional[str]
    ) -> list[tuple[User, list[str]]]:
        """승인된 활성 강사 (NAMED 우선, 이름순). specialty 는 콤마 문자열이라 Python 에서 거른다"""
        conditions = [User.role == "INSTRUCTOR", User.status == "ACTIVE", User.is_active == True]  # noqa: E712
        if location:
            conditions.append(User.instructor_location == location)
        if name:
            conditions.append(User.display_name.ilike(f"%{name}%"))
        instructors = (
            await self.session.execute(
                select(User).where(and_(*conditions)).order_by((User.instructor_tier != "NAMED").asc(), User.display_name.asc())
            )
        ).scalars().all()

        result = []
        for u in instructors:
            specialties = [s.strip() for s in (u.instructor_specialties or "").split(",") if s.strip()]
            if specialty and specialty not in specialties:
                continue
            result.append((u, specialties))
        return result

    # ── 고객 조회·담당 등록 ──────────────────────────────────────────────────

    async def lookup_customer_by_phone(self, phone: str) -> tuple[User, Optional[str]]:
        customer = (
            await self.session.execute(
                select(User).where(and_(User.phone == phone, User.role == "CUSTOMER", User.is_active == True))  # noqa: E712
            )
        ).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="해당 전화번호로 등록된 고객을 찾을 수 없습니다.")
        manager_name = None
        if customer.manager_id:
            manager_name = (
                await self.session.execute(select(User.display_name).where(User.id == customer.manager_id))
            ).scalar_one_or_none()
        return customer, manager_name

    async def assign_customer(self, customer_id: UUID, instructor_id: UUID) -> None:
        """담당 강사가 없는 고객(또는 이미 내 고객)만 담당으로 등록"""
        customer = (
            await self.session.execute(select(User).where(and_(User.id == customer_id, User.is_active == True)))  # noqa: E712
        ).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")
        if customer.role != "CUSTOMER":
            raise HTTPException(status_code=400, detail="고객 계정만 담당 등록할 수 있습니다.")
        if customer.manager_id and customer.manager_id != instructor_id:
            raise HTTPException(status_code=409, detail="이미 다른 강사의 담당 고객입니다. 고객 동의 후 변경할 수 있습니다.")
        customer.manager_id = instructor_id
        self.session.add(customer)
        await self.session.commit()

    # ── 통계 ─────────────────────────────────────────────────────────────────

    async def _status_counts(self, *where) -> dict[str, int]:
        res = await self.session.execute(
            select(Booking.status, func.count().label("cnt"))
            .join(User, Booking.guest_id == User.id)
            .where(*where)
            .group_by(Booking.status)
        )
        return {row.status: row.cnt for row in res}

    async def my_stats(self, instructor_id: UUID) -> dict:
        """담당 고객 수 + 담당 고객 예약의 상태별 집계·출석률"""
        customer_count = (
            await self.session.execute(
                select(func.count()).select_from(User).where(and_(User.manager_id == instructor_id, User.is_active == True))  # noqa: E712
            )
        ).scalar_one()
        return {"customer_count": customer_count, **_attendance(await self._status_counts(User.manager_id == instructor_id))}

    async def customer_stats(self, instructor_id: UUID, customer_id: UUID) -> dict:
        customer = (
            await self.session.execute(
                select(User).where(
                    and_(User.id == customer_id, User.manager_id == instructor_id, User.is_active == True)  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="담당 고객을 찾을 수 없습니다.")
        counts = await self._status_counts(Booking.guest_id == customer_id)
        return {"customer_id": str(customer_id), "customer_name": customer.display_name, **_attendance(counts)}

    # ── 매출·운영 대시보드 (강사 웹에서 보고, 앱에서 확인) ─────────────────────

    async def dashboard(self, instructor_id: UUID, months: int = 6) -> dict:
        """최근 N개월 월별 매출, 결제수단·수강권별 합계, 고객·수강권 현황. 월 구분은 한국 시간"""
        kst = ZoneInfo("Asia/Seoul")
        now = datetime.now(kst)
        keys: list[str] = []
        y, m = now.year, now.month
        for _ in range(months):
            keys.append(f"{y:04d}-{m:02d}")
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        keys.reverse()
        this_month, last_month = keys[-1], (keys[-2] if len(keys) > 1 else None)

        passes = await PassRepository(self.session).list_by_instructor(instructor_id)
        pass_name = {cp.id: cp.pass_name for cp in passes}

        monthly = {k: {"month": k, "amount": 0, "count": 0} for k in keys}
        by_method: dict[str, int] = {}
        by_pass: dict[str, int] = {}
        for pay in await PaymentRepository(self.session).list_for_instructor(instructor_id):
            if pay.status != "COMPLETED" or pay.created_at is None:
                continue
            key = pay.created_at.astimezone(kst).strftime("%Y-%m")
            if key not in monthly:
                continue
            monthly[key]["amount"] += pay.amount
            monthly[key]["count"] += 1
            by_method[pay.method] = by_method.get(pay.method, 0) + pay.amount
            name = pass_name.get(pay.customer_pass_id, "수강권 미연결") if pay.customer_pass_id else "수강권 미연결"
            by_pass[name] = by_pass.get(name, 0) + pay.amount

        month_start = date(now.year, now.month, 1)
        customers = list(
            (await self.session.execute(
                select(User).where(User.manager_id == instructor_id, User.is_active == True)  # noqa: E712
            )).scalars().all()
        )
        completed_lessons = (
            await self.session.execute(
                select(func.count())
                .select_from(Booking)
                .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
                .join(Calendar, Calendar.id == TimeSlot.calendar_id)
                .where(Calendar.host_id == instructor_id, Booking.status == "COMPLETED", Booking.when >= month_start)
            )
        ).scalar_one()
        active = [cp for cp in passes if cp.status == "ACTIVE"]

        def ranked(d: dict[str, int], label: str) -> list[dict]:
            return [{label: k, "amount": v} for k, v in sorted(d.items(), key=lambda kv: -kv[1])]

        return {
            "months": [monthly[k] for k in keys],
            "this_month": monthly[this_month]["amount"],
            "last_month": monthly[last_month]["amount"] if last_month else 0,
            "period_total": sum(v["amount"] for v in monthly.values()),
            "by_method": ranked(by_method, "method"),
            "by_pass": ranked(by_pass, "pass_name"),
            "customers": {
                "total": len(customers),
                "new_this_month": sum(1 for c in customers if c.created_at and c.created_at.astimezone(kst).date() >= month_start),
            },
            "passes": {
                "active": len(active),
                "remaining_sessions": sum(max(0, cp.sessions_total - cp.sessions_used) for cp in active),
                "completed": sum(1 for cp in passes if cp.status == "COMPLETED"),
            },
            "lessons_completed_this_month": completed_lessons,
        }

