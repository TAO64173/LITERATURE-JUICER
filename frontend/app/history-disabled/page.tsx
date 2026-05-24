"use client";

import { useState, useEffect, useCallback } from "react";
import { Navbar } from "@/components/Navbar";
import { showToast } from "@/components/Toast";
import { fetchHistory, type HistoryRecord } from "@/lib/api";

export default function HistoryPage() {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const loadHistory = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchHistory();
      setRecords(data);
    } catch {
      showToast("获取历史记录失败", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleDownload = (resultUrl: string | null) => {
    if (!resultUrl) return;
    const proxyUrl = `/api/proxy${resultUrl.startsWith("/") ? resultUrl : `/${resultUrl}`}`;
    window.open(proxyUrl, "_blank");
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const statusBadge = (status: HistoryRecord["status"]) => {
    const map: Record<HistoryRecord["status"], { label: string; cls: string }> = {
      completed: { label: "已完成", cls: "bg-green-50 text-green-700 ring-green-600/20" },
      processing: { label: "处理中", cls: "bg-yellow-50 text-yellow-700 ring-yellow-600/20" },
      failed: { label: "失败", cls: "bg-red-50 text-red-700 ring-red-600/20" },
    };
    const { label, cls } = map[status];
    return (
      <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${cls}`}>
        {label}
      </span>
    );
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />

      <section className="pt-32 pb-20">
        <div className="mx-auto max-w-4xl px-6">
          <h1 className="text-2xl font-bold text-gray-900">解析历史</h1>
          <p className="mt-2 text-sm text-gray-500">查看过往的文献解析记录并重新下载 Excel</p>

          {loading ? (
            <div className="mt-12 text-center text-gray-400">加载中...</div>
          ) : records.length === 0 ? (
            <div className="mt-12 text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-gray-100">
                <svg className="h-7 w-7 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
              </div>
              <p className="text-gray-500">暂无解析记录</p>
              <a href="/" className="mt-4 inline-block text-sm text-blue-600 hover:underline">
                去上传文献
              </a>
            </div>
          ) : (
            <div className="mt-8 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">文件名</th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">时间</th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">状态</th>
                    <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {records.map((r) => (
                    <tr key={r.id} className="hover:bg-gray-50/50">
                      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">{r.filename}</td>
                      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">{formatDate(r.created_at)}</td>
                      <td className="whitespace-nowrap px-6 py-4">{statusBadge(r.status)}</td>
                      <td className="whitespace-nowrap px-6 py-4 text-right">
                        {r.status === "completed" && r.result_url ? (
                          <button
                            onClick={() => handleDownload(r.result_url)}
                            className="text-sm font-medium text-blue-600 hover:text-blue-800"
                          >
                            下载
                          </button>
                        ) : (
                          <span className="text-sm text-gray-300">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
