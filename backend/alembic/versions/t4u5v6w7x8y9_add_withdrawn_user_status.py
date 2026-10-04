"""allow WITHDRAWN user status (member withdrawal keeps payment records)

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
Create Date: 2026-10-01 00:00:00.000000

배경:
- 결제 기록 5년 보존(s3t4u5v6w7x8) 때문에 결제가 있는 회원은 삭제할 수 없다.
  대신 탈퇴 처리: 로그인 차단 + 개인정보 익명화, 회원 행과 결제 기록은 남긴다 (개인정보보호법 제21조 분리 보관).

변경 내용:
- users.chk_user_status 에 'WITHDRAWN' 추가

데이터: 행은 바꾸지 않는다
downgrade: WITHDRAWN 회원이 있으면 실패한다 (상태를 되돌릴 수 없음). 없으면 예전 제약으로 복원
"""
from alembic import op

revision = "t4u5v6w7x8y9"
down_revision = "s3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.users DROP CONSTRAINT IF EXISTS chk_user_status")
    op.execute(
        "ALTER TABLE public.users ADD CONSTRAINT chk_user_status "
        "CHECK (status IN ('ACTIVE','PENDING','SUSPENDED','WITHDRAWN'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.users DROP CONSTRAINT IF EXISTS chk_user_status")
    op.execute(
        "ALTER TABLE public.users ADD CONSTRAINT chk_user_status "
        "CHECK (status IN ('ACTIVE','PENDING','SUSPENDED'))"
    )
