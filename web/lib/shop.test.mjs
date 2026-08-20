import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  stripTags,
  sanitizeQuery,
  formatWon,
  parseNaverResponse,
  demoItems,
  sortItems,
} from "./shop.mjs";

describe("sanitizeQuery", () => {
  it("rejects empty", () => {
    const { query, error } = sanitizeQuery("   ");
    assert.equal(query, null);
    assert.match(error, /검색어/);
  });
  it("rejects too long", () => {
    const { query, error } = sanitizeQuery("가".repeat(81));
    assert.equal(query, null);
    assert.match(error, /80/);
  });
  it("collapses spaces", () => {
    const { query, error } = sanitizeQuery("  웹개발   폰트  ");
    assert.equal(error, null);
    assert.equal(query, "웹개발 폰트");
  });
});

describe("stripTags", () => {
  it("removes naver highlight tags", () => {
    assert.equal(stripTags("<b>무선청소기</b> G10"), "무선청소기 G10");
    assert.equal(stripTags("A &amp; B"), "A & B");
  });
});

describe("formatWon", () => {
  it("formats thousands", () => {
    assert.equal(formatWon(129000), "129,000원");
    assert.equal(formatWon("89000"), "89,000원");
    assert.equal(formatWon(null), null);
  });
});

describe("parseNaverResponse", () => {
  it("normalizes fixture-like payload", () => {
    const parsed = parseNaverResponse({
      items: [
        {
          title: "<b>웹폰트</b> 패키지",
          lprice: "39000",
          mallName: "폰트몰",
          link: "https://search.shopping.naver.com/catalog/1",
          image: "https://example.com/a.jpg",
          productId: "1",
          brand: "Pretendard",
          category3: "폰트",
        },
      ],
    });
    assert.equal(parsed.ok, true);
    assert.equal(parsed.items[0].title, "웹폰트 패키지");
    assert.equal(parsed.items[0].price_text, "39,000원");
  });
});

describe("demoItems", () => {
  it("keeps the query in titles", () => {
    const items = demoItems("웹개발 폰트");
    assert.equal(items.length, 3);
    for (const item of items) {
      assert.match(item.title, /웹개발 폰트/);
      assert.ok(item.link.startsWith("https://"));
    }
  });
});

describe("sortItems", () => {
  it("orders by price ascending", () => {
    const items = demoItems("웹개발 폰트");
    const sorted = sortItems(items, "asc");
    assert.deepEqual(
      sorted.map((item) => item.price),
      [89000, 129000, 219000],
    );
  });
});
