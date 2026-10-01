/** Mọi lời gọi /api/* được chuyển tới FastAPI, để trình duyệt chỉ nói chuyện với một origin. */
const backend = process.env.BACKEND_URL || "http://localhost:8000";

export default {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
};
