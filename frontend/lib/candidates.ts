/**
 * candidates API クライアントと共有型。
 *
 * backend の `schemas.py`（`CandidateParseResult` / `CandidateCreate` / `CandidateOut`）
 * と契約を一致させる。
 */

import { apiFetch } from "@/lib/api";

/** 応募書類の構造化結果（LLM 出力）。配列は空配列デフォルト、それ以外は null 許容。 */
export interface CandidateParseResult {
  name: string | null;
  age: number | null;
  nearest_station: string | null;
  desired_rate: number | null;
  experience_years: number | null;
  skills: string[];
  certifications: string[];
  work_history: string | null;
  education: string | null;
  self_pr: string | null;
}

/** `POST /candidates/parse` のレスポンス（構造化結果 + 原文）。 */
export type CandidateParseResponse = CandidateParseResult & {
  raw_text: string;
};

/** `POST /candidates` のリクエスト（構造化結果 + 紐づく求人 + 原文）。 */
export type CandidateCreate = CandidateParseResult & {
  job_id: number;
  raw_text: string;
};

/** `POST /candidates` のレスポンス（保存済み候補者）。 */
export type CandidateOut = CandidateCreate & { id: number; created_at: string };

/** 生テキストを LLM 構造化する（`POST /candidates/parse`）。 */
export function parseCandidate(
  rawText: string,
): Promise<CandidateParseResponse> {
  return apiFetch<CandidateParseResponse>("/candidates/parse", {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText }),
  });
}

/** 構造化結果を保存する（`POST /candidates`）。 */
export function createCandidate(data: CandidateCreate): Promise<CandidateOut> {
  return apiFetch<CandidateOut>("/candidates", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
