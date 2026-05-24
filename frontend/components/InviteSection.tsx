"use client";

import { useState, useEffect } from "react";
import { showToast } from "@/components/Toast";
import { fetchInviteInfo } from "@/lib/api";

export function InviteSection() {
  const [copied, setCopied] = useState<"code" | "link" | null>(null);
  const [inviteCode, setInviteCode] = useState("");
  const [invitedCount, setInvitedCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchInviteInfo()
      .then((data) => {
        if (data.success) {
          setInviteCode(data.invite_code);
          setInvitedCount(data.invited_count);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const inviteLink = inviteCode
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/sign-up?ref=${inviteCode}`
    : "";

  const handleCopy = async (text: string, type: "code" | "link") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(type);
      showToast(type === "code" ? "邀请码已复制" : "邀请链接已复制", "success");
      setTimeout(() => setCopied(null), 2000);
    } catch {
      showToast("复制失败，请手动复制", "error");
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
        <div className="animate-pulse space-y-3">
          <div className="h-4 w-32 rounded bg-gray-200" />
          <div className="h-10 w-full rounded bg-gray-100" />
          <div className="h-10 w-full rounded bg-gray-100" />
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50">
          <svg
            className="h-5 w-5 text-purple-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"
            />
          </svg>
        </div>
        <div>
          <h3 className="text-base font-bold text-gray-900">邀请好友得额度</h3>
          <p className="text-xs text-gray-400">每成功邀请 1 位好友，可获得 2 篇额外解析次数</p>
        </div>
      </div>

      {invitedCount > 0 && (
        <div className="mb-3 rounded-lg bg-green-50 px-4 py-2 text-sm text-green-700">
          已成功邀请 {invitedCount} 位好友，获得 {invitedCount * 2} 篇额度
        </div>
      )}

      <div className="space-y-3">
        {/* Invite code */}
        <div className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3">
          <div>
            <span className="text-xs text-gray-400">我的邀请码</span>
            <p className="font-mono text-lg font-bold tracking-wider text-gray-900">
              {inviteCode || "—"}
            </p>
          </div>
          <button
            onClick={() => inviteCode && handleCopy(inviteCode, "code")}
            disabled={!inviteCode}
            className="rounded-md bg-white px-3 py-1.5 text-xs font-medium text-gray-600 shadow-sm ring-1 ring-gray-200 transition-all hover:bg-gray-50 disabled:opacity-50"
          >
            {copied === "code" ? "已复制 ✓" : "复制邀请码"}
          </button>
        </div>

        {/* Invite link */}
        <div className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3">
          <div className="min-w-0">
            <span className="text-xs text-gray-400">邀请链接</span>
            <p className="truncate font-mono text-sm text-gray-500">{inviteLink || "—"}</p>
          </div>
          <button
            onClick={() => inviteLink && handleCopy(inviteLink, "link")}
            disabled={!inviteLink}
            className="ml-3 shrink-0 rounded-md bg-white px-3 py-1.5 text-xs font-medium text-gray-600 shadow-sm ring-1 ring-gray-200 transition-all hover:bg-gray-50 disabled:opacity-50"
          >
            {copied === "link" ? "已复制 ✓" : "复制邀请链接"}
          </button>
        </div>
      </div>
    </div>
  );
}
