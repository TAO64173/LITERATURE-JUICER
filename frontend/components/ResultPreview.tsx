"use client";

import type { UploadResult } from "@/lib/api";

interface ResultPreviewProps {
  results: UploadResult[];
}

const FIELD_LABELS: Record<string, string> = {
  title: "文献标题",
  author: "作者",
  year: "年份",
  journal: "期刊",
  doi: "DOI",
  keywords: "关键词",
  abstract: "摘要",
  question: "研究问题",
  background: "研究背景",
  gap: "研究空白",
  objective: "研究目标",
  method: "研究方法",
  dataset: "数据集",
  metrics: "核心指标",
  comparison: "对比方法",
  innovation: "创新点",
  findings: "研究发现",
  conclusion: "结论",
  limitation: "局限性",
  future_work: "未来工作",
  inspiration: "启发",
};

const METADATA_KEYS = ["title", "author", "year", "journal", "doi", "keywords", "abstract"];
const CORE_KEYS = ["question", "method", "metrics", "innovation", "limitation"];
const EXTRA_KEYS = [
  "background", "gap", "objective", "dataset",
  "comparison", "findings", "conclusion", "future_work", "inspiration",
];

function isEmpty(value: string | undefined): boolean {
  return !value || value.trim() === "" || value === "未提供" || value === "未提及";
}

const LONG_FIELDS = new Set(["abstract", "findings", "conclusion", "background"]);

function FieldRow({ label, value, fieldKey }: { label: string; value: string; fieldKey?: string }) {
  if (isEmpty(value)) return null;
  const isLong = fieldKey ? LONG_FIELDS.has(fieldKey) : false;
  return (
    <div className="group">
      <dt className="text-xs font-semibold uppercase tracking-wider text-gray-400">
        {label}
      </dt>
      <dd className={`mt-1 text-sm leading-relaxed text-gray-700 ${isLong ? "line-clamp-4" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function ResultCard({ result, index }: { result: UploadResult; index: number }) {
  const title = result.title || `文献 ${index + 1}`;
  const metadata = METADATA_KEYS.filter((k) => !isEmpty(result[k]));
  const core = CORE_KEYS.filter((k) => !isEmpty(result[k]));
  const extras = EXTRA_KEYS.filter((k) => !isEmpty(result[k]));

  return (
    <div className="rounded-xl border border-gray-100 bg-white shadow-sm transition-all hover:shadow-md">
      {/* Header */}
      <div className="border-b border-gray-50 px-6 py-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-base font-bold text-gray-900 leading-snug">
            {title}
          </h3>
          <span className="shrink-0 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-600">
            #{index + 1}
          </span>
        </div>
        {!isEmpty(result.author) && (
          <p className="mt-1 text-xs text-gray-400">
            {result.author}
            {!isEmpty(result.year) ? ` · ${result.year}` : ""}
            {!isEmpty(result.journal) ? ` · ${result.journal}` : ""}
          </p>
        )}
      </div>

      {/* Core analysis fields */}
      <div className="px-6 py-4">
        <dl className="grid gap-4 sm:grid-cols-2">
          {core.map((key) => (
            <FieldRow key={key} label={FIELD_LABELS[key] || key} value={result[key]} fieldKey={key} />
          ))}
        </dl>
      </div>

      {/* Extra fields (collapsible) */}
      {extras.length > 0 && (
        <details className="border-t border-gray-50 px-6 py-3">
          <summary className="cursor-pointer text-xs font-medium text-gray-400 hover:text-gray-600 select-none">
            更多字段 ({extras.length})
          </summary>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2">
            {extras.map((key) => (
              <FieldRow key={key} label={FIELD_LABELS[key] || key} value={result[key]} fieldKey={key} />
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}

export function ResultPreview({ results }: ResultPreviewProps) {
  if (!results || results.length === 0) return null;

  return (
    <div className="space-y-4">
      {results.map((result, i) => (
        <ResultCard key={i} result={result} index={i} />
      ))}
    </div>
  );
}
