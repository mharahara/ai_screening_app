import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
  getCandidateDetail,
  listRankings,
  type CandidateDetailOut,
  type CandidateRankingItem,
} from "@/lib/rankings";
import { ApiError, API_BASE_URL } from "@/lib/api";
import { server } from "./server";

/**
 * `lib/rankings.ts` の API クライアント契約テスト。
 *
 * backend は MSW でネットワーク層モックし、各関数が
 * - 正しいメソッド・パスを叩くこと
 * - レスポンス（型）をそのまま返すこと
 * - スコア算出済み／未算出（null）の両フィクスチャを正しく扱うこと
 * - 404 で ApiError.status が立つこと
 * を検証する。LLM 応答の質はテスト対象外で、契約（通り道・型整合）のみ見る。
 *
 * 型は backend の schemas.py（CandidateRankingItem / CandidateDetailOut /
 * ScoreOut / RequirementCheck）と対応する。
 */

/** スコア算出済みのランキング行。 */
const SCORED_ITEM: CandidateRankingItem = {
  candidate_id: 1,
  name: "山田 太郎",
  created_at: "2026-06-26T00:00:00Z",
  total_score: 87,
  skill_score: 90,
  experience_score: 85,
  industry_score: 80,
  position_score: 88,
  required_met: 3,
  required_total: 4,
};

/** スコア未算出のランキング行（スコア系フィールドが全て null）。 */
const PENDING_ITEM: CandidateRankingItem = {
  candidate_id: 2,
  name: "佐藤 花子",
  created_at: "2026-06-25T00:00:00Z",
  total_score: null,
  skill_score: null,
  experience_score: null,
  industry_score: null,
  position_score: null,
  required_met: null,
  required_total: null,
};

/** スコア算出済みの候補者詳細。 */
const SCORED_DETAIL: CandidateDetailOut = {
  id: 1,
  job_id: 10,
  name: "山田 太郎",
  age: 35,
  nearest_station: "渋谷",
  desired_rate: 80,
  experience_years: 10,
  skills: ["Python", "TypeScript"],
  certifications: ["AWS SAA"],
  work_history: "2015年〜現在: 株式会社サンプル エンジニア",
  education: "○○大学 情報工学部 卒業",
  self_pr: "フルスタックエンジニアとして活動してきました。",
  raw_text: "応募書類の原文テキスト",
  created_at: "2026-06-26T00:00:00Z",
  score: {
    id: 100,
    candidate_id: 1,
    total_score: 87,
    skill_score: 90,
    experience_score: 85,
    industry_score: 80,
    position_score: 88,
    required_met: 3,
    required_total: 4,
    requirement_checks: [
      { requirement: "Python", status: "充足", evidence: "10年の実務経験" },
      { requirement: "Go", status: "未充足", evidence: null },
    ],
    strengths: "幅広い技術スタックを扱える。",
    concerns: "マネジメント経験が浅い。",
    interview_points: "チームリードの意欲を確認する。",
    scored_at: "2026-06-26T01:00:00Z",
  },
};

/** スコア未算出の候補者詳細（score が null）。 */
const PENDING_DETAIL: CandidateDetailOut = {
  id: 2,
  job_id: 10,
  name: "佐藤 花子",
  age: null,
  nearest_station: null,
  desired_rate: null,
  experience_years: null,
  skills: [],
  certifications: [],
  work_history: null,
  education: null,
  self_pr: null,
  raw_text: "別の応募書類の原文",
  created_at: "2026-06-25T00:00:00Z",
  score: null,
};

describe("listRankings", () => {
  it("GET /jobs/{jobId}/rankings を叩き、ランキング一覧を返す", async () => {
    server.use(
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () =>
        HttpResponse.json([SCORED_ITEM, PENDING_ITEM]),
      ),
    );

    const items = await listRankings(10);

    expect(items).toEqual([SCORED_ITEM, PENDING_ITEM]);
    // 算出済みはスコアが入る。
    expect(items[0].total_score).toBe(87);
    expect(items[0].required_met).toBe(3);
    // 未算出はスコア系が全て null。
    expect(items[1].total_score).toBeNull();
    expect(items[1].skill_score).toBeNull();
    expect(items[1].required_total).toBeNull();
  });

  it("候補者0件のとき空配列を返す", async () => {
    server.use(
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () => HttpResponse.json([])),
    );

    const items = await listRankings(10);

    expect(items).toEqual([]);
  });

  it("name が null の行をそのまま返す（型整合）", async () => {
    server.use(
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () =>
        HttpResponse.json([{ ...SCORED_ITEM, name: null }]),
      ),
    );

    const items = await listRankings(10);

    expect(items[0].name).toBeNull();
  });

  it("求人が存在しない（404）とき ApiError.status=404 を投げる", async () => {
    server.use(
      http.get(`${API_BASE_URL}/jobs/999/rankings`, () =>
        HttpResponse.json({ detail: "Job not found" }, { status: 404 }),
      ),
    );

    const error = await listRankings(999).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
  });
});

describe("getCandidateDetail", () => {
  it("GET /candidates/{candidateId}/detail を叩き、算出済み詳細を返す", async () => {
    server.use(
      http.get(`${API_BASE_URL}/candidates/1/detail`, () =>
        HttpResponse.json(SCORED_DETAIL),
      ),
    );

    const detail = await getCandidateDetail(1);

    expect(detail).toEqual(SCORED_DETAIL);
    expect(detail.score).not.toBeNull();
    expect(detail.score?.total_score).toBe(87);
    // requirement_checks の status・evidence が型どおり復元される。
    expect(detail.score?.requirement_checks[0].status).toBe("充足");
    expect(detail.score?.requirement_checks[1].evidence).toBeNull();
  });

  it("スコア未算出の候補者は score が null（型整合）", async () => {
    server.use(
      http.get(`${API_BASE_URL}/candidates/2/detail`, () =>
        HttpResponse.json(PENDING_DETAIL),
      ),
    );

    const detail = await getCandidateDetail(2);

    expect(detail.score).toBeNull();
    expect(detail.name).toBe("佐藤 花子");
    expect(detail.skills).toEqual([]);
  });

  it("候補者が存在しない（404）とき ApiError.status=404 を投げる", async () => {
    server.use(
      http.get(`${API_BASE_URL}/candidates/999/detail`, () =>
        HttpResponse.json({ detail: "Candidate not found" }, { status: 404 }),
      ),
    );

    const error = await getCandidateDetail(999).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
  });
});
