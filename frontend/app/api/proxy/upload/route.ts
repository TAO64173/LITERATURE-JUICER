import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function proxyUpload(req: NextRequest) {
  let token: string | null = null;
  try {
    const authResult = await Promise.race([
      auth(),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("auth() timeout after 15s")), 15_000)
      ),
    ]);
    token = await authResult.getToken();
  } catch (err) {
    console.error("[upload-proxy] auth() failed:", err);
    return NextResponse.json(
      { success: false, message: "认证失败，请重新登录" },
      { status: 401 }
    );
  }

  if (!token) {
    return NextResponse.json(
      { success: false, message: "未登录，请先登录" },
      { status: 401 }
    );
  }

  const targetUrl = new URL("/upload", API_BASE);

  let body: FormData;
  try {
    body = await req.formData();
  } catch (err) {
    console.error("[upload-proxy] Failed to read FormData:", err);
    return NextResponse.json(
      { success: false, message: "读取上传文件失败" },
      { status: 400 }
    );
  }

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${token}`);

  const url = targetUrl.toString();

  let backendRes: Response;
  try {
    backendRes = await fetch(url, {
      method: "POST",
      headers,
      body,
      duplex: "half",
    } as RequestInit);
  } catch (err: unknown) {
    const msg = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
    console.error(`[upload-proxy] Fetch failed for ${url}: ${msg}`);
    return NextResponse.json(
      { success: false, message: `无法连接后端服务: ${msg}` },
      { status: 502 }
    );
  }

  try {
    const buffer = await backendRes.arrayBuffer();
    return new Response(buffer, {
      status: backendRes.status,
      headers: {
        "Content-Type": backendRes.headers.get("content-type") || "application/json",
      },
    });
  } catch (err) {
    console.error("[upload-proxy] Response buffering failed:", err);
    return NextResponse.json(
      { success: false, message: "读取后端响应失败" },
      { status: 502 }
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    return await proxyUpload(req);
  } catch (err) {
    console.error("[upload-proxy] Uncaught error:", err);
    return new Response(
      JSON.stringify({ success: false, message: String(err) }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}
