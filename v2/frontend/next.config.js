/** @type {import('next').NextConfig} */
const apiRewriteTarget = (
  process.env.API_REWRITE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"
).replace(/\/$/, "");

const nextConfig = {
  output: "standalone",
  // Долгие ИИ-запросы (оффер/оценка) через rewrite /api → backend
  experimental: {
    proxyTimeout: 1000 * 180,
  },
  async rewrites() {
    // D4: same-origin /api/v1/* → backend (cookies + EventSource).
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiRewriteTarget}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
