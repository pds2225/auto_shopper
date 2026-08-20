export function stripTags(text: string): string;
export function sanitizeQuery(raw: string): { query: string | null; error: string | null };
export function formatWon(value: unknown): string | null;
export function normalizeItem(raw: unknown): {
  title: string;
  price: number | null;
  price_text: string;
  mall: string;
  link: string;
  image: string;
  brand: string;
  category: string;
  product_id: string;
} | null;
export function parseNaverResponse(payload: unknown): {
  ok: boolean;
  reason?: string;
  count?: number;
  items: Array<NonNullable<ReturnType<typeof normalizeItem>>>;
};
export function demoItems(query: string): Array<NonNullable<ReturnType<typeof normalizeItem>>>;
export function naverMobileUrl(query: string): string;
export function clampSort(sort: string): string;
export const MAX_QUERY_LEN: number;
