import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET() {
  console.log("[/api/quota] GET — start");
  let token: string | null = null;
  try {
    const authResult = await Promise.race([
      auth(),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("auth() timeout after 15s")), 15_000)
      ),
    ]);
    token = await authResult.getToken();
    console.log(`[/api/quota] Token: ${token ? token.substring(0, 20) + "..." : "null"}`);
  } catch (err) {
    console.error("[/api/quota] auth() failed:", err);
    return NextResponse.json(
      { success: false, message: "认证失败", total: 3, used: 0, remaining: 3 },
      { status: 200 }
    );
  }

  if (!token) {
    console.warn("[/api/quota] No token");
    return NextResponse.json(
      { success: false, message: "未登录", total: 3, used: 0, remaining: 3 },
      { status: 200 }
    );
  }

  try {
    const url = `${API_BASE}/quota`;
    console.log(`[/api/quota] Fetching ${url}`);
    const res = await fetch(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });

    console.log(`[/api/quota] Backend status: ${res.status}`);
    const data = await res.text();
    console.log(`[/api/quota] Response: ${data.substring(0, 200)}`);
    return new Response(data, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("[/api/quota] Fetch failed:", err);
    return NextResponse.json(
      { success: false, message: "无法连接后端服务", total: 3, used: 0, remaining: 3 },
      { status: 200 }
    );
  }
}
