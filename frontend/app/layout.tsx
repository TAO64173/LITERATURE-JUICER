import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { zhCN } from "@clerk/localizations";
import { AuthBar } from "@/components/AuthBar";
import { ToastContainer } from "@/components/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "Literature Juicer - AI 文献榨汁机",
  description:
    "上传 PDF，AI 自动提取核心变量，生成结构化 Excel 表格，让文献综述不再痛苦。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider localization={zhCN} afterSignOutUrl="/sign-in">
      <html lang="zh-CN" className="h-full antialiased">
        <body className="flex min-h-full flex-col bg-white font-sans text-gray-900">
          <AuthBar />
          {children}
          <ToastContainer />
        </body>
      </html>
    </ClerkProvider>
  );
}
