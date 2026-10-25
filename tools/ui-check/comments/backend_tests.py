import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))  # 저장소 루트
import sys; sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from lib import apply
H, A, R = "head", "above", "rep"
spec = {
 "alembic/env.py": [(H, "Alembic 실행 설정: 모델 등록, 비교 대상 조정, 온라인 마이그레이션"), (R, "# Alembic 설정 (Standard)", "# Alembic 설정")],
 "scripts/check_db_connection.py": [(H, "DB 연결 확인 (make dbcheck)")],
 "tests/conftest.py": [(H, "테스트 공용 설정: 로컬 DB, 앱 클라이언트, 사용자·토큰 만들기"), (R, "# Instructor / Customer helpers", "# 강사·고객 만들기")],
 "tests/test_booking_flow.py": [(R, "# 휴무\n", "# 휴무 5종\n"), (R, "# 수강권 차감 (멤버십은 수강권으로 통합)", "# 수강권 차감")],
 "tests/test_bookings.py": [(H, "예약 생성·중복 방지·취소 신청 흐름"), (R, "# CANCEL_REQUESTED 상태 머신 테스트", "# 취소 신청(CANCEL_REQUESTED) 흐름")],
 "tests/test_consent_policy.py": [(H, "피드백 공개 동의: 동의하면 공개, 철회하면 비공개, 대상 고객만 가능")],
 "tests/test_lesson_notes.py": [(R, "# 고객별 노트 (예약 연결 없이), PDF, 목록", "# 고객별 노트 (예약 연결 없이), PDF, 목록")],
 "tests/test_match_request.py": [(H, "매칭·상담 요청: 수수료, 중복 방지, 수락·거절")],
 "tests/test_password_login.py": [(H, "비밀번호 해시와 아이디/비밀번호 로그인")],
 "tests/test_payment.py": [(H, "결제 기록: 등록 권한, 수강권 연결, 조회 범위, 상태 변경")],
 "tests/test_posts.py": [(H, "게시물: 작성 권한, 목록·검색 노출 범위, 댓글, 좋아요, 미디어")],
 "tests/test_users.py": [(H, "푸시 토큰 저장·삭제와 내 정보")],
}
print("변경 파일:", apply(REPO + "/backend", spec))
