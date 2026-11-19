"""더미 데이터의 규모와 사람 ID. seed.py(데이터 넣기)와 locustfile.py(토큰 만들기)가 같이 쓴다

앱 코드를 불러오지 않는다 (Locust 는 앱 의존성이 없는 별도 환경에서 돈다).
"""
from uuid import UUID, uuid5

N_INSTRUCTORS = 20
CUSTOMERS_PER_INSTRUCTOR = 25
SLOT_HOURS = range(9, 17)  # 9시~17시, 1시간짜리 슬롯 8개

_NS = UUID("6f1c2d3e-0000-4000-8000-00000000a11d")


def instructor_id(n: int) -> UUID:
    return uuid5(_NS, f"instructor-{n}")


def customer_id(n: int) -> UUID:
    return uuid5(_NS, f"customer-{n}")
