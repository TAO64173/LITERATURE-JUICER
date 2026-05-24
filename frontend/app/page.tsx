"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Navbar } from "@/components/Navbar";
import { UploadZone } from "@/components/UploadZone";
import { FileGrid, type FileItem } from "@/components/FileGrid";
import { ProgressBar } from "@/components/ProgressBar";
import { showToast } from "@/components/Toast";
import { ResultPreview } from "@/components/ResultPreview";
import { QuotaModal } from "@/components/QuotaModal";
import { uploadFiles, applyInviteCode, type UploadResult } from "@/lib/api";

const MAX_FILES = 20;
const MAX_SIZE = 10 * 1024 * 1024; // 10MB

export default function HomePage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState({ percent: 0, message: "", visible: false });
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [quotaRefreshKey, setQuotaRefreshKey] = useState(0);
  const [quotaModalOpen, setQuotaModalOpen] = useState(false);
  const downloadSectionRef = useRef<HTMLDivElement>(null);
  const previewSectionRef = useRef<HTMLDivElement>(null);

  const handleFilesAdded = useCallback(
    (newFiles: File[]) => {
      const validFiles: FileItem[] = [];
      for (const f of newFiles) {
        if (!f.name.toLowerCase().endsWith(".pdf")) {
          showToast(`${f.name} 不是 PDF 文件`, "error");
          continue;
        }
        if (f.size > MAX_SIZE) {
          showToast(`${f.name} 超过 10MB 限制`, "error");
          continue;
        }
        if (files.length + validFiles.length >= MAX_FILES) {
          showToast(`最多上传 ${MAX_FILES} 个文件`, "error");
          break;
        }
        validFiles.push({ name: f.name, size: f.size, file: f, status: "ready" });
      }
      if (validFiles.length > 0) {
        setFiles((prev) => [...prev, ...validFiles]);
      }
    },
    [files.length]
  );

  const handleRemove = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleProcess = useCallback(async () => {
    if (files.length === 0 || isProcessing) return;

    setIsProcessing(true);
    setDownloadUrl(null);
    setFiles((prev) => prev.map((f) => ({ ...f, status: "processing" as const })));
    setProgress({ percent: 50, message: "正在上传并解析文件...", visible: true });

    try {
      const result = await uploadFiles(files.map((f) => f.file));

      if (result.download_url) {
        setDownloadUrl(result.download_url);
        setResults(result.results || []);
        setFiles((prev) => prev.map((f) => (f.status === "processing" ? { ...f, status: "done" } : f)));
        setQuotaRefreshKey((k) => k + 1);
        showToast("文献解析完成！", "success");
        setTimeout(() => downloadSectionRef.current?.scrollIntoView({ behavior: "smooth" }), 300);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "处理过程中发生错误";
      if (msg.includes("额度") || msg.includes("quota")) {
        setQuotaModalOpen(true);
      } else {
        showToast(msg, "error");
      }
      setFiles((prev) => prev.map((f) => (f.status === "processing" ? { ...f, status: "error" } : f)));
    } finally {
      setIsProcessing(false);
      setProgress((p) => ({ ...p, visible: false }));
    }
  }, [files, isProcessing]);

  const handleDownload = useCallback(() => {
    if (downloadUrl) {
      const proxyUrl = `/api/proxy${downloadUrl}`;
      window.open(proxyUrl, "_blank");
      showToast("开始下载 Excel 文件", "success");
    }
  }, [downloadUrl]);

  const handleReset = useCallback(() => {
    setFiles([]);
    setDownloadUrl(null);
    setResults([]);
    setShowPreview(false);
    setProgress({ percent: 0, message: "", visible: false });
  }, []);

  const scrollToUpload = useCallback(() => {
    document.getElementById("upload-section")?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (showPreview && previewSectionRef.current) {
      previewSectionRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [showPreview]);

  // Apply pending invite code after sign-up
  useEffect(() => {
    const pendingCode = localStorage.getItem("pending_invite_code");
    if (pendingCode) {
      applyInviteCode(pendingCode)
        .then((res) => {
          if (res.success) {
            showToast(res.message, "success");
            setQuotaRefreshKey((k) => k + 1);
          }
        })
        .catch(() => {})
        .finally(() => {
          localStorage.removeItem("pending_invite_code");
        });
    }
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar quotaRefreshKey={quotaRefreshKey} />
      <QuotaModal open={quotaModalOpen} onClose={() => setQuotaModalOpen(false)} />

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-32 pb-20">
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-0 left-1/2 h-[600px] w-[1200px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 opacity-60" />
        </div>

        <div className="mx-auto max-w-7xl px-6">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div className="animate-fade-in">
              <h1 className="text-5xl font-extrabold tracking-tight text-gray-900 sm:text-6xl">
                <span className="gradient-text">AI 文献榨汁机</span>
              </h1>
              <p className="mt-6 text-lg leading-relaxed text-gray-600">
                上传 PDF，AI 自动提取核心变量——研究问题、方法、指标、创新点、局限性，一键生成结构化 Excel 表格，让文献综述不再痛苦。
              </p>
              <div className="mt-8 flex gap-4">
                <button
                  onClick={scrollToUpload}
                  className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 hover:shadow-md"
                >
                  开始上传
                </button>
                <a
                  href="#features"
                  className="rounded-lg border border-gray-200 px-6 py-3 text-sm font-semibold text-gray-700 transition-all hover:border-gray-300 hover:bg-gray-50"
                >
                  了解更多
                </a>
              </div>
            </div>

            {/* Paper stack illustration */}
            <div className="relative hidden h-[360px] lg:block">
              <div className="paper-stack" style={{ position: "relative", right: "auto", top: "auto", transform: "none" }}>
                <div className="paper paper-1">
                  <div className="paper-header" />
                  <div className="paper-rows">
                    <div className="paper-row">
                      <div className="paper-bar accent" style={{ width: "70%" }} />
                      <div className="paper-bar" style={{ width: "30%" }} />
                    </div>
                    <div className="paper-row">
                      <div className="paper-bar" style={{ width: "45%" }} />
                      <div className="paper-bar accent" style={{ width: "55%" }} />
                    </div>
                    <div className="paper-row">
                      <div className="paper-bar" style={{ width: "80%" }} />
                    </div>
                  </div>
                </div>
                <div className="paper paper-2">
                  <div className="paper-header" />
                  <div className="paper-rows">
                    <div className="paper-row">
                      <div className="paper-bar" style={{ width: "60%" }} />
                      <div className="paper-bar accent" style={{ width: "40%" }} />
                    </div>
                    <div className="paper-row">
                      <div className="paper-bar accent" style={{ width: "50%" }} />
                      <div className="paper-bar" style={{ width: "50%" }} />
                    </div>
                  </div>
                </div>
                <div className="paper paper-3">
                  <div className="paper-header" />
                  <div className="paper-rows">
                    <div className="paper-row">
                      <div className="paper-bar accent" style={{ width: "55%" }} />
                      <div className="paper-bar" style={{ width: "45%" }} />
                    </div>
                    <div className="paper-row">
                      <div className="paper-bar" style={{ width: "70%" }} />
                    </div>
                    <div className="paper-row">
                      <div className="paper-bar" style={{ width: "40%" }} />
                      <div className="paper-bar accent" style={{ width: "60%" }} />
                    </div>
                  </div>
                </div>
              </div>

              <div className="glass-card glass-card-1 animate-float">
                <div className="glass-card-icon bg-blue-50">
                  <svg className="h-4 w-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div className="glass-card-label">已解析</div>
                <div className="glass-card-value">128</div>
                <div className="glass-card-sub">篇文献</div>
              </div>

              <div className="glass-card glass-card-2 animate-float" style={{ animationDelay: "2s" }}>
                <div className="glass-card-icon bg-green-50">
                  <svg className="h-4 w-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                </div>
                <div className="glass-card-label">准确率</div>
                <div className="glass-card-value">95%</div>
                <div className="glass-card-sub">变量提取</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Upload Section */}
      <section id="upload-section" className="bg-gray-50/50 py-20">
        <div className="mx-auto max-w-4xl px-6">
          <div className="rounded-2xl border border-gray-100 bg-white p-8 shadow-sm">
            <h2 className="mb-2 text-xl font-bold text-gray-900">上传文献</h2>
            <p className="mb-6 text-sm text-gray-500">
              支持批量上传 PDF 文件，每个文件不超过 10MB，页数不超过 30 页
            </p>

            <UploadZone onFilesAdded={handleFilesAdded} disabled={isProcessing} />

            {files.length > 0 && (
              <div className="mt-6">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">
                    已选择 {files.length} 个文件
                  </span>
                  {!isProcessing && (
                    <button onClick={handleReset} className="text-xs text-gray-400 hover:text-gray-600">
                      清空全部
                    </button>
                  )}
                </div>
                <FileGrid files={files} onRemove={handleRemove} />
              </div>
            )}

            <div className="mt-6">
              <ProgressBar {...progress} />

              {files.length > 0 && !isProcessing && !downloadUrl && (
                <button
                  onClick={handleProcess}
                  className="mt-4 w-full rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 hover:shadow-md disabled:opacity-50"
                  disabled={files.length === 0}
                >
                  开始分析 ({files.length} 个文件)
                </button>
              )}
            </div>
          </div>

          {downloadUrl && (
            <div ref={downloadSectionRef} className="mt-6 animate-fade-in rounded-2xl border border-green-100 bg-green-50 p-8 text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-green-100">
                <svg className="h-7 w-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-gray-900">解析完成</h3>
              <p className="mt-1 text-sm text-gray-600">所有文献已成功解析，可预览结果或下载 Excel 表格</p>
              <div className="mt-6 flex justify-center gap-3">
                {results.length > 0 && (
                  <button
                    onClick={() => setShowPreview((v) => !v)}
                    className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700"
                  >
                    {showPreview ? "收起预览" : "预览结果"}
                  </button>
                )}
                <button
                  onClick={handleDownload}
                  className="rounded-lg bg-green-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-green-700"
                >
                  下载 Excel
                </button>
                <button
                  onClick={handleReset}
                  className="rounded-lg border border-gray-200 px-6 py-3 text-sm font-semibold text-gray-700 transition-all hover:bg-gray-50"
                >
                  继续上传
                </button>
              </div>
            </div>
          )}

          {showPreview && results.length > 0 && (
            <div ref={previewSectionRef} className="mt-6 animate-fade-in">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-bold text-gray-900">解析结果预览</h3>
                <span className="text-xs text-gray-400">共 {results.length} 篇文献</span>
              </div>
              <ResultPreview results={results} />
            </div>
          )}
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mb-12 text-center">
            <h2 className="text-3xl font-bold text-gray-900">核心功能</h2>
            <p className="mt-3 text-gray-500">AI 驱动的文献解析，让研究效率提升 10 倍</p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />,
                title: "PDF 智能解析",
                desc: "自动识别文献结构，提取正文内容，跳过参考文献",
                bgClass: "bg-blue-50",
                textClass: "text-blue-600",
              },
              {
                icon: <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />,
                title: "AI 变量提取",
                desc: "DeepSeek 大模型精准提取研究问题、方法、指标等核心维度",
                bgClass: "bg-purple-50",
                textClass: "text-purple-600",
              },
              {
                icon: <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M12 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M21.375 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125M12 17.25v-5.25" />,
                title: "结构化输出",
                desc: "自动生成格式化的 Excel 矩阵表格，方便对比分析",
                bgClass: "bg-green-50",
                textClass: "text-green-600",
              },
              {
                icon: <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />,
                title: "批量处理",
                desc: "一次上传多篇文献，系统自动排队处理，效率翻倍",
                bgClass: "bg-orange-50",
                textClass: "text-orange-600",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="group rounded-xl border border-gray-100 bg-white p-6 shadow-sm transition-all hover:border-gray-200 hover:shadow-md"
              >
                <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-lg ${item.bgClass}`}>
                  <svg
                    className={`h-6 w-6 ${item.textClass}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    {item.icon}
                  </svg>
                </div>
                <h3 className="mb-2 font-bold text-gray-900">{item.title}</h3>
                <p className="text-sm leading-relaxed text-gray-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Result Preview */}
      <section className="bg-gray-50/50 py-20">
        <div className="mx-auto max-w-5xl px-6">
          <div className="mb-12 text-center">
            <h2 className="text-3xl font-bold text-gray-900">输出预览</h2>
            <p className="mt-3 text-gray-500">自动生成结构化文献矩阵表格</p>
          </div>

          <div className="result-table-wrap">
            <table className="result-table">
              <thead>
                <tr>
                  <th>文献名称</th>
                  <th>研究问题</th>
                  <th>研究方法</th>
                  <th>核心指标</th>
                  <th>创新点</th>
                  <th>局限性</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["Deep Learning for NLP", "文本分类精度不足", "Transformer + BERT", "F1 Score / Accuracy", "引入注意力机制", "计算资源消耗大"],
                  ["Climate Change Analysis", "全球变暖趋势预测", "时间序列分析", "温度偏差 / CO2浓度", "多源数据融合", "历史数据缺失"],
                  ["Healthcare AI Review", "医疗影像诊断效率", "CNN + 迁移学习", "灵敏度 / 特异度", "小样本学习能力", "跨设备泛化性差"],
                ].map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-12">
        <div className="mx-auto max-w-7xl px-6">
          <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
                <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                </svg>
              </div>
              <span className="font-bold text-gray-900">Literature Juicer</span>
            </div>
            <p className="text-sm text-gray-400">&copy; 2026 Literature Juicer. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
