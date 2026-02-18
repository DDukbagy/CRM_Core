// src/app/admin/page.tsx
import StatsCards from "@/components/dashboard/StatsCards";

export default function AdminPage() {
  return (
    <div>
      {/* 1. 상단 인사말 */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-800">안녕하세요, 관리자님! 👋</h2>
        <p className="text-gray-500 mt-1">오늘의 시스템/비즈니스 현황을 한눈에 확인하세요.</p>
      </div>

      {/* 2. 핵심 지표 카드 */}
      <StatsCards />

      {/* 3. 하단 섹션: 최근 활동 & 빠른 실행 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* 왼쪽: 최근 가입 고객 리스트 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="p-6 border-b border-gray-100 flex justify-between items-center">
            <h3 className="font-semibold text-gray-800">최근 가입 고객</h3>
            <button className="text-sm text-blue-600 hover:underline">모두 보기</button>
          </div>
          <div className="divide-y divide-gray-100">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="p-4 flex items-center hover:bg-gray-50 transition-colors cursor-pointer"
              >
                <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-gray-500 font-bold">
                  U{i}
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-900">새로운 고객 {i}</p>
                  <p className="text-xs text-gray-500">user{i}@example.com</p>
                </div>
                <div className="ml-auto text-xs text-gray-400">2시간 전</div>
              </div>
            ))}
          </div>
        </div>

        {/* 오른쪽: 빠른 작업 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-800 mb-4">빠른 작업</h3>
          <div className="space-y-3">
            <button className="w-full text-left px-4 py-3 bg-gray-50 hover:bg-blue-50 hover:text-blue-600 rounded-lg transition-colors text-sm font-medium text-gray-700">
              + 강사 등록 승인 처리하기
            </button>
            <button className="w-full text-left px-4 py-3 bg-gray-50 hover:bg-blue-50 hover:text-blue-600 rounded-lg transition-colors text-sm font-medium text-gray-700">
              + 시스템 공지 등록하기
            </button>
            <button className="w-full text-left px-4 py-3 bg-gray-50 hover:bg-blue-50 hover:text-blue-600 rounded-lg transition-colors text-sm font-medium text-gray-700">
              + 팀원 초대/권한 관리하기
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
