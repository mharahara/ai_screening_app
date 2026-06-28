/**
 * rankings / candidate-detail API クライアントと共有型。
 *
 * backend の `schemas.py`（`RequirementCheck` / `ScoreOut` / `CandidateRankingItem` /
 * `CandidateDetailOut`）と契約を一致させる。
 */

import { apiFetch } from "@/lib/api";

/** 必須要件1件の充足判定（スコアの一部）。値はそのまま表示ラベル。 */
export interface RequirementCheck {
  requirement: string;
  status: "充足" | "未充足";
  evidence: string | null;
}

/** マッチングスコア（Score モデル）の全フィールド。 */
export interface ScoreOut {
  id: number;
  candidate_id: number;
  total_score: number;
  skill_score: number;
  experience_score: number;
  industry_score: number;
  position_score: number;
  required_met: number;
  required_total: number;
  requirement_checks: RequirementCheck[];
  strengths: string;
  concerns: string;
  interview_points: string;
  scored_at: string;
}

/**
 * ランキング一覧の1行（候補者 + スコアサマリー）。
 * スコア未算出の候補者はスコア系フィールドが null。
 */
export interface CandidateRankingItem {
  candidate_id: number;
  name: string | null;
  created_at: string;
  total_score: number | null;
  skill_score: number | null;
  experience_score: number | null;
  industry_score: number | null;
  position_score: number | null;
  required_met: number | null;
  required_total: number | null;
}

/** 候補者詳細（CandidateOut の全フィールド + スコア）。 */
export interface CandidateDetailOut {
  id: number;
  job_id: number;
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
  raw_text: string;
  created_at: string;
  score: ScoreOut | null;
}

/** 求人ごとの候補者ランキングを取得する（`GET /jobs/{jobId}/rankings`）。 */
export function listRankings(jobId: number): Promise<CandidateRankingItem[]> {
  return apiFetch<CandidateRankingItem[]>(`/jobs/${jobId}/rankings`);
}

/** 候補者詳細を取得する（`GET /candidates/{candidateId}/detail`）。 */
export function getCandidateDetail(
  candidateId: number,
): Promise<CandidateDetailOut> {
  return apiFetch<CandidateDetailOut>(`/candidates/${candidateId}/detail`);
}
