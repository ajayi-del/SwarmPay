/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output for efficient Docker/Railway deployment
  output: "standalone",

  // Suppress build warnings for missing optional dependencies
  webpack: (config) => {
    config.resolve.fallback = { ...config.resolve.fallback, fs: false, net: false, tls: false };
    return config;
  },
};

export default nextConfig;
