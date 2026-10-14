"""데모 데이터 넣기: 데모 계정으로 로그인해 실제 API 로 강사 승인·수강권·예약·레슨노트·채팅·프로모션을 만든다

데모 전용 Supabase 프로젝트·데모 백엔드에만 쓴다 (docs/operations/demo-deploy.md).
계정은 Supabase 대시보드에서 먼저 만든다. 토큰·비밀번호는 출력하지 않는다.

필요한 환경변수
  DEMO_API_URL           데모 백엔드 주소 (예: https://crm-core-demo-api.onrender.com)
  SUPABASE_URL           데모 Supabase Project URL
  SUPABASE_ANON_KEY      데모 Supabase anon key
  DEMO_PASSWORD          데모 계정 공통 비밀번호
  DEMO_ADMIN_EMAIL       백엔드 SUPER_ADMIN_EMAIL 과 같은 계정
  DEMO_INSTRUCTOR_EMAIL
  DEMO_CUSTOMER_EMAIL
  DEMO_CUSTOMER2_EMAIL   (선택) 두 번째 고객

실행: cd backend && poetry run python scripts/seed_demo.py
"""
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

API = os.environ["DEMO_API_URL"].rstrip("/")
AUTH = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1/token?grant_type=password"
ANON = os.environ["SUPABASE_ANON_KEY"]
PASSWORD = os.environ["DEMO_PASSWORD"]
EMAILS = {
    "admin": os.environ["DEMO_ADMIN_EMAIL"],
    "inst": os.environ["DEMO_INSTRUCTOR_EMAIL"],
    "cust": os.environ["DEMO_CUSTOMER_EMAIL"],
}
if os.environ.get("DEMO_CUSTOMER2_EMAIL"):
    EMAILS["cust2"] = os.environ["DEMO_CUSTOMER2_EMAIL"]
NAMES = {"admin": "데모 관리자", "inst": "김프로", "cust": "최고객", "cust2": "정고객"}
TODAY = datetime.now(ZoneInfo("Asia/Seoul")).date()

http = httpx.Client(timeout=60)  # 무료 호스팅은 잠들어 있다가 깨어나는 데 시간이 걸린다
tok: dict[str, str] = {}


def call(who: str, method: str, path: str, **kw):
    r = http.request(method, API + path, headers={"Authorization": f"Bearer {tok[who]}"}, **kw)
    if r.status_code >= 400:
        sys.exit(f"실패: {method} {path} → {r.status_code} {r.text[:200]}")
    return r.json() if r.content else None


def login(who: str) -> None:
    r = http.post(AUTH, headers={"apikey": ANON}, json={"email": EMAILS[who], "password": PASSWORD})
    if r.status_code != 200:
        sys.exit(f"로그인 실패: {who} ({r.status_code}). Supabase 대시보드에 계정이 있는지, 비밀번호가 맞는지 확인")
    tok[who] = r.json()["access_token"]


