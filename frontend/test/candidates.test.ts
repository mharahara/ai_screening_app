import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
  createCandidate,
  parseCandidate,
  type CandidateCreate,
  type CandidateParseResponse,
} from "@/lib/candidates";
import { ApiError, API_BASE_URL } from "@/lib/api";
import { server } from "./server";

/**
 * `lib/candidates.ts` の API クライアント契約テスト。
 *
 * backend は MSW でネットワーク層モックし、各関数が
 * - 正しいメソッド・パスを叩くこと
 * - 正しいボディを送ること（リクエストを捕捉して assert）
 * - レスポンス（型）をそのまま返すこと
 * - 失敗系で ApiError.code が立つこと
 * を検証する。LLM 応答の質はテスト対象外で、契約（通り道）のみ見る。
 */

/** 全フィールドを含む parse 結果のフィクスチャ（型整合の確認も兼ねる）。 */
const PARSE_RESULT: CandidateParseResponse = {
  name: "山田 太郎",
  age: 35,
  nearest_station: "渋谷",
  desired_rate: 80,
  experience_years: 10,
  skills: ["Python", "TypeScript", "React"],
  certifications: ["AWS SAA", "情報処理技術者"],
  work_history: "2015年〜現在: 株式会社サンプル エンジニア",
  education: "○○大学 情報工学部 卒業",
  self_pr: "フルスタックエンジニアとして活動してきました。",
  raw_text: "応募書類の原文テキスト",
};

describe("parseCandidate", () => {
  it("POST /candidates/parse に { raw_text } を送り、構造化結果を返す", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(`${API_BASE_URL}/candidates/parse`, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(PARSE_RESULT);
      }),
    );

    const result = await parseCandidate("応募書類の原文テキスト");

    // リクエストボディは { raw_text } のみ。
    expect(receivedBody).toEqual({ raw_text: "応募書類の原文テキスト" });
    // レスポンスは全フィールド + raw_text をそのまま返す。
    expect(result).toEqual(PARSE_RESULT);
    expect(result.skills).toEqual(["Python", "TypeScript", "React"]);
    expect(result.certifications).toEqual(["AWS SAA", "情報処理技術者"]);
    expect(result.raw_text).toBe("応募書類の原文テキスト");
  });

  it("null 許容フィールドが null のときもそのまま返す", async () => {
    const parseResultWithNulls: CandidateParseResponse = {
      name: null,
      age: null,
      nearest_station: null,
      desired_rate: null,
      experience_years: null,
      skills: [],
      certifications: [],
      work_history: null,
      education: null,
      self_pr: null,
      raw_text: "テキスト",
    };

    server.use(
      http.post(`${API_BASE_URL}/candidates/parse`, () =>
        HttpResponse.json(parseResultWithNulls),
      ),
    );

    const result = await parseCandidate("テキスト");

    expect(result.name).toBeNull();
    expect(result.age).toBeNull();
    expect(result.skills).toEqual([]);
    expect(result.certifications).toEqual([]);
    expect(result.raw_text).toBe("テキスト");
  });

  it.each([
    { status: 502, code: "PARSE_FAILED" },
    { status: 503, code: "LLM_UNAVAILABLE" },
    { status: 502, code: "LLM_TIMEOUT" },
  ])(
    "失敗レスポンス（$status / $code）で ApiError.code が立つ",
    async ({ status, code }) => {
      server.use(
        http.post(`${API_BASE_URL}/candidates/parse`, () =>
          HttpResponse.json(
            { detail: { code, message: "boom", attempts: 2 } },
            { status },
          ),
        ),
      );

      const error = await parseCandidate("x").catch((e) => e);

      expect(error).toBeInstanceOf(ApiError);
      expect(error.status).toBe(status);
      expect(error.code).toBe(code);
      expect(error.message).toBe("boom");
    },
  );
});

describe("createCandidate", () => {
  it("POST /candidates に全フィールド + job_id + raw_text を送り、CandidateOut を返す", async () => {
    const input: CandidateCreate = {
      name: PARSE_RESULT.name,
      age: PARSE_RESULT.age,
      nearest_station: PARSE_RESULT.nearest_station,
      desired_rate: PARSE_RESULT.desired_rate,
      experience_years: PARSE_RESULT.experience_years,
      skills: PARSE_RESULT.skills,
      certifications: PARSE_RESULT.certifications,
      work_history: PARSE_RESULT.work_history,
      education: PARSE_RESULT.education,
      self_pr: PARSE_RESULT.self_pr,
      job_id: 3,
      raw_text: PARSE_RESULT.raw_text,
    };

    let receivedBody: unknown;
    server.use(
      http.post(`${API_BASE_URL}/candidates`, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(
          { ...input, id: 99, created_at: "2026-06-26T00:00:00Z" },
          { status: 201 },
        );
      }),
    );

    const result = await createCandidate(input);

    // ボディは全フィールド + job_id + raw_text を含む。
    expect(receivedBody).toEqual(input);
    expect((receivedBody as CandidateCreate).job_id).toBe(3);
    expect((receivedBody as CandidateCreate).raw_text).toBe(PARSE_RESULT.raw_text);
    // レスポンスは id・created_at 込み。
    expect(result.id).toBe(99);
    expect(result.created_at).toBe("2026-06-26T00:00:00Z");
    expect(result.name).toBe("山田 太郎");
    expect(result.skills).toEqual(["Python", "TypeScript", "React"]);
  });

  it.each([
    { status: 422, code: undefined },
    { status: 500, code: undefined },
  ])(
    "保存失敗（$status）で ApiError がスローされる",
    async ({ status }) => {
      server.use(
        http.post(`${API_BASE_URL}/candidates`, () =>
          HttpResponse.json(
            { detail: "Validation error" },
            { status },
          ),
        ),
      );

      const error = await createCandidate({
        name: null,
        age: null,
        nearest_station: null,
        desired_rate: null,
        experience_years: null,
        skills: [],
        certifications: [],
        work_history: null,
        education: null,
        self_pr: null,
        job_id: 1,
        raw_text: "x",
      }).catch((e) => e);

      expect(error).toBeInstanceOf(ApiError);
      expect(error.status).toBe(status);
    },
  );
});
