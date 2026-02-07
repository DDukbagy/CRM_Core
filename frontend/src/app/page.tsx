import HealthTest from "@/components/HealthTest";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-white">
      <h1 className="text-4xl font-bold text-blue-600 mb-4">
        CRM Frontend 준비 완료 🚀
      </h1>
      <p className="text-xl text-gray-600 mb-8">
        src 디렉토리 구조로 전환되었습니다.
      </p>

      {/* 방금 만든 통신 테스트 컴포넌트 추가 */}
      <HealthTest />
    </main>
  );
}