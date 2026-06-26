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

/**
 * FastAPI の HTTPException が返すエラー詳細。
 *
 * 構造化失敗系（parse）では `{ code, message, attempts? }` のオブジェクト、
 * それ以外（例: 404）では文字列が `detail` に入りうる。両方を表現する。
 */
export interface ApiErrorDetail {
  code?: string;
  message?: string;
  attempts?: number;
}

export class ApiError extends Error {
  /**
   * パース済みのエラー詳細（FastAPI の `detail`）。
   * オブジェクト形式なら `ApiErrorDetail`、文字列形式ならその文字列、無ければ undefined。
   */
  public readonly detail?: ApiErrorDetail | string;

  /** detail がオブジェクト形式のときの `code`（出し分け用ショートカット）。 */
  public readonly code?: string;

  constructor(
    public readonly status: number,
    message: string,
    detail?: ApiErrorDetail | string,
  ) {
    super(message);
    this.name = "ApiError";
    this.detail = detail;
    this.code = detail && typeof detail === "object" ? detail.code : undefined;
  }
}

/**
 * エラーレスポンスのボディから FastAPI の `detail` を安全に取り出す。
 *
 * - JSON でない／本文が空のときは undefined。
 * - `detail` がオブジェクトなら `{ code, message, attempts }` に正規化。
 * - `detail` が文字列ならそのまま返す。
 */
async function parseErrorDetail(
  res: Response,
): Promise<ApiErrorDetail | string | undefined> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return undefined;
  }

  if (body == null || typeof body !== "object") {
    return undefined;
  }

  const detail = (body as { detail?: unknown }).detail;
  if (detail == null) {
    return undefined;
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    return {
      code: typeof d.code === "string" ? d.code : undefined,
      message: typeof d.message === "string" ? d.message : undefined,
      attempts: typeof d.attempts === "number" ? d.attempts : undefined,
    };
  }
  return undefined;
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
    const detail = await parseErrorDetail(res);
    const detailMessage =
      detail && typeof detail === "object"
        ? detail.message
        : typeof detail === "string"
          ? detail
          : undefined;
    throw new ApiError(
      res.status,
      detailMessage ?? `API request failed: ${res.status} ${res.statusText}`,
      detail,
    );
  }

  // 204 No Content など本文が無い場合に備える。
  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}
