"use client";

interface ProgressBarProps {
  percent: number;
  message: string;
  visible: boolean;
}

export function ProgressBar({ percent, message, visible }: ProgressBarProps) {
  if (!visible) return null;

  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-600">{message}</p>
      <div className="h-1.5 overflow-hidden rounded-full bg-gray-100">
        <div
          className="h-full rounded-full bg-blue-600 transition-all duration-500 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
