"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { sortItems } from "@/lib/shop.mjs";

type ShopItem = {
  title: string;
  price: number | null;
  price_text: string;
  mall: string;
  link: string;
  image: string;
  brand: string;
  category: string;
  product_id?: string;
};

type SearchResponse = {
  ok: boolean;
  source?: "naver" | "demo" | "error";
  query?: string;
  count?: number;
  items?: ShopItem[];
  reason?: string;
  naver_mobile_url?: string;
};

const SORTS = [
  { id: "sim", label: "관련순" },
  { id: "asc", label: "낮은 가격" },
  { id: "dsc", label: "높은 가격" },
] as const;

export default function SearchApp() {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<(typeof SORTS)[number]["id"]>("sim");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");

  const canSearch = q.trim().length > 0 && !loading;

  async function runSearch(query: string, nextSort: string) {
    const trimmed = query.trim();
    if (!trimmed) {
      setError("검색어를 입력하세요");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await fetch(
        `/api/search?q=${encodeURIComponent(trimmed)}&sort=${encodeURIComponent(nextSort)}`,
        { cache: "no-store" },
      );
      const json = (await res.json()) as SearchResponse;
      if (!res.ok && !json.items?.length) {
        setError(json.reason || "검색에 실패했습니다");
        setData(null);
        return;
      }
      setData(json);
    } catch {
      setError("네트워크 오류입니다. 연결을 확인하세요");
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void runSearch(q, sort);
  }

  const items = useMemo(
    () => sortItems(data?.items || [], sort),
    [data, sort],
  );
  const isDemo = data?.source === "demo";
  const naverUrl = useMemo(() => {
    if (data?.naver_mobile_url) return data.naver_mobile_url;
    const trimmed = q.trim();
    if (!trimmed) return "";
    return `https://msearch.shopping.naver.com/search/all?query=${encodeURIComponent(trimmed)}`;
  }, [data, q]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initial = params.get("q");
    if (initial) {
      setQ(initial);
      void runSearch(initial, sort);
    }
    // first paint only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">auto_shopper</p>
        <h1>어디서나 장보기</h1>
        <p className="lede">
          휴대폰·PC 브라우저에서 바로 검색하세요. 한글 폰트가 아이폰·안드로이드·윈도우 모두에서
          깨지지 않습니다. 결제는 직접 합니다.
        </p>
      </header>

      <form className="search" onSubmit={onSubmit}>
        <label className="sr-only" htmlFor="q">
          상품 검색
        </label>
        <input
          id="q"
          name="q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="예: 웹개발 폰트, 저소음 키보드"
          autoComplete="off"
          enterKeyHint="search"
          maxLength={80}
        />
        <button type="submit" disabled={!canSearch}>
          {loading ? "찾는 중" : "검색"}
        </button>
      </form>

      <div className="sorts" role="tablist" aria-label="정렬">
        {SORTS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={sort === item.id ? "chip on" : "chip"}
            onClick={() => {
              setSort(item.id);
              if (q.trim()) void runSearch(q, item.id);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {error ? <p className="banner err">{error}</p> : null}
      {isDemo ? (
        <p className="banner warn">
          {data?.reason}{" "}
          {naverUrl ? (
            <a href={naverUrl} target="_blank" rel="noreferrer">
              네이버 쇼핑(휴대폰)에서 보기
            </a>
          ) : null}
        </p>
      ) : null}

      {data && !items.length && !loading ? (
        <p className="empty">결과가 없습니다. 다른 검색어를 시도하세요.</p>
      ) : null}

      <ul className="cards">
        {items.map((item, index) => (
          <li key={`${item.product_id || item.link}-${index}`}>
            <a className="card" href={item.link || naverUrl} target="_blank" rel="noreferrer">
              <div className="thumb" aria-hidden="true">
                {item.image ? (
                  // product images are remote; native img avoids next/image domain config surprises
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={item.image} alt="" />
                ) : (
                  <span>상품</span>
                )}
              </div>
              <div className="meta">
                <strong>{item.title}</strong>
                <em>{item.price_text}</em>
                <span>
                  {item.mall}
                  {item.brand ? ` · ${item.brand}` : ""}
                </span>
              </div>
            </a>
          </li>
        ))}
      </ul>

      {data?.ok && naverUrl ? (
        <p className="foot-link">
          <a href={naverUrl} target="_blank" rel="noreferrer">
            네이버 쇼핑 앱/휴대폰 페이지로 열기
          </a>
        </p>
      ) : null}

      <footer className="foot">
        결제·비밀번호 입력은 하지 않습니다. 마음에 드는 상품만 눌러 직접 구매하세요.
        홈 화면에 추가하면 앱처럼 열립니다.
      </footer>
    </main>
  );
}
