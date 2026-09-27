import type { Metadata } from "next";

import { Toaster } from "sonner";

import "./globals.css";

export const metadata: Metadata = {
  title: "Summer Checkin",
  description: "每日打卡、复盘与巡检",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="bg-background text-foreground antialiased">
        {children}
        <Toaster position="top-center" />
      </body>
    </html>
  );
}
