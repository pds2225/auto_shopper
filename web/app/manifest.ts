import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "장보기 — 어디서나 쓰는 쇼핑 도우미",
    short_name: "장보기",
    description: "휴대폰·PC에서 네이버 쇼핑 검색",
    start_url: "/",
    display: "standalone",
    background_color: "#f4efe6",
    theme_color: "#14382c",
    lang: "ko",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