def main() -> None:
    print("데모 백엔드 깨우는 중…")
    http.get(API + "/health")

    for who in EMAILS:
        login(who)
    me = {who: call(who, "GET", "/users/me") for who in EMAILS}  # 최초 로그인이면 여기서 사용자 생성
    if me["admin"]["role"] != "ADMIN":
        sys.exit("관리자 계정이 ADMIN 이 아님: 백엔드 SUPER_ADMIN_EMAIL 이 DEMO_ADMIN_EMAIL 과 같은지 확인")
    ids = {who: u["id"] for who, u in me.items()}

    # 강사 승인 (승인되면 기본 캘린더·슬롯이 생긴다)
    if me["inst"]["role"] != "INSTRUCTOR" or me["inst"]["status"] != "ACTIVE":
        call("inst", "POST", "/instructors/apply")
        call("admin", "POST", f"/instructors/{ids['inst']}/approve")
    if call("inst", "GET", "/passes/types"):
        sys.exit("이미 데모 데이터가 있습니다. 다시 넣으려면 데모 DB 를 비우고 실행하세요")

    for who, name in NAMES.items():
        if who in ids:
            call("admin", "PATCH", f"/users/{ids[who]}", json={"display_name": name})
    call("inst", "PATCH", "/users/me", json={
        "instructor_location": "서울 강남", "instructor_specialties": "드라이버,숏게임,초보",
        "instructor_bio": "10년차 KPGA 프로. 초보부터 싱글까지 체계적으로 지도합니다.",
        "career_years": 10, "certifications": "KPGA 정회원", "recurring_off_days": [0],
    })

    # 담당 고객, 수강권, 결제
    customers = [w for w in ("cust", "cust2") if w in ids]
    for c in customers:
        call("inst", "POST", "/users/me/customers", json={"email": EMAILS[c]})
    t10 = call("inst", "POST", "/passes/types", json={"name": "10회권", "duration_hours": 1, "session_count": 10, "price": 500000})
    call("inst", "POST", "/passes/types", json={"name": "20회권", "duration_hours": 1, "session_count": 20, "price": 900000})
    cp = call("inst", "POST", "/passes/assign", json={"customer_id": ids["cust"], "pass_type_id": t10["id"]})
    call("inst", "POST", "/payments", json={"customer_id": ids["cust"], "customer_pass_id": cp["id"], "amount": 500000, "method": "TRANSFER"})
    if "cust2" in ids:
        cp2 = call("inst", "POST", "/passes/assign", json={"customer_id": ids["cust2"], "pass_type_id": t10["id"]})
        call("inst", "POST", "/payments", json={"customer_id": ids["cust2"], "customer_pass_id": cp2["id"], "amount": 500000, "method": "CASH"})

    # 예약: 내일 이후 영업일 2개 (하나는 확정, 하나는 신청 중)
    inst_cal = call("inst", "GET", "/calendars/me")
    avail = call("cust", "GET", f"/calendars/{ids['inst']}/availability",
                 params={"start": str(TODAY + timedelta(days=1)), "end": str(TODAY + timedelta(days=14))})
    open_days = [d for d in avail["days"] if d["slots"]]
    booked = 0
    for d in open_days[:2]:
        slot = d["slots"][len(d["slots"]) // 2]
        b = call("cust", "POST", "/bookings", json={"time_slot_id": slot["time_slot_id"], "when": d["date"], "topic": "드라이버 스윙"})
        if booked == 0:
            call("inst", "PATCH", f"/calendars/me/bookings/{b['id']}/confirm", json={"topic": "드라이버 스윙 교정"})
        booked += 1

    # 레슨노트, 게시물, 프로모션, 채팅
    call("inst", "POST", "/lesson-notes", json={"customer_id": ids["cust"], "title": "1회차 레슨",
         "content": "어드레스 자세와 그립을 점검했습니다. 다음 시간에는 백스윙 궤도를 연습합니다."})
    call("inst", "POST", "/posts", json={"type": "PROMOTION", "title": "가을 시즌 레슨 오픈",
         "content": "10월 평일 오전 레슨 자리가 남아 있습니다. 문의하기로 편하게 연락 주세요."})
    call("inst", "POST", "/promotions", json={"title": "가을맞이 10회권 할인", "description": "10월 한 달 10회권 10% 할인",
         "pass_type_id": t10["id"], "discount_type": "PERCENT", "discount_value": 10,
         "start_date": str(TODAY), "end_date": str(TODAY + timedelta(days=30))})
    room = call("cust", "POST", "/chat/rooms", json={"instructor_id": ids["inst"]})
    call("cust", "POST", f"/chat/rooms/{room['id']}/messages", json={"content": "안녕하세요, 주말 레슨도 가능한가요?"})
    call("inst", "POST", f"/chat/rooms/{room['id']}/messages", json={"content": "네, 토요일 오전 가능합니다. 달력에서 신청해 주세요!"})

    print(f"완료: 강사 1명, 고객 {len(customers)}명, 수강권·결제, 예약 {booked}건, 레슨노트, 게시물, 프로모션, 채팅 (캘린더 {inst_cal['id']})")


if __name__ == "__main__":
    main()
