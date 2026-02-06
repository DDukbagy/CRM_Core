from fastapi import APIRouter, Depends
from app.core.auth.deps import get_current_user, CurrentUser
from app.domains.users.schemas import UserResponse

router = APIRouter(tags=["Users"])

@router.get("/users/me", response_model=UserResponse)
async def read_users_me(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    현재 로그인한 사용자의 정보를 반환합니다.
    프론트엔드 초기 진입 시, 또는 내 정보 확인 시 사용됩니다.
    """
    return current_user