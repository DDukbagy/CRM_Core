from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import require_role, CurrentUser, get_current_user
from app.db.session import get_session
from app.domains.matching.models import MatchRequest
from app.domains.matching.repository import MatchRepository
from app.domains.matching.schemas import MatchRequestCreate, MatchRequestRead

# 경로는 기존 API 계약(/instructors/match...)을 유지한다.
router = APIRouter(prefix="/instructors", tags=["Matching"])


def _read(mr, *, instructor_name: Optional[str] = None, customer_name: Optional[str] = None) -> MatchRequestRead:
    return MatchRequestRead(
        id=mr.id,
        customer_id=mr.customer_id,
        instructor_id=mr.instructor_id,
        request_type=getattr(mr, "request_type", None) or "MATCH",
        status=mr.status,
        fee=mr.fee,
        note=mr.note,
        instructor_name=instructor_name,
        customer_name=customer_name,
        created_at=mr.created_at,
        updated_at=mr.updated_at,
    )


@router.post("/match", status_code=status.HTTP_201_CREATED, response_model=MatchRequestRead)
async def request_match(
    payload: MatchRequestCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER"})),
):
    """고객 → 강사 매칭 신청"""
    mr, instructor = await MatchRepository(session).create(payload, UUID(str(user.id)))
    return _read(mr, instructor_name=instructor.display_name)


@router.get("/match/me", response_model=list[MatchRequestRead])
async def get_my_match_requests(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """고객: 내 매칭 요청 목록 / 강사: 받은 매칭 요청 목록"""
    rows = await MatchRepository(session).list_for_user(user)
    return [
        _read(r, instructor_name=getattr(r, "instructor_name", None), customer_name=getattr(r, "customer_name", None))
        for r in rows
    ]


@router.patch("/match/{request_id}/accept", response_model=MatchRequestRead)
async def accept_match(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 매칭 요청 수락 → 담당 강사 지정 + 채팅방 생성"""
    mr, customer = await MatchRepository(session).accept(request_id, user)
    return _read(mr, customer_name=customer.display_name if customer else None)


@router.patch("/match/{request_id}/reject", response_model=MatchRequestRead)
async def reject_match(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """강사가 매칭 요청 거절"""
    mr: MatchRequest = await MatchRepository(session).reject(request_id, user)
    return _read(mr)


@router.delete("/match/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_match(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role({"CUSTOMER"})),
):
    """고객이 매칭 요청 취소"""
    await MatchRepository(session).cancel(request_id, user)
    return None
