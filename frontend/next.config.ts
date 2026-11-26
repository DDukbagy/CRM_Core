import type { NextConfig } from "next";

const dev = process.env.NODE_ENV !== "production";

// 브라우저가 이 사이트에서 불러와도 되는 것의 목록 (Content-Security-Policy)
// 화면에 스크립트가 끼어들더라도 다른 사이트의 스크립트를 불러오거나, 다른 사이트로 데이터를 보내거나, 이 사이트를 틀 안에 넣지 못하게 한다.
// - API 는 같은 주소의 /api 프록시로만 부른다 → connect-src 'self'. S3 는 사진·영상을 서명 주소로 직접 올리고 보여 주기 때문에 연다
// - script-src 의 'unsafe-inline' 은 Next.js 가 페이지에 넣는 인라인 스크립트 때문에 남겨 둔다.
//   없애려면 요청마다 nonce 를 붙여야 한다 (모든 페이지가 동적 렌더링이 된다). 지금은 하지 않았다
const S3 = "https://*.amazonaws.com";
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${S3}`,
  `media-src 'self' blob: ${S3}`,
  `connect-src 'self' ${S3}${dev ? " ws:" : ""}`,
  "font-src 'self' data:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
];

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
