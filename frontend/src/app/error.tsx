"use client";

import { useEffect } from "react";

/**
 * 전역 에러 페이지
 * - 라우트 트리 생성 중 오류가 나더라도 안정적으로 렌더링되도록 제공합니다.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
        <h2 className="text-2xl font-bold text-gray-800">오류가 발생했습니다.</h2>
        <p className="text-gray-500 mt-2">잠시 후 다시 시도해 주세요.</p>

        <button
          onClick={reset}
          className="inline-block mt-6 px-4 py-2 rounded-xl bg-indigo-900 text-white font-semibold hover:bg-indigo-800 transition-colors"
        >
          다시 시도
        </button>
      </div>
    </div>
  );
}
