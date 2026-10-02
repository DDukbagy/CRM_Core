from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import CurrentUser
from app.domains.chat.repository import ChatRepository
from app.domains.matching.models import MatchRequest, NAMED_FEE
from app.domains.matching.schemas import MatchRequestCreate
from app.domains.users.models import User

REQUEST_TYPES = ("MATCH", "CONSULTATION")


class MatchRepository:
    """고객 → 강사 매칭·상담 요청 (PENDING → ACCEPTED / REJECTED / CANCELLED)"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # 활성 강사에게만, 같은 종류의 진행 중(PENDING/ACCEPTED) 요청은 하나만. 네임드 강사 매칭은 수수료, 상담은 무료
    async def create(self, payload: MatchRequestCreate, customer_id: UUID) -> tuple[MatchRequest, User]:
        instructor = (
            await self.session.execute(
                select(User).where(
                    and_(
                        User.id == payload.instructor_id,
                        User.role == "INSTRUCTOR",
                        User.status == "ACTIVE",
                        User.is_active == True,  # noqa: E712
                    )
                )
            )
        ).scalar_one_or_none()
        if not instructor:
            raise HTTPException(status_code=404, detail="강사를 찾을 수 없습니다.")

        req_type = (payload.request_type or "MATCH").upper()
        if req_type not in REQUEST_TYPES:
            raise HTTPException(status_code=400, detail="request_type은 MATCH 또는 CONSULTATION 이어야 합니다.")

        tier = (instructor.instructor_tier or "NORMAL").upper()
        fee = NAMED_FEE if tier == "NAMED" and req_type == "MATCH" else 0

        dup = await self.session.execute(
            select(MatchRequest).where(
                and_(
                    MatchRequest.customer_id == customer_id,
                    MatchRequest.request_type == req_type,
                    MatchRequest.status.in_(["PENDING", "ACCEPTED"]),
                )
            )
        )
        if dup.scalar_one_or_none():
            label = "매칭" if req_type == "MATCH" else "상담"
            raise HTTPException(
                status_code=409,
                detail=f"이미 진행 중인 {label} 요청이 있습니다. 기존 요청을 취소 후 다시 신청해 주세요.",
            )

        mr = MatchRequest(
            customer_id=customer_id,
            instructor_id=payload.instructor_id,
            request_type=req_type,
            status="PENDING",
            fee=fee,
            note=payload.note,
        )
        self.session.add(mr)
        await self.session.commit()
        await self.session.refresh(mr)
        return mr, instructor

    # 고객: 보낸 요청(강사 이름 포함) / 강사·관리자: 받은 요청(고객 이름 포함)
    async def list_for_user(self, user: CurrentUser) -> list:
        uid = str(user.id)
        if user.role == "CUSTOMER":
            sql = """
                SELECT mr.*, u.display_name AS instructor_name
                FROM instructor_match_requests mr
                JOIN public.users u ON u.id = mr.instructor_id
                WHERE mr.customer_id = :uid
                ORDER BY mr.created_at DESC
            """
        elif user.role in ("INSTRUCTOR", "ADMIN"):
            sql = """
                SELECT mr.*, u.display_name AS customer_name
                FROM instructor_match_requests mr
                JOIN public.users u ON u.id = mr.customer_id
                WHERE mr.instructor_id = :uid
                ORDER BY mr.created_at DESC
            """
        else:
            return []
        return list((await self.session.execute(text(sql), {"uid": uid})).fetchall())

    async def _get_pending_for_instructor(self, request_id: UUID, instructor_id: str, action: str) -> MatchRequest:
        mr = await self.session.get(MatchRequest, request_id)
        if not mr or str(mr.instructor_id) != instructor_id:
            raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
        if mr.status != "PENDING":
            raise HTTPException(status_code=400, detail=f"{action}할 수 없는 상태입니다: {mr.status}")
        return mr

    # 수락: MATCH 면 고객의 담당 강사로 지정(상담은 연결 없음), 채팅방 생성 — 한 트랜잭션
    async def accept(self, request_id: UUID, instructor: CurrentUser) -> tuple[MatchRequest, Optional[User]]:
        mr = await self._get_pending_for_instructor(request_id, str(instructor.id), "수락")
        mr.status = "ACCEPTED"
        self.session.add(mr)

        customer = (await self.session.execute(select(User).where(User.id == mr.customer_id))).scalar_one_or_none()
        if customer and (mr.request_type or "MATCH") == "MATCH":
            customer.manager_id = mr.instructor_id
            self.session.add(customer)

        await ChatRepository(self.session).ensure_room_for_match(mr.customer_id, mr.instructor_id, mr.id)
        await self.session.commit()
        await self.session.refresh(mr)
        return mr, customer

    async def reject(self, request_id: UUID, instructor: CurrentUser) -> MatchRequest:
        mr = await self._get_pending_for_instructor(request_id, str(instructor.id), "거절")
        mr.status = "REJECTED"
        self.session.add(mr)
        await self.session.commit()
        await self.session.refresh(mr)
        return mr

    async def cancel(self, request_id: UUID, customer: CurrentUser) -> None:
        mr = await self.session.get(MatchRequest, request_id)
        if not mr or str(mr.customer_id) != str(customer.id):
            raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
        if mr.status != "PENDING":
            raise HTTPException(status_code=400, detail="취소할 수 없는 상태입니다.")
        mr.status = "CANCELLED"
        self.session.add(mr)
        await self.session.commit()
