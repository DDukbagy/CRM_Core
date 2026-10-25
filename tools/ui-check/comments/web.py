import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))  # 저장소 루트
import sys; sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from lib import apply
H, A, R = "head", "above", "rep"
P = "// frontend/src/"
def first(path, new):  # 첫 줄의 파일 경로 주석을 설명으로 바꾼다
    return (R, f"{P}{path}\n", f"// {new}\n")
spec = {
 "src/app/(protected)/admin/analytics/page.tsx": [first("app/(protected)/admin/analytics/page.tsx — 준비 중", "관리자 영업/통계 (준비 중)")],
 "src/app/(protected)/admin/instructors/page.tsx": [first("app/(protected)/admin/instructors/page.tsx — 준비 중", "관리자 강사 관리 (준비 중)")],
 "src/app/(protected)/admin/system/page.tsx": [first("app/(protected)/admin/system/page.tsx — 준비 중", "관리자 시스템 관리 (준비 중)")],
 "src/app/(protected)/admin/page.tsx": [first("app/(protected)/admin/page.tsx", "관리자 대시보드")],
 "src/app/(protected)/instructor/customers/page.tsx": [(H, "강사 웹 고객 관리: 담당 고객 목록·검색, 전화번호·이메일로 등록")],
 "src/app/(protected)/instructor/page.tsx": [(H, "강사 웹 대시보드: 통계, 레슨 신청 확정·거절, 취소 신청 처리, 오늘 예약 완료·노쇼")],
 "src/app/(protected)/instructor/posts/page.tsx": [(H, "강사 웹 게시물: 작성·수정·삭제, 미디어 업로드, 댓글")],
 "src/app/(protected)/instructor/profile/page.tsx": [(H, "강사 웹 내 정보: 강사 프로필 편집, 정기 휴무 요일")],
 "src/app/(protected)/instructor/revenue/page.tsx": [(H, "강사 웹 매출: 결제 내역, 수동 결제 등록")],
 "src/app/(protected)/instructor/notes/page.tsx": [(R, "// 피드백 게시물을 레슨노트로 통합\n", "")],
 "src/app/(protected)/instructor/promotions/page.tsx": [],
 "src/app/(protected)/instructor/insights/page.tsx": [],
 "src/app/(protected)/instructor/schedule/page.tsx": [first("app/(protected)/instructor/schedule/page.tsx", "강사 웹 스케줄: 시간 슬롯 추가·켜기/끄기·삭제")],
 "src/app/(protected)/layout.tsx": [first("app/(protected)/layout.tsx", "로그인이 필요한 화면 공통 레이아웃")],
 "src/app/api/[...path]/route.ts": [first("app/api/[...path]/route.ts", "백엔드 프록시: 브라우저 요청에 Supabase 토큰을 붙여 FastAPI 로 전달")],
 "src/app/api/auth/sync/route.ts": [first("app/api/auth/sync/route.ts", "로그인 직후 세션 쿠키 갱신")],
 "src/app/error.tsx": [first("app/error.tsx", "전역 오류 화면")],
 "src/app/forbidden/page.tsx": [first("app/forbidden/page.tsx", "권한 없음 화면")],
 "src/app/layout.tsx": [first("app/layout.tsx", "루트 레이아웃")],
 "src/app/login/actions.ts": [first("app/login/actions.ts", "로그인 서버 액션")],
 "src/app/login/page.tsx": [first("app/login/page.tsx", "로그인 화면: Supabase 로그인 후 역할별 화면으로 이동")],
 "src/app/not-found.tsx": [first("app/not-found.tsx", "404 화면")],
 "src/app/page.tsx": [first("app/page.tsx", "루트(/): 바로 /login 으로 보냄")],
 "src/app/schedule/page.tsx": [(H, "스케줄 화면 (기본 사이드바 메뉴)")],
 "src/components/common/ComingSoon.tsx": [(R, "// 아직 만들지 않은 화면 자리 (고객 앱 스토어 탭과 같은 \"준비 중\" 안내)", "// 아직 만들지 않은 화면의 \"준비 중\" 안내")],
 "src/components/layout/DashboardLayout.tsx": [first("components/layout/DashboardLayout.tsx", "대시보드 공통 레이아웃: 사이드바 메뉴, 헤더, 로그아웃"),
    (R, "  // 로그아웃 (최소/확실)", "  // 로그아웃"), (R, "      {/* 사이드바 (Sidebar) */}", "      {/* 사이드바 */}")],
 "src/lib/axios.ts": [first("lib/axios.ts", "API 클라이언트: 항상 /api 프록시로 요청")],
 "src/lib/providers.tsx": [first("lib/providers.tsx", "앱 공통 Provider: TanStack Query, Supabase 세션 감지"),
    (R, " * Supabase Client (운영 인증 단일 기준)", " * Supabase 클라이언트 (인증 기준)")],
 "src/lib/supabase/client.ts": [first("lib/supabase/client.ts", "브라우저용 Supabase 클라이언트"),
    (R, " * 기존 코드(Topbar/DashboardLayout)가 기대하는 export", " * 공용 인스턴스 (DashboardLayout 등에서 사용)")],
 "src/lib/supabase/server.ts": [first("lib/supabase/server.ts", "서버용 Supabase 클라이언트 (쿠키 세션)")],
 "src/proxy.ts": [first("proxy.ts", "접근 제어: 로그인 확인, /admin·/instructor 는 역할 확인")],
}
print("변경 파일:", apply(REPO + "/frontend", spec, ts=True))
