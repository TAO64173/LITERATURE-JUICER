"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { checkPaymentStatus } from "@/lib/api";

function PaymentSuccessContent() {
  const searchParams = useSearchParams();
  const orderId = searchParams.get("orderId");

  const [status, setStatus] = useState<"loading" | "success" | "timeout">("loading");
  const [credits, setCredits] = useState(0);

  useEffect(() => {
    if (!orderId) {
      setStatus("timeout");
      return;
    }

    let attempts = 0;
    const maxAttempts = 30; // 30 * 2s = 60s

    const poll = setInterval(async () => {
      attempts += 1;
      try {
        const data = await checkPaymentStatus(orderId);
        if (data.success && data.paid) {
          setCredits(data.credits);
          setStatus("success");
          clearInterval(poll);
        } else if (attempts >= maxAttempts) {
          setStatus("timeout");
          clearInterval(poll);
        }
      } catch {
        if (attempts >= maxAttempts) {
          setStatus("timeout");
          clearInterval(poll);
        }
      }
    }, 2000);

    return () => clearInterval(poll);
  }, [orderId]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="mx-4 w-full max-w-md rounded-2xl bg-white p-8 text-center shadow-lg">
        {status === "loading" && (
          <>
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />
            <h2 className="text-lg font-bold text-gray-900">正在确认支付结果…</h2>
            <p className="mt-2 text-sm text-gray-500">请稍候，正在与支付平台同步</p>
          </>
        )}

        {status === "success" && (
          <>
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-green-50">
              <svg className="h-7 w-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-gray-900">支付成功！</h2>
            <p className="mt-2 text-sm text-gray-500">已到账 <span className="font-semibold text-blue-600">{credits}</span> 篇解析额度</p>
            <Link
              href="/"
              className="mt-6 inline-block rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
            >
              返回首页
            </Link>
          </>
        )}

        {status === "timeout" && (
          <>
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-orange-50">
              <svg className="h-7 w-7 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-gray-900">支付超时</h2>
            <p className="mt-2 text-sm text-gray-500">请稍后查看额度是否已到账</p>
            <Link
              href="/"
              className="mt-6 inline-block rounded-lg bg-gray-900 px-6 py-2.5 text-sm font-semibold text-white hover:bg-gray-800"
            >
              返回首页
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function PaymentSuccessPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />
      </div>
    }>
      <PaymentSuccessContent />
    </Suspense>
  );
}
