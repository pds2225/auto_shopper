import { NextResponse } from "next/server";
import {
  sanitizeQuery,
  parseNaverResponse,
  demoItems,
  naverMobileUrl,
  clampSort,
  sortItems,
} from "@/lib/shop.mjs";
import { loadNaverEnv } from "@/lib/loadEnv";

export const dynamic = "force-dynamic";

function demoPayload(query: string, reason: string, sort: string) {
  const items = sortItems(demoItems(query), sort);
  return {
    ok: true,
    source: "demo",
    query,
    count: items.length,
    items,
    reason,
    naver_mobile_url: naverMobileUrl(query),
  };
}

export async function GET(request: Request) {
  loadNaverEnv();
  const { searchParams } = new URL(request.url);
  const { query, error } = sanitizeQuery(searchParams.get("q") || "");
  if (!query) {
    return NextResponse.json({ ok: false, reason: error, items: [] }, { status: 400 });
  }
  const sort = clampSort(searchParams.get("sort") || "sim");
  const display = Math.max(1, Math.min(Number(searchParams.get("display") || 20) || 20, 40));

  const id = (process.env.NAVER_CLIENT_ID || "").trim();
  const secret = (process.env.NAVER_CLIENT_SECRET || "").trim();
  if (!id || !secret) {
    return NextResponse.json(
      demoPayload(
        query,
        "네이버 API 키가 없어 데모 결과를 보여줍니다. 휴대폰에서는 아래 ‘네이버에서 보기’로 바로 검색할 수 있습니다.",
        sort,
      ),
    );
  }

  const url =
    "https://openapi.naver.com/v1/search/shop.json?" +
    new URLSearchParams({ query, display: String(display), sort }).toString();

  try {
    const res = await fetch(url, {
      headers: {
        "X-Naver-Client-Id": id,
        "X-Naver-Client-Secret": secret,
      },
      cache: "no-store",
    });
    if (!res.ok) {
      const body = await res.text();
      console.error("naver shop api failed", res.status, body.slice(0, 300));
      return NextResponse.json(
        demoPayload(query, `네이버 API가 ${res.status}로 실패해 데모로 대체했습니다.`, sort),
      );
    }
    const payload = await res.json();
    const items = sortItems(parsed.items, sort);
    return NextResponse.json({
      ...parsed,
      items,
      count: items.length,
      source: "naver",
      query,
      naver_mobile_url: naverMobileUrl(query),
    });
  } catch (err) {
    console.error("naver shop api error", err);
    return NextResponse.json(
      demoPayload(query, "네트워크 오류로 데모 결과를 보여줍니다.", sort),
    );
  }
}
