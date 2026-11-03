import os; REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))  # 저장소 루트
import sys; sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from lib import apply
H, A, R = "head", "above", "rep"
def first(old, new): return (R, f"// {old}\n", f"// {new}\n")
customer = {
 "app/(auth)/login.tsx": [first("app/(auth)/login.tsx", "로그인 화면 (Supabase, 고객 계정만)")],
 "app/(tabs)/_layout.tsx": [first("app/(tabs)/_layout.tsx", "하단 탭 구성과 커스텀 탭 바"), (R, "// Custom Tab Bar", "// 커스텀 탭 바"), (R, "// Layout\n", "// 탭 레이아웃\n"), (R, "// Styles\n", "// 스타일\n")],
 "app/(tabs)/bookings.tsx": [first("app/(tabs)/bookings.tsx — 예약 목록", "예약 탭: 내 예약 목록과 상태별 보기")],
 "app/(tabs)/chat.tsx": [(H, "채팅 탭: 강사와의 채팅방 목록·대화, 담당 강사 지정 (모임 채팅은 준비 중)")],
 "app/(tabs)/index.tsx": [first("app/(tabs)/index.tsx", "홈 탭: 담당 강사, 다가오는 예약, 알림")],
 "app/(tabs)/match.tsx": [first("app/(tabs)/match.tsx", "강사 찾기 탭: 단계별 매칭, 강사 목록, 상세 프로필에서 문의하기"), (R, "// 숨고식 단계별 매칭", "// 단계별 매칭")],
 "app/(tabs)/notes.tsx": [(R, "를 본다. 피드백 게시물을 여기로 통합", "를 본다")],
 "app/(tabs)/passes.tsx": [(H, "수강권 탭: 내 수강권, 담당 강사의 수강권 상품과 진행 중인 프로모션")],
 "app/(tabs)/posts.tsx": [first("app/(tabs)/posts.tsx", "게시물 탭: 강사 게시물 피드, 미디어, 댓글, 좋아요")],
 "app/(tabs)/profile.tsx": [first("app/(tabs)/profile.tsx", "내 정보 탭: 프로필, 정보 수정, 로그아웃, 회원 탈퇴")],
 "app/(tabs)/schedule.tsx": [first("app/(tabs)/schedule.tsx", "예약하기 탭: 월간 달력, 날짜별 예약 가능 시간, 레슨 신청·상세")],
 "app/(tabs)/store.tsx": [(H, "스토어 탭 (준비 중)")],
 "app/_layout.tsx": [first("app/_layout.tsx", "앱 루트: 로그인 상태에 따라 화면 이동, Sentry")],
 "app/booking/[id].tsx": [first("app/booking/[id].tsx", "예약 상세 화면")],
 "app/edit-profile.tsx": [first("app/edit-profile.tsx", "정보 수정 화면 (피드백 공개 동의 포함)")],
 "lib/alert.ts": [(R, "폰은 기존 Alert.alert 그대로", "폰은 Alert.alert")],
 "lib/api.ts": [first("lib/api.ts", "API 클라이언트: Supabase 토큰을 붙여 백엔드 호출")],
 "lib/bookingUtils.ts": [(R, "// Types\n", "// 타입\n"), (R, "// Booking status UI 상수", "// 예약 상태 표시")],
 "lib/config.ts": [first("lib/config.ts", "환경 설정 (EXPO_PUBLIC_ 변수)")],
 "lib/supabase.ts": [first("lib/supabase.ts", "Supabase 클라이언트 (세션 저장)")],
 "types/api.ts": [first("types/api.ts", "API 응답 타입 (백엔드 schemas.py 와 맞춘다)"), (R, "// 레슨 노트 (피드백 게시물을 통합). file_url", "// 레슨 노트. file_url")],
}
instructor = {
 "app/(auth)/login.tsx": [(H, "로그인 화면 (Supabase, 강사 계정만)")],
 "app/(tabs)/_layout.tsx": [(H, "하단 탭 구성")],
 "app/(tabs)/chat.tsx": [(H, "채팅 탭: 고객과의 채팅방 목록·대화")],
 "app/(tabs)/customers.tsx": [(H, "고객 탭: 담당 고객 목록, 전화번호·이메일로 등록")],
 "app/(tabs)/index.tsx": [(H, "홈 탭: 통계, 레슨 신청 처리, 오늘 예약")],
 "app/(tabs)/notes.tsx": [(R, "// 피드백 게시물을 여기로 통합. 고객은 고객 앱 레슨노트 탭에서 본다", "// 고객은 고객 앱 레슨노트 탭에서 본다")],
 "app/(tabs)/posts.tsx": [(H, "게시물 탭: 작성·수정·삭제, 미디어 업로드, 댓글"),
    (R, "        // 1. 서버에서 presigned PUT URL 발급\n", "        // 업로드 주소를 받아 S3 에 바로 올린다 (FormData 없이 PUT, RN 에서 안정적)\n"),
    (R, "        // 2. S3에 직접 PUT (FormData 없음 — RN에서 안정적)\n", ""), (R, "      // 3. 로컬 URI → S3 URL 교체\n", "")],
 "app/(tabs)/profile.tsx": [(H, "내 정보 탭: 강사 프로필, 정기 휴무 요일, 로그아웃")],
 "app/(tabs)/revenue.tsx": [(H, "매출 탭: 결제 내역, 수동 결제 등록, 운영 현황 이동")],
 "app/(tabs)/schedule.tsx": [(H, "스케줄 탭: 월간 달력, 날짜별 예약·휴무 관리"), (R, "(work override 복원 방지용)", "(그날 휴무 처리 전 확인용)")],
 "app/_layout.tsx": [(H, "앱 루트: 로그인 상태에 따라 화면 이동, Sentry")],
 "app/customer/[id].tsx": [(H, "고객 상세: 정보, 예약 통계, 발급한 수강권"), (R, "  // 이 고객에게 발급한 수강권 (멤버십은 수강권으로 통합)", "  // 이 고객에게 발급한 수강권")],
 "lib/alert.ts": [(R, "폰은 기존 Alert.alert 그대로", "폰은 Alert.alert")],
 "lib/api.ts": [(H, "API 클라이언트: Supabase 토큰을 붙여 백엔드 호출")],
 "lib/bookingUtils.ts": [(R, "// Types\n", "// 타입\n"), (R, "// Booking status UI 상수", "// 예약 상태 표시")],
 "lib/config.ts": [(H, "환경 설정 (EXPO_PUBLIC_ 변수)")],
 "lib/customerRegisterContext.tsx": [(H, "고객 등록 모달 열기 상태 공유")],
 "lib/supabase.ts": [(H, "Supabase 클라이언트 (세션 저장)")],
 "types/api.ts": [(H, "API 응답 타입 (백엔드 schemas.py 와 맞춘다)"), (R, "// 레슨 노트 (피드백 게시물을 통합). file_url", "// 레슨 노트. file_url")],
}
print("고객 앱:", apply(REPO + "/apps/customer", customer, ts=True))
print("강사 앱:", apply(REPO + "/apps/instructor", instructor, ts=True))
