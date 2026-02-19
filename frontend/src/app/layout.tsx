import type { Metadata } from "next";
import "./globals.css";

/**
 * Root Layout
 * - Next App Router가 내부 _not-found 트리를 만들 때도 반드시 참조됩니다.
 */
export const metadata: Metadata = {
  title: "CRM",
  description: "CRM Admin/Instructor",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
