# 날짜 기준: 서비스는 한국에서 쓰므로 "오늘"은 한국 시간으로 판단한다 (서버 시간은 UTC)
from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today_kst() -> date:
    """한국 시간 기준 오늘 (UTC 서버에서 00~09시에 하루 전 날짜가 되지 않게)"""
    return datetime.now(KST).date()
