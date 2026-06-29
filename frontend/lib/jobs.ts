/**
 * jobs API クライアントと共有型。
 *
 * backend の `schemas.py`（`JobParseResult` / `JobCreate` / `JobOut` / `JobSummary`・enum）
 * と契約を一致させる。enum は StrEnum で値がそのまま日本語の表示ラベルになる。
 */

import { apiFetch } from "@/lib/api";

/** 雇用形態。値がそのまま表示ラベル。null は未選択（言及なし）。 */
export type EmploymentType =
  | "正社員"
  | "契約社員"
  | "業務委託"
  | "派遣"
  | "その他";

/** リモート可否。 */
export type RemoteWork = "フルリモート" | "一部リモート" | "出社" | "不明";

/** ポジションレベル。 */
export type PositionLevel =
  | "ジュニア"
  | "ミドル"
  | "シニア"
  | "リード"
  | "マネージャー";

export const EMPLOYMENT_TYPES: readonly EmploymentType[] = [
  "正社員",
  "契約社員",
  "業務委託",
  "派遣",
  "その他",
];

export const REMOTE_WORKS: readonly RemoteWork[] = [
  "フルリモート",
  "一部リモート",
  "出社",
  "不明",
];

export const POSITION_LEVELS: readonly PositionLevel[] = [
  "ジュニア",
  "ミドル",
  "シニア",
  "リード",
  "マネージャー",
];

/** 求人票の構造化結果（LLM 出力）。配列は空配列デフォルト、それ以外は null 許容。 */
export interface JobParseResult {
  title: string | null;
  description: string | null;
  required_skills: string[];
  preferred_skills: string[];
  ideal_profile: string | null;
  employment_type: EmploymentType | null;
  location: string | null;
  remote_work: RemoteWork | null;
  rate_min: number | null;
  rate_max: number | null;
  min_experience_years: number | null;
  position_level: PositionLevel | null;
  industry_experience: string | null;
  certifications: string[];
}

/** `POST /jobs/parse` のレスポンス（構造化結果 + 原文）。 */
export type JobParseResponse = JobParseResult & { raw_text: string };

/** `POST /jobs` のリクエスト（構造化結果 + 原文）。 */
export type JobCreate = JobParseResult & { raw_text: string; matching_instructions: string | null };

/** `POST /jobs` のレスポンス（保存済み求人）。 */
export type JobOut = JobCreate & { id: number; created_at: string };

/** `GET /jobs` の各要素（一覧用の軽量スキーマ）。 */
export interface JobListItem {
  id: number;
  title: string | null;
  created_at: string;
}

/** 生テキストを LLM 構造化する（`POST /jobs/parse`）。 */
export function parseJob(rawText: string): Promise<JobParseResponse> {
  return apiFetch<JobParseResponse>("/jobs/parse", {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText }),
  });
}

/** 構造化結果を保存する（`POST /jobs`）。 */
export function createJob(input: JobCreate): Promise<JobOut> {
  return apiFetch<JobOut>("/jobs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** 保存済み求人一覧を取得する（`GET /jobs`）。 */
export function listJobs(): Promise<JobListItem[]> {
  return apiFetch<JobListItem[]>("/jobs");
}

/** 求人を削除する（`DELETE /jobs/{id}`）。 */
export async function deleteJob(id: number): Promise<void> {
  await apiFetch<void>(`/jobs/${id}`, { method: "DELETE" });
}

/** 求人を1件取得する（`GET /jobs/{id}`）。 */
export function getJob(id: number): Promise<JobOut> {
  return apiFetch<JobOut>(`/jobs/${id}`);
}
