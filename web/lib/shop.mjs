const TAG_RE = /<[^>]+>/g;
const MAX_QUERY_LEN = 80;
const ALLOWED_SORT = new Set(["sim", "date", "asc", "dsc"]);

export function stripTags(text) {
  return String(text || "")
    .replace(TAG_RE, "")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .trim();
}

export function sanitizeQuery(raw) {
  const query = String(raw || "").trim().replace(/\s+/g, " ");
  if (!query) return { query: null, error: "검색어를 입력하세요" };
  if (query.length > MAX_QUERY_LEN) {
    return { query: null, error: "검색어가 너무 깁니다 (80자 이내)" };
  }
  return { query, error: null };
}

export function formatWon(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(n) || n < 0) return null;
  return `${Math.trunc(n).toLocaleString("ko-KR")}원`;
}

export function normalizeItem(raw) {
  if (!raw || typeof raw !== "object") return null;
  const title = stripTags(raw.title || raw.name || "");
  if (!title) return null;
  let price = null;
  if (raw.lprice !== null && raw.lprice !== undefined && raw.lprice !== "") {
    const n = Number(String(raw.lprice).replace(/,/g, ""));
    if (Number.isFinite(n)) price = Math.trunc(n);
  }
  return {
    title,
    price,
    price_text: formatWon(price) || "가격 미표시",
    mall: String(raw.mallName || raw.mall || "").trim() || "판매처 미표시",
    link: String(raw.link || raw.productUrl || "").trim(),
    image: String(raw.image || raw.imageUrl || "").trim(),
    brand: String(raw.brand || "").trim(),
    category: String(raw.category3 || raw.category2 || raw.category || "").trim(),
    product_id: String(raw.productId || raw.product_id || "").trim(),
  };
}

export function parseNaverResponse(payload) {
  if (!payload || typeof payload !== "object") {
    return { ok: false, reason: "응답 형식이 올바르지 않습니다", items: [] };
  }
  const items = [];
  for (const raw of payload.items || []) {
    const item = normalizeItem(raw);
    if (item) items.push(item);
  }
  return { ok: true, count: items.length, items };
}

export function demoItems(query) {
  const q = String(query || "상품").trim() || "상품";
  const link = `https://search.shopping.naver.com/search/all?query=${encodeURIComponent(q)}`;
  const samples = [
    { title: `${q} 인기 모델 (데모)`, lprice: "129000", mallName: "데모스토어", brand: "데모", link, image: "", productId: "demo-1", category3: "데모" },
    { title: `${q} 가성비형 (데모)`, lprice: "89000", mallName: "데모마켓", brand: "데모", link, image: "", productId: "demo-2", category3: "데모" },
    { title: `${q} 프리미엄 (데모)`, lprice: "219000", mallName: "데모몰", brand: "데모", link, image: "", productId: "demo-3", category3: "데모" },
  ];
  return samples.map(normalizeItem).filter(Boolean);
}

export function naverMobileUrl(query) {
  return `https://msearch.shopping.naver.com/search/all?query=${encodeURIComponent(query)}`;
}

export function clampSort(sort) {
  return ALLOWED_SORT.has(sort) ? sort : "sim";
}

export { MAX_QUERY_LEN };
