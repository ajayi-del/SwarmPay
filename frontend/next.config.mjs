/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow NEXT_PUBLIC_API_URL to be set at runtime via Railway env vars
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
  // Standalone output for efficient Docker/Railway deployment
  output: "standalone",
};

export default nextConfig;
