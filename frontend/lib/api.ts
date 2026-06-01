const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface QuotaInfo {
  success: boolean;
  total: number;
  used: number;
  remaining: number;
  role: "admin" | "user";
}

export interface InviteInfo {
  success: boolean;
  invite_code: string;
  invited_count: number;
}

export interface HistoryRecord {
  id: string;
  filename: string;
  status: "processing" | "completed" | "failed";
  result_url: string | null;
  created_at: string;
}

export interface UploadResult {
  question: string;
  method: string;
  metrics: string;
  innovation: string;
  limitation: string;
  [key: string]: string;
}

export interface UploadResponse {
  success: boolean;
  download_url: string;
  results: UploadResult[];
  errors: string[];
  warnings: string[];
  remaining_quota?: number;
}

export async function fetchQuota(): Promise<QuotaInfo> {
  const res = await fetch("/api/quota", { method: "GET" });
  if (!res.ok) {
    throw new Error("获取额度失败");
  }
  const data = await res.json();
  if (!data.success) {
    throw new Error(data.message || "获取额度失败");
  }
  return data;
}

export async function fetchHistory(): Promise<HistoryRecord[]> {
  const res = await fetch("/api/proxy/history", { method: "GET" });
  if (!res.ok) {
    throw new Error("获取历史记录失败");
  }
  const data = await res.json();
  return data.history || [];
}

export async function uploadFiles(files: File[]): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file);
  });

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300_000);

  try {
    const res = await fetch("/api/proxy/upload", {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const text = await res.text();
      let msg = "上传失败";
      try {
        const err = JSON.parse(text);
        msg = err.detail || err.message || msg;
      } catch {}
      throw new Error(msg);
    }

    const data: UploadResponse = await res.json();

    if (!data.success) {
      const msg = data.errors?.join("\n") || "处理失败";
      throw new Error(msg);
    }

    return data;
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("上传超时（5分钟），请减少文件数量后重试");
    }
    throw err;
  }
}

export async function fetchInviteInfo(): Promise<InviteInfo> {
  const res = await fetch("/api/proxy/invite/info", { method: "GET" });
  if (!res.ok) {
    throw new Error("获取邀请信息失败");
  }
  return res.json();
}

export async function applyInviteCode(code: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch("/api/proxy/invite/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    throw new Error("邀请码使用失败");
  }
  return res.json();
}


