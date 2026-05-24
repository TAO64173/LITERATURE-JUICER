import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function proxyRequest(req: NextRequest, path: string[]) {
  const targetPath = path.join("/");
  console.log(`[proxy] ${req.method} /${targetPath} — start`);

  let token: string | null = null;
  try {
    // Wrap auth() in a timeout to prevent hanging
    const authResult = await Promise.race([
      auth(),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("auth() timeout after 15s")), 15_000)
      ),
    ]);
    token = await authResult.getToken();
    console.log(`[proxy] Token obtained: ${token ? token.substring(0, 20) + "..." : "null"}`);
  } catch (err) {
    console.error("[proxy] auth() failed:", err);
    return NextResponse.json(
      { success: false, message: "认证失败，请重新登录" },
      { status: 401 }
    );
  }

  if (!token) {
    console.warn("[proxy] No token returned from auth()");
    return NextResponse.json(
      { success: false, message: "未登录，请先登录" },
      { status: 401 }
    );
  }

  const targetUrl = new URL(`/${targetPath}`, API_BASE);
  req.nextUrl.searchParams.forEach((value, key) => {
    targetUrl.searchParams.set(key, value);
  });

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${token}`);

  const contentType = req.headers.get("content-type");
  const isFormData = contentType?.includes("multipart/form-data");
  console.log(`[proxy] Content-Type: ${contentType}, isFormData: ${isFormData}`);

  let body: BodyInit | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    try {
      if (isFormData) {
        body = await req.formData();
        console.log("[proxy] FormData body read OK");
      } else {
        body = await req.text();
        if (contentType) {
          headers.set("Content-Type", contentType);
        } else {
          headers.set("Content-Type", "application/json");
        }
      }
    } catch (err) {
      console.error("[proxy] Body read failed:", err);
      return NextResponse.json(
        { success: false, message: "读取请求体失败" },
        { status: 400 }
      );
    }
  }

  console.log(`[proxy] Forwarding to ${targetUrl.toString()}`);
  let backendRes: Response;
  try {
    backendRes = await fetch(targetUrl.toString(), {
      method: req.method,
      headers,
      body,
    });
    console.log(`[proxy] Backend responded: status=${backendRes.status}`);
  } catch (err) {
    console.error("[proxy] Backend fetch failed:", err);
    return NextResponse.json(
      { success: false, message: "无法连接后端服务" },
      { status: 502 }
    );
  }

  const responseContentType = backendRes.headers.get("content-type") || "";

  // Buffer all responses (JSON, Excel, files)
  const buffer = await backendRes.arrayBuffer();
  const resHeaders: Record<string, string> = {
    "Content-Type": responseContentType || "application/octet-stream",
  };
  const contentDisposition = backendRes.headers.get("content-disposition");
  if (contentDisposition) resHeaders["Content-Disposition"] = contentDisposition;
  return new Response(buffer, {
    status: backendRes.status,
    headers: resHeaders,
  });
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(req, path);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(req, path);
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(req, path);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(req, path);
}
