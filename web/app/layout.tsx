import type { Metadata, Viewport } from "next";
import { Noto_Sans_KR } from "next/font/google";
import "./globals.css";

const notoSansKr = Noto_Sans_KR({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: "swap",
  variable: "--font-noto-sans-kr",
  preload: true,
});

export const metadata: Metadata = {
  title: "장보기 — 어디서나 쓰는 쇼핑 도우미",
  description: "휴대폰과 PC에서 네이버 쇼핑을 검색하고 가격을 비교합니다. 결제는 직접.",
  applicationName: "장보기",
  formatDetection: { telephone: false },
  appleWebApp: {
    capable: true,
    title: "장보기",
    statusBarStyle: "default",
  },
  icons: {
    icon: "/icon.svg",
    apple: "/icon.svg",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#14382c",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={notoSansKr.variable}>
      <body>{children}</body>
    </html>
  );
}
