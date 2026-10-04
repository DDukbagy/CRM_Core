"""거래 기록 보존 기간 (결제·계약)

- 대금결제 기록 5년: 전자상거래법 시행령 제6조, 국세기본법 제85조의3(거래 증빙)
- 계약 또는 청약철회 등에 관한 기록 5년: 전자상거래법 시행령 제6조 → 발급 수강권

보존 기간 안의 기록이 있는 회원은 삭제하지 않고 탈퇴 처리(개인정보만 비움)한다.
"""
from datetime import datetime, timezone
from typing import Optional

RECORD_RETENTION_YEARS = 5


def retention_cutoff(now: Optional[datetime] = None) -> datetime:
    """이 시각보다 뒤의 기록은 아직 보존 기간 중 (N년 전 같은 날짜·시각, 2/29 는 2/28)"""
    now = now or datetime.now(timezone.utc)
    try:
        return now.replace(year=now.year - RECORD_RETENTION_YEARS)
    except ValueError:
        return now.replace(year=now.year - RECORD_RETENTION_YEARS, day=28)
