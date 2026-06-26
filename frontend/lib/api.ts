/**
 * backend (FastAPI) を叩くための薄い API クライアント雛形。
 *
 * ベース URL は環境変数 `NEXT_PUBLIC_API_BASE_URL` から読む。
 * 未設定時はローカル開発の既定値 `http://localhost:8000` を用いる。
 *
 * 実際のエンドポイント別メソッド（jobs / candidates / rankings 等）は
 * 後続 issue で本ファイルまたは lib 配下に追加していく。ここでは最小の
 * 汎用ラッパ（apiFetch）のみを提供する。
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * backend へ JSON リクエストを送る汎用ヘルパー。
 *
 * @param path  先頭スラッシュ付きのパス（例: "/jobs"）
 * @param init  fetch のオプション
 * @returns     パース済みのレスポンスボディ
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    throw new ApiError(
      res.status,
      `API request failed: ${res.status} ${res.statusText}`,
    );
  }

  // 204 No Content など本文が無い場合に備える。
  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}
