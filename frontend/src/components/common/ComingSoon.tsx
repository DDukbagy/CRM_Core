// 아직 만들지 않은 화면 자리 (고객 앱 스토어 탭과 같은 "준비 중" 안내)
export default function ComingSoon({ title }: { title: string }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 p-6 text-center">
      <div className="text-5xl">🛠️</div>
      <h1 className="text-xl font-bold text-gray-900">{title}</h1>
      <p className="text-sm text-gray-400">준비 중입니다</p>
    </div>
  );
}
