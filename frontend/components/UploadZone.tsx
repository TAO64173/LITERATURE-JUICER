"use client";

import { useRef, useCallback } from "react";

interface UploadZoneProps {
  onFilesAdded: (files: File[]) => void;
  disabled?: boolean;
}

export function UploadZone({ onFilesAdded, disabled }: UploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleClick = useCallback(() => {
    if (!disabled) fileInputRef.current?.click();
  }, [disabled]);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        onFilesAdded(Array.from(e.target.files));
        e.target.value = "";
      }
    },
    [onFilesAdded]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (disabled) return;
      if (e.dataTransfer.files.length > 0) {
        onFilesAdded(Array.from(e.dataTransfer.files));
      }
    },
    [disabled, onFilesAdded]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) {
        e.currentTarget.classList.add("border-blue-400", "bg-blue-50/50");
      }
    },
    [disabled]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.currentTarget.classList.remove("border-blue-400", "bg-blue-50/50");
  }, []);

  return (
    <div
      onClick={handleClick}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`flex flex-1 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 px-8 py-16 text-center transition-colors ${
        disabled
          ? "cursor-not-allowed opacity-50"
          : "hover:border-blue-300 hover:bg-blue-50/30"
      }`}
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-blue-50">
        <svg
          className="h-7 w-7 text-blue-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
      </div>
      <p className="mb-1.5 text-[15px] font-semibold text-gray-800">
        点击或拖拽 PDF 文件到此处上传
      </p>
      <p className="text-sm text-gray-400">
        支持批量上传 · 单个文件 &lt;10MB · 页数 &lt;30 页
      </p>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        multiple
        className="hidden"
        onChange={handleFileChange}
      />
    </div>
  );
}
