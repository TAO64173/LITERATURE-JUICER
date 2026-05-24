"use client";

import Link from "next/link";
import { QuotaDisplay } from "./QuotaDisplay";

interface NavbarProps {
  quotaRefreshKey?: number;
}

export function Navbar({ quotaRefreshKey }: NavbarProps) {
  return (
    <nav className="fixed top-10 left-0 right-0 z-50 border-b border-gray-100 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 lg:px-12">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600">
            <svg
              className="h-4 w-4 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <span className="text-base font-bold tracking-tight text-gray-900">
            Literature Juicer
          </span>
        </Link>

        {/* Center nav links */}
        <div className="hidden items-center gap-7 md:flex">
          <a
            href="#features"
            className="text-sm text-gray-500 transition-colors hover:text-gray-900"
          >
            功能介绍
          </a>
          <a
            href="#upload"
            className="text-sm text-gray-500 transition-colors hover:text-gray-900"
          >
            使用指南
          </a>
          <Link
            href="/pricing"
            className="text-sm text-gray-500 transition-colors hover:text-gray-900"
          >
            定价
          </Link>
          {/* <Link
            href="/history"
            className="text-sm text-gray-500 transition-colors hover:text-gray-900"
          >
            History
          </Link> */}
        </div>

        {/* Right: quota */}
        <div className="flex items-center gap-3">
          <QuotaDisplay refreshKey={quotaRefreshKey} />
        </div>
      </div>
    </nav>
  );
}
