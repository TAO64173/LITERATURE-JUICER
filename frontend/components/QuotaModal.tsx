"use client";

import { useState } from "react";
import { showToast } from "@/components/Toast";
import { createOrder } from "@/lib/api";

interface QuotaModalProps {
  open: boolean;
  onClose: () => void;
}

export function QuotaModal({ open, onClose }: QuotaModalProps) {
  const [loading, setLoading] = useState<number | null>(null);

  if (!open) return null;

  const handleBuy = async (amount: number) => {
    setLoading(amount);
    try {
      const data = await createOrder(amount);
      if (data.success && data.payUrl) {
        window.location.href = data.payUrl;
      } else {
        showToast(data.message || "创建订单失败", "error");
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : "网络错误，请稍后重试", "error");
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Modal */}
      <div className="relative mx-4 w-full max-w-md animate-fade-in rounded-2xl bg-white p-6 shadow-xl">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-gray-300 hover:text-gray-500"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-orange-50">
            <svg
              className="h-7 w-7 text-orange-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-gray-900">免费额度已用完</h3>
          <p className="mt-1 text-sm text-gray-500">升级套餐继续解析更多文献</p>
        </div>

        <div className="mt-6 space-y-3">
          <button
            onClick={() => handleBuy(8.8)}
            disabled={loading !== null}
            className="flex w-full items-center justify-between rounded-xl border border-gray-100 bg-white px-5 py-4 text-left transition-all hover:border-blue-200 hover:bg-blue-50/50 disabled:opacity-60"
          >
            <div>
              <p className="text-sm font-bold text-gray-900">基础包</p>
              <p className="text-xs text-gray-400">10 篇解析额度</p>
            </div>
            <span className="text-lg font-extrabold text-gray-900">
              {loading === 8.8 ? "处理中…" : "¥8.8"}
            </span>
          </button>
          <button
            onClick={() => handleBuy(15)}
            disabled={loading !== null}
            className="flex w-full items-center justify-between rounded-xl border border-blue-200 bg-blue-50/50 px-5 py-4 text-left ring-1 ring-blue-200 transition-all hover:bg-blue-50 disabled:opacity-60"
          >
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-bold text-gray-900">专业包</p>
                <span className="rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-semibold text-white">
                  推荐
                </span>
              </div>
              <p className="text-xs text-gray-400">20 篇解析额度</p>
            </div>
            <span className="text-lg font-extrabold text-gray-900">
              {loading === 15 ? "处理中…" : "¥15"}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
