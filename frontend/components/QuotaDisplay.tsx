"use client";

import { useEffect, useState } from "react";
import { fetchQuota } from "@/lib/api";

interface QuotaDisplayProps {
  refreshKey?: number;
}

export function QuotaDisplay({ refreshKey }: QuotaDisplayProps) {
  const [quota, setQuota] = useState<{
    total: number;
    used: number;
    remaining: number;
    role: "admin" | "user";
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchQuota()
      .then((data) => {
        if (!cancelled && data.success) {
          setQuota({
            total: data.total,
            used: data.used,
            remaining: data.remaining,
            role: data.role,
          });
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  if (loading) {
    return (
      <div className="h-7 w-24 animate-pulse rounded-md bg-gray-100" />
    );
  }

  if (!quota) return null;

  // Admin display
  if (quota.role === "admin") {
    return (
      <div className="flex items-center gap-1.5 rounded-full bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 border border-purple-200">
        <svg
          className="h-3.5 w-3.5 text-purple-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
          />
        </svg>
        <span>管理员账号 · 无限额度</span>
      </div>
    );
  }

  // Normal user display
  const isNewUser = quota.used === 0 && quota.remaining === 3;

  return (
    <div className="flex items-center gap-1.5 rounded-full bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-200">
      <svg
        className="h-3.5 w-3.5 text-blue-500"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1"
        />
      </svg>
      {isNewUser ? (
        <span>
          <span className="text-green-600 font-semibold">新用户赠送 3 篇</span>
          {" · 剩余 "}
          <span className="text-blue-600 font-semibold">{quota.remaining}</span>
          {" 篇"}
        </span>
      ) : (
        <span>
          剩余额度：
          <span
            className={
              quota.remaining > 0 ? "text-blue-600 font-semibold" : "text-red-500 font-semibold"
            }
          >
            {quota.remaining}
          </span>
          {" 篇"}
        </span>
      )}
    </div>
  );
}
