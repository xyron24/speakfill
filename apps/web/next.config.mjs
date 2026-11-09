/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    // Fallback so `npm run dev` outside compose can still reach the API.
    // In compose, browsers go through Caddy, which routes /api/* to the api service.
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_INTERNAL_URL || "http://api:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
