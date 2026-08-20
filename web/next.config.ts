import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "shopping-phinf.pstatic.net" },
      { protocol: "https", hostname: "shop-phinf.pstatic.net" },
    ],
  },
};

export default nextConfig;
