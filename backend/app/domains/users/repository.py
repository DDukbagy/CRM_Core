from datetime import datetime, timezone
import secrets
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser
from app.core.auth.security import get_password_hash
from app.domains.calendar.repository import CalendarRepository
from app.domains.chat.repository import ChatRepository
from app.core.retention import RECORD_RETENTION_YEARS
from app.domains.passes.repository import PassRepository
from app.domains.payment.repository import PaymentRepository
from app.domains.users.models import User
from app.domains.users.schemas import UserCreate, UserUpdate

# 본인이 PATCH /users/me 로 바꿀 수 있는 필드 (역할·상태·담당 강사는 제외)
SELF_EDITABLE_FIELDS = (
    "email", "phone",
    "instructor_location", "instructor_specialties", "instructor_bio", "career_years", "certifications",
    "birth_date", "gender", "lesson_purpose", "recurring_off_days", "feedback_consent",
)


def safe_uuid(value) -> UUID:
    """current_user.id 가 깨져 있으면 500 이 아니라 401"""
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token subject")


def _make_username(user_id: UUID, email: Optional[str]) -> str:
    """email 앞부분, 없으면 user_<uuid 앞 8자리> (뒤에 suffix 붙일 여지 남김)"""
    base = email.split("@")[0] if email else f"user_{str(user_id)[:8]}"
    return base[:30]


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_404(self, user_id: UUID) -> User:
        user = (await self.session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    # ── 내 계정 ──────────────────────────────────────────────────────────────

    async def get_or_create_me(self, current: CurrentUser) -> User:
        """users 행이 없으면 만들어 둔다(동기화). username 충돌 시 suffix 를 붙여 재시도"""
        user_id = safe_uuid(current.id)
        user = (await self.session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user:
            return user

        username_base = _make_username(user_id, current.email)
        for i in range(5):
            suffix = "" if i == 0 else "_" + secrets.token_hex(2)
            new_user = User(
                id=user_id,
                username=(username_base + suffix)[:40],
                email=current.email,
                display_name=current.display_name or "사용자",
                password=None,
                role="CUSTOMER",
                is_active=True,
            )
            self.session.add(new_user)
            try:
                await self.session.commit()
                await self.session.refresh(new_user)
                return new_user
            except IntegrityError:
                await self.session.rollback()
                existing = (await self.session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                if existing:
                    return existing
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="사용자 생성 실패")

    async def update_me(self, current: CurrentUser, payload: UserUpdate) -> User:
        user = await self.get_or_create_me(current)
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return user
        # username·display_name 은 null 로 지우지 않는다
        for field in ("username", "display_name"):
            if data.get(field) is not None:
                setattr(user, field, data[field])
        for field in SELF_EDITABLE_FIELDS:
            if field in data:
                setattr(user, field, data[field])
        try:
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            return user
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 username 또는 email 입니다.")

    async def set_push_token(self, user_id, token: Optional[str]) -> None:
        user = (await self.session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user and (token is not None or user.push_token):
            user.push_token = token
            self.session.add(user)
            await self.session.commit()

    # ── 목록·상세 (역할별 범위) ──────────────────────────────────────────────

    async def list_for_user(self, current: CurrentUser, limit: int, offset: int, role: Optional[str]) -> tuple[list[User], int, int, int]:
        """관리자: 전체 / 강사: 담당 고객 / 그 외: 본인. (items, total, limit, offset)"""
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)
        filters = []
        if current.role == "INSTRUCTOR":
            filters.append(User.manager_id == safe_uuid(current.id))
        elif current.role != "ADMIN":
            filters.append(User.id == safe_uuid(current.id))
        if role:
            filters.append(User.role == role)

        users = (
            await self.session.execute(
                select(User).where(*filters).order_by(User.created_at.desc()).limit(limit).offset(offset)
            )
        ).scalars().all()
        total = (await self.session.execute(select(func.count()).select_from(User).where(*filters))).scalar_one()
        return list(users), total, limit, offset

    async def get_visible(self, user_id: UUID, current: CurrentUser) -> User:
        """관리자: 전체 / 강사: 본인·담당 고객 / 고객: 본인·담당 강사"""
        user = await self.get_or_404(user_id)
        me = safe_uuid(current.id)
        if current.role == "ADMIN":
            return user
        if current.role == "INSTRUCTOR":
            if user.id != me and user.manager_id != me:
                raise HTTPException(status_code=403, detail="Forbidden")
            return user
        if user.id == me:
            return user
        me_row = (await self.session.execute(select(User).where(User.id == me))).scalar_one_or_none()
        if me_row and me_row.manager_id and me_row.manager_id == user.id:
            return user
        raise HTTPException(status_code=403, detail="Forbidden")

    # ── 계정 관리 ────────────────────────────────────────────────────────────

    async def register_customer_by_email(self, instructor_id: UUID, email: str) -> User:
        """강사가 이메일로 담당 고객 등록 (담당 강사가 없거나 이미 나인 고객만)"""
        customer = (await self.session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="등록되지 않은 고객입니다.")
        if customer.role != "CUSTOMER":
            raise HTTPException(status_code=400, detail="고객 계정이 아닙니다.")
        if customer.manager_id and customer.manager_id != instructor_id:
            raise HTTPException(status_code=409, detail="이미 담당 강사가 있는 고객입니다.")
        if customer.manager_id != instructor_id:
            customer.manager_id = instructor_id
            self.session.add(customer)
            await self.session.commit()
            await self.session.refresh(customer)
        return customer

    async def create(self, user_in: UserCreate, current: CurrentUser) -> User:
        """관리자·강사가 계정 생성. 강사는 CUSTOMER 만, 담당 강사는 본인으로 고정"""
        manager_id = user_in.manager_id
        if current.role == "INSTRUCTOR":
            manager_id = current.id
            if user_in.role != "CUSTOMER":
                raise HTTPException(status_code=403, detail="강사는 일반 고객만 등록할 수 있습니다.")

        new_user = User(
            id=uuid4(),
            username=user_in.username,
            email=user_in.email,
            display_name=user_in.display_name,
            phone=user_in.phone,
            manager_id=manager_id,
            password=get_password_hash(user_in.password),
            role=user_in.role or "CUSTOMER",
            is_active=True,
        )
        try:
            self.session.add(new_user)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 아이디 또는 이메일입니다.")
        # 관리자가 바로 만든 강사 계정도 기본 캘린더를 갖는다
        if new_user.role == "INSTRUCTOR":
            await CalendarRepository(self.session).ensure_default(new_user.id)
        await self.session.refresh(new_user)
        return new_user

    async def update(self, user_id: UUID, user_in: UserUpdate, current: CurrentUser) -> User:
        """관리자: 전체 / 강사: 본인·담당 고객 / 그 외: 본인. 아이디·이메일·이름만"""
        user = await self.get_or_404(user_id)
        me = safe_uuid(current.id)
        if current.role == "INSTRUCTOR":
            if user.id != me and user.manager_id != me:
                raise HTTPException(status_code=403, detail="Forbidden")
        elif current.role != "ADMIN" and user.id != me:
            raise HTTPException(status_code=403, detail="Forbidden")

        data = user_in.model_dump(exclude_unset=True)
        for field in ("username", "email", "display_name"):
            if data.get(field):
                setattr(user, field, data[field])
        try:
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            return user
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="이미 사용 중인 정보입니다.")

    async def withdraw(self, user_id: UUID, current: CurrentUser) -> User:
        """탈퇴 처리: 로그인 차단 + 개인정보 익명화. 회원 행·결제·예약 기록은 남긴다

        - 본인, 관리자, 담당 강사(담당 고객에 한해)만 가능
        - 결제 기록 보존 의무 때문에 삭제할 수 없는 회원에게 쓴다 (개인정보보호법 제21조 분리 보관)
        - 이 회원이 담당하던 고객은 담당 강사가 없는 상태가 된다
        """
        user = await self.get_or_404(user_id)
        me = safe_uuid(current.id)
        if not (user.id == me or current.role == "ADMIN" or (current.role == "INSTRUCTOR" and user.manager_id == me)):
            raise HTTPException(status_code=403, detail="Forbidden")
        if (user.status or "").upper() == "WITHDRAWN":
            return user

        user.status = "WITHDRAWN"
        user.is_active = False
        user.withdrawn_at = datetime.now(timezone.utc)
        user.username = f"withdrawn_{user.id.hex[:16]}"
        user.display_name = "탈퇴한 회원"
        for field in (
            "email", "phone", "password", "push_token", "manager_id",
            "instructor_tier", "instructor_location", "instructor_specialties", "instructor_bio",
            "career_years", "certifications", "birth_date", "gender", "lesson_purpose",
        ):
            setattr(user, field, None)
        user.recurring_off_days = []
        user.feedback_consent = False
        self.session.add(user)

        await self.session.execute(update(User).where(User.manager_id == user.id).values(manager_id=None))
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user_id: UUID, current: CurrentUser) -> None:
        """관리자: 전체 / 강사: 담당 고객만 (본인 계정 삭제 불가)

        결제·계약(수강권) 기록의 보존 기간(5년)이 끝나지 않았으면 삭제하지 않는다 → 탈퇴 처리를 쓴다.
        보존 기간이 끝난 기록만 있으면 그 기록을 먼저 지우고 회원을 삭제한다 (한 트랜잭션).
        """
        user = await self.get_or_404(user_id)
        if current.role == "INSTRUCTOR":
            if user.manager_id != safe_uuid(current.id):
                raise HTTPException(status_code=403, detail="Forbidden")
        elif current.role != "ADMIN":
            raise HTTPException(status_code=403, detail="Forbidden")

        payments = PaymentRepository(self.session)
        passes = PassRepository(self.session)
        retained = [
            name
            for name, count in (
                ("결제", await payments.count_retained_for_customer(user.id)),
                ("수강권", await passes.count_retained_for_user(user.id)),
            )
            if count
        ]
        if retained:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"보존 기간({RECORD_RETENTION_YEARS}년)이 끝나지 않은 {'·'.join(retained)} 기록이 있어 회원을 삭제할 수 없습니다. "
                    "탈퇴 처리(POST /users/{id}/withdraw)를 사용하세요."
                ),
            )
        await payments.delete_expired_for_customer(user.id)
        await passes.delete_expired_for_user(user.id)
        await self.session.delete(user)
        await self.session.commit()

    async def select_manager(self, current: CurrentUser, instructor_id: UUID) -> User:
        """고객이 담당 강사를 지정한다. 그 강사에게 문의(채팅방)한 적이 있어야 한다.
        (강사가 앱 밖에서 구한 고객을 등록하는 것은 register_customer_by_email)"""
        me = await self.get_or_404(safe_uuid(current.id))
        if (me.role or "").upper() != "CUSTOMER":
            raise HTTPException(status_code=403, detail="고객만 담당 강사를 지정할 수 있습니다.")
        if me.manager_id == instructor_id:
            return me
        instructor = await self.session.get(User, instructor_id)
        if not instructor or (instructor.role or "").upper() != "INSTRUCTOR" or (instructor.status or "").upper() != "ACTIVE":
            raise HTTPException(status_code=404, detail="강사를 찾을 수 없습니다.")
        if await ChatRepository(self.session).find_room(me.id, instructor_id) is None:
            raise HTTPException(status_code=400, detail="먼저 문의하기로 강사와 대화를 시작하세요.")
        me.manager_id = instructor_id
        self.session.add(me)
        await self.session.commit()
        await self.session.refresh(me)
        return me
