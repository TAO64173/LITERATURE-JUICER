"use client";

import { useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { InviteSection } from "@/components/InviteSection";

const plans = [
  {
    name: "免费版",
    price: "¥0",
    period: "",
    features: ["注册即送 3 篇解析额度", "PDF 智能解析", "AI 变量提取", "Excel 结构化输出"],
    button: "立即开始",
    href: "/sign-up",
    highlight: false,
  },
  {
    name: "基础包",
    price: "¥8.8",
    period: "",
    features: ["10 篇解析额度", "PDF 智能解析", "AI 变量提取", "Excel 结构化输出", "批量处理"],
    button: "立即购买",
    href: "#",
    highlight: false,
  },
  {
    name: "专业包",
    price: "¥15",
    period: "",
    badge: "推荐",
    features: ["20 篇解析额度", "PDF 智能解析", "AI 变量提取", "Excel 结构化输出", "批量处理", "优先处理队列"],
    button: "立即购买",
    href: "#",
    highlight: true,
  },
];

export default function PricingPage() {
  const [quotaRefreshKey, setQuotaRefreshKey] = useState(0);

  return (
    <div className="flex min-h-screen flex-col pt-28 pb-20">
      <Navbar quotaRefreshKey={quotaRefreshKey} />
      {/* Header */}
      <div className="mx-auto max-w-5xl px-6 text-center">
        <h1 className="text-3xl font-extrabold tracking-tight text-gray-900 sm:text-4xl">
          选择适合你的方案
        </h1>
        <p className="mt-3 text-gray-500">
          注册即送 3 篇免费额度，按需购买更多
        </p>
      </div>

      {/* Pricing cards */}
      <div className="mx-auto mt-12 max-w-5xl px-6">
        <div className="grid gap-6 sm:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative flex flex-col rounded-2xl border p-6 transition-all ${
                plan.highlight
                  ? "border-blue-200 bg-blue-50/50 shadow-md ring-1 ring-blue-200"
                  : "border-gray-100 bg-white shadow-sm hover:shadow-md"
              }`}
            >
              {plan.badge && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-3 py-0.5 text-xs font-semibold text-white">
                  {plan.badge}
                </span>
              )}
              <h3 className="text-lg font-bold text-gray-900">{plan.name}</h3>
              <div className="mt-3">
                <span className="text-4xl font-extrabold text-gray-900">{plan.price}</span>
                {plan.period && <span className="ml-1 text-sm text-gray-400">{plan.period}</span>}
              </div>
              <ul className="mt-6 flex-1 space-y-3">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-gray-600">
                    <svg
                      className="mt-0.5 h-4 w-4 shrink-0 text-green-500"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2.5}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href={plan.href}
                className={`mt-6 block rounded-lg px-4 py-2.5 text-center text-sm font-semibold transition-all ${
                  plan.highlight
                    ? "bg-blue-600 text-white hover:bg-blue-700"
                    : "border border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                }`}
              >
                {plan.button}
              </Link>
            </div>
          ))}
        </div>
      </div>

      {/* Invite section */}
      <div className="mx-auto mt-8 max-w-2xl px-6">
        <InviteSection />
      </div>

      {/* Back to home */}
      <div className="mt-12 text-center">
        <Link href="/" className="text-sm text-gray-400 hover:text-gray-600">
          ← 返回首页
        </Link>
      </div>
    </div>
  );
}
