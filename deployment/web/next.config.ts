import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async redirects() {
    return [
      {
        source: "/regimes",
        destination: "/regime-intelligence",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;

