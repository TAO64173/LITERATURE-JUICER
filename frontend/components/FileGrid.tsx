"use client";

export interface FileItem {
  name: string;
  size: number;
  file: File;
  status: "ready" | "processing" | "done" | "error";
  errorMsg?: string;
}

interface FileGridProps {
  files: FileItem[];
  onRemove: (index: number) => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

const STATUS_STYLES: Record<string, string> = {
  ready: "bg-gray-100 text-gray-600",
  processing: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  error: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<string, string> = {
  ready: "待上传",
  processing: "解析中",
  done: "已完成",
  error: "失败",
};

const PDF_ICON = (
  <svg
    className="h-8 w-8 text-red-400"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
    />
  </svg>
);

export function FileGrid({ files, onRemove }: FileGridProps) {
  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-300">
        <svg
          className="mb-2 h-8 w-8"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
          />
        </svg>
        <p className="text-sm">暂无文件</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 overflow-y-auto" style={{ maxHeight: 420 }}>
      {files.map((item, index) => (
        <div
          key={`${item.name}-${index}`}
          className="group relative flex flex-col items-center rounded-lg border border-gray-100 bg-white p-3 shadow-sm transition-shadow hover:shadow-md"
        >
          {/* Delete button */}
          {item.status !== "processing" && (
            <button
              onClick={() => onRemove(index)}
              className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full text-gray-300 opacity-0 transition-all hover:bg-red-50 hover:text-red-400 group-hover:opacity-100"
              aria-label="删除"
            >
              &times;
            </button>
          )}

          {/* Icon */}
          <div className="mb-2">{PDF_ICON}</div>

          {/* Name */}
          <div
            className="w-full truncate text-center text-xs font-medium text-gray-700"
            title={item.name}
          >
            {item.name}
          </div>

          {/* Size */}
          <div className="mt-0.5 text-[10px] text-gray-400">
            {formatSize(item.size)}
          </div>

          {/* Status badge */}
          <span
            className={`mt-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_STYLES[item.status]}`}
          >
            {STATUS_LABELS[item.status]}
          </span>
        </div>
      ))}
    </div>
  );
}
