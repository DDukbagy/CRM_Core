from __future__ import annotations

import secrets
from uuid import UUID, uuid4
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.deps import require_role, get_current_user, CurrentUser
from app.db.session import get_session
from app.domains.users.models import User
from app.security import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_password_hash

from app.domains.users.schemas import (
    UserRead,
    UsersListResponse,
    UserUpdate,
    UserCreate,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

def _safe_uuid(value: str) -> UUID:
    """
    ✅ 인증 안전장치:
    - current_user.id(UUID 문자열)가 깨져 있으면 500이 아니라 401로 귀결
    """
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token subject")

def _make_username(user_id: UUID, email: str | None) -> str:
    """
    자동 생성 username 규칙
    - email이 있으면 email prefix 우선
    - 없으면 user_<uuid앞8자리>
    """
    base = (email.split("@")[0] if email else f"user_{str(user_id)[:8]}")
    return base[:30] # suffix 붙일 여지 남김

async def _get_or_create_user_row(
    session: AsyncSession,
    user_id: UUID,
    email: str | None,
    display_name: str | None,
) -> User:
    """
    users row가 있으면 반환, 없으면 생성(자동 동기화)
    - username 충돌 대비해서 몇 번 재시도
    """
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    username_base = _make_username(user_id, email)
    display = display_name or "사용자"

    # 중복 방지를 위해 suffix 추가 시도
    for i in range(5):
        suffix = "" if i == 0 else "_" + secrets.token_hex(2)   # 4 hex
        username = (username_base + suffix)[:40]

        new_user = User(
            id=user_id,
            username=username,
            email=email,
            display_name=display,
            password=None,      # password는 DB에서 nullable이어야 함
            role="CUSTOMER",
            is_active=True
        )
        session.add(new_user)

        try:
            await session.commit()
            await session.refresh(new_user)
            return new_user
        except IntegrityError:
            await session.rollback()

            # 동시성 문제로 이미 생성되었을 경우 재조회
            result = await session.execute(select(User).where(User.id == user_id))
            existing = result.scalar_one_or_none()
            if existing:
                return existing

            # 아니면 username 충돌 가능성 → retry

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="사용자 생성 실패",
    )

@router.get("/me", response_model=UserRead)
async def get_my_account(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    내 계정 조회
    - 로그인한 유저 본인만 접근
    - users row가 없으면 자동 생성(동기화)
    """
    user_id = _safe_uuid(current_user.id)
    email = current_user.email
    display_name = current_user.display_name

    user = await _get_or_create_user_row(session, user_id, email, display_name)
    return user

@router.patch("/me", response_model=UserRead)
async def update_my_account(
    payload: UserUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    내 프로필 일부 수정(PATCH)
    - username/email/display_name 중 들어온 것만 업데이트
    - users row가 없으면 먼저 자동 생성(동기화) 후 업데이트
    """
    user_id = _safe_uuid(current_user.id)
    email = current_user.email
    display_name = current_user.display_name
    user = await _get_or_create_user_row(session, user_id, email, display_name)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return user  # 수정할 게 없으면 그대로 반환

    # 허용된 필드만 반영
    if "username" in data and data["username"] is not None:
        user.username = data["username"]
    if "email" in data:
        user.email = data["email"]
    if "display_name" in data and data["display_name"] is not None:
        user.display_name = data["display_name"]

    try:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    except IntegrityError:
        await session.rollback()
        # username/email unique 충돌 같은 케이스
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 username 또는 email 입니다.",
        )

