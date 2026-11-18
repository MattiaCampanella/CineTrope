const API = process.env.CINETROPE_API ?? "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  images: { remotePatterns: [{ protocol: "https", hostname: "image.tmdb.org" }] },
  // Il backend semantico (FastAPI) resta su :8000; il browser parla solo con Next.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};
