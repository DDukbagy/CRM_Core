/**
 * 전역 404 페이지
 * - Next가 내부 _not-found 트리를 만들지 않도록 명시적으로 제공합니다.
 */
export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
        <h2 className="text-2xl font-bold text-gray-800">페이지를 찾을 수 없습니다.</h2>
        <p className="text-gray-500 mt-2">요청하신 주소가 존재하지 않습니다.</p>
        <a
          href="/login"
          className="inline-block mt-6 px-4 py-2 rounded-xl bg-indigo-900 text-white font-semibold hover:bg-indigo-800 transition-colors"
        >
          로그인으로 이동
        </a>
      </div>
    </div>
  );
}
