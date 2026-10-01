import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import "./globals.css";

const body = Be_Vietnam_Pro({ subsets: ["vietnamese", "latin"], weight: ["400", "500", "600", "700"], variable: "--font-body" });

export const metadata: Metadata = { title: "Kiểm tra hồ sơ thuế" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className={body.variable}>
      <body>{children}</body>
    </html>
  );
}
