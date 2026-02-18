import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from "@/lib/providers";
import AuthShell from "@/components/auth/AuthShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Professional CRM",
  description: "Next-gen CRM for smart business",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {/* Providers로 가장 바깥을 감싸줍니다 */}
        <Providers>
          {/* 보안: /login 제외 모든 페이지는 인증+권한 확인 후 렌더링 */}
          <AuthShell>{children}</AuthShell>
        </Providers>
      </body>
    </html>
  );
}