# 목록 조회 (강사, 관리자 차별화)
@router.get("", response_model=UsersListResponse)
async def list_users(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    # 권한 체크가 필요 아래 사용
    # current_host: CurrentUser = Depends(require_role({"INSTRUCTOR", "ADMIN"})),
):
    """
    특정 유저 조회(호스트 전용)
    - 현재는 host 권한만 체크
    - 운영 확장 시 current_host를 이용해 코치별 범위 제한 로직을 붙일 수 있음
    """
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)

    filters = []

    if current_user.role == 'ADMIN':
        # 관리자: 제약 없음 (모든 데이터 조회)
        pass
    elif current_user.role == 'INSTRUCTOR':
        # 강사: 본인이 담당자(manager_id)인 고객만 조회 OR 본인 계정
        filters.append(
            (User.manager_id == _safe_uuid(str(current_user.id))) | (User.id == _safe_uuid(str(current_user.id)))
        )
    else:
        # 일반 고객 등: 본인 것만 조회 (보안)
        filters.append(User.id == _safe_uuid(str(current_user.id)))

    # 페이징 적용
    stmt = select(User).where(*filters).order_by(User.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    users = result.scalars().all()

    # 운영식 카운트 쿼리 (SELECT COUNT(*) ...)
    count_stmt = select(func.count()).select_from(User).where(*filters)
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    return {
        "items": users,
        "total": total,
        "limit": limit,
        "offset": offset,
    }

@router.get("/{user_id}", response_model=UserRead)
async def get_user_detail(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    유저 목록 조회(호스트 전용)
    - UsersListResponse(items/total/limit/offset)로 고정
    """
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role == 'ADMIN':
        return user
    elif current_user.role == 'INSTRUCTOR':
        if user.id != _safe_uuid(str(current_user.id)) and user.manager_id != _safe_uuid(str(current_user.id)):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    else:
        if user.id != _safe_uuid(str(current_user.id)):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    [신규 고객 등록]
    - 보안 검사(Depends) 없이 누구나 등록 가능하게 열어두었습니다.
    """
    # UUID 생성
    new_id = uuid4()

    # 비밀번호 해싱
    hashed_password = get_password_hash(user_in.password)

    # 담당자 자동 배정
    manager_id_to_set = user_in.manager_id

    # 강사가 고객을 등록 시 담당자를 '강사 본인'으로 강제 설정
    if current_user.role == 'INSTRUCTOR':
        manager_id_to_set = current_user.id
        # 강사는 'CUSTOMER'만 만들 수 있게 강제 (보안)
        if user_in.role != 'CUSTOMER':
            raise HTTPException(status_code=403, detail="강사는 일반 고객만 등록할 수 있습니다.")

    # DB 모델 생성
    new_user = User(
        id=new_id,
        username=user_in.username,
        email=user_in.email,
        display_name=user_in.display_name,
        phone=user_in.phone,
        manager_id=manager_id_to_set, # 👈 담당자 저장
        password=hashed_password,
        role=user_in.role or "CUSTOMER",
        is_active=True,
    )

    try:
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return new_user
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 아이디 또는 이메일입니다.",
        )

@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    [관리자용] 특정 회원 정보 수정
    """
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role == 'ADMIN':
        pass
    elif current_user.role == 'INSTRUCTOR':
        if user.id != _safe_uuid(str(current_user.id)) and user.manager_id != _safe_uuid(str(current_user.id)):
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if user.id != _safe_uuid(str(current_user.id)):
            raise HTTPException(status_code=403, detail="Forbidden")

    # 업데이트 로직
    update_data = user_in.model_dump(exclude_unset=True)

    if "username" in update_data and update_data["username"]:
        user.username = update_data["username"]
    if "email" in update_data and update_data["email"]:
        user.email = update_data["email"]
    if "display_name" in update_data and update_data["display_name"]:
        user.display_name = update_data["display_name"]

    try:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="이미 사용 중인 정보입니다.")

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    [관리자용] 특정 회원 삭제
    """
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role == 'ADMIN':
        pass
    elif current_user.role == 'INSTRUCTOR':
        if user.id != _safe_uuid(str(current_user.id)) and user.manager_id != _safe_uuid(str(current_user.id)):
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if user.id != _safe_uuid(str(current_user.id)):
            raise HTTPException(status_code=403, detail="Forbidden")

    await session.delete(user)
    await session.commit()
    return None

@router.post("/login/access-token")
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """
    [로그인] 아이디/비번을 검사하고 JWT 토큰(신분증)을 발급합니다.
    """
    # 유저 찾기
    result = await session.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    # 유저가 없거나 비밀번호가 틀리면 -> 에러 뻥!
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="아이디 또는 비밀번호가 틀렸습니다.")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="비활성화된 계정입니다.")

    # 유효기간 설정 (24시간)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # 토큰 발급 (신분증에 user_id랑 role 정보를 심어줌)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,          # 프론트엔드가 길을 찾기 위해 필요
        "display_name": user.display_name # 환영 인사에 쓰려고 추가
    }
