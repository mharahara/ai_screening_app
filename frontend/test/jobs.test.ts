import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
  createJob,
  deleteJob,
  listJobs,
  parseJob,
  type JobCreate,
  type JobParseResponse,
} from "@/lib/jobs";
import { ApiError, API_BASE_URL } from "@/lib/api";
import { server } from "./server";

/**
 * `lib/jobs.ts` の API クライアント契約テスト。
 *
 * backend は MSW でネットワーク層モックし、各関数が
 * - 正しいメソッド・パスを叩くこと
 * - 正しいボディを送ること（リクエストを捕捉して assert）
 * - レスポンス（型）をそのまま返すこと
 * - 失敗系で ApiError.code が立つこと
 * を検証する。LLM 応答の質はテスト対象外で、契約（通り道）のみ見る。
 */

/** 全フィールドを含む parse 結果のフィクスチャ（型整合の確認も兼ねる）。 */
const PARSE_RESULT: JobParseResponse = {
  title: "Backend Engineer",
  description: "API 開発",
  required_skills: ["Python", "FastAPI"],
  preferred_skills: ["AWS"],
  ideal_profile: "自走できる人",
  rate_min: 60,
  rate_max: 90,
  min_experience_years: 3,
  position_level: "シニア",
  industry_experience: "SaaS",
  certifications: ["AWS SAA"],
  raw_text: "求人票の原文テキスト",
};

describe("parseJob", () => {
  it("POST /jobs/parse に { raw_text } を送り、構造化結果を返す", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(`${API_BASE_URL}/jobs/parse`, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(PARSE_RESULT);
      }),
    );

    const result = await parseJob("求人票の原文テキスト");

    // リクエストボディは { raw_text } のみ。
    expect(receivedBody).toEqual({ raw_text: "求人票の原文テキスト" });
    // レスポンスは全フィールド + raw_text をそのまま返す。
    expect(result).toEqual(PARSE_RESULT);
    expect(result.required_skills).toEqual(["Python", "FastAPI"]);
    expect(result.raw_text).toBe("求人票の原文テキスト");
  });

  it.each([
    { status: 502, code: "PARSE_FAILED" },
    { status: 503, code: "LLM_UNAVAILABLE" },
    { status: 502, code: "LLM_TIMEOUT" },
  ])(
    "失敗レスポンス（$status / $code）で ApiError.code が立つ",
    async ({ status, code }) => {
      server.use(
        http.post(`${API_BASE_URL}/jobs/parse`, () =>
          HttpResponse.json(
            { detail: { code, message: "boom", attempts: 2 } },
            { status },
          ),
        ),
      );

      const error = await parseJob("x").catch((e) => e);

      expect(error).toBeInstanceOf(ApiError);
      expect(error.status).toBe(status);
      expect(error.code).toBe(code);
      expect(error.message).toBe("boom");
    },
  );
});

describe("createJob", () => {
  it("POST /jobs に全フィールド + raw_text を送り、JobOut を返す", async () => {
    const input: JobCreate = {
      title: PARSE_RESULT.title,
      description: PARSE_RESULT.description,
      required_skills: PARSE_RESULT.required_skills,
      preferred_skills: PARSE_RESULT.preferred_skills,
      ideal_profile: PARSE_RESULT.ideal_profile,
      rate_min: PARSE_RESULT.rate_min,
      rate_max: PARSE_RESULT.rate_max,
      min_experience_years: PARSE_RESULT.min_experience_years,
      position_level: PARSE_RESULT.position_level,
      industry_experience: PARSE_RESULT.industry_experience,
      certifications: PARSE_RESULT.certifications,
      raw_text: PARSE_RESULT.raw_text,
      matching_instructions: null,
    };

    let receivedBody: unknown;
    server.use(
      http.post(`${API_BASE_URL}/jobs`, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(
          { ...input, id: 42, created_at: "2026-06-26T00:00:00Z" },
          { status: 201 },
        );
      }),
    );

    const result = await createJob(input);

    // ボディは全フィールド + raw_text を含む。
    expect(receivedBody).toEqual(input);
    expect((receivedBody as JobCreate).raw_text).toBe(PARSE_RESULT.raw_text);
    // レスポンスは id・created_at 込み。
    expect(result.id).toBe(42);
    expect(result.created_at).toBe("2026-06-26T00:00:00Z");
    expect(result.title).toBe("Backend Engineer");
  });
});

describe("listJobs", () => {
  it("GET /jobs を叩いて一覧を返す", async () => {
    const fixture = [
      { id: 1, title: "Backend Engineer", created_at: "2026-06-26T00:00:00Z" },
      { id: 2, title: null, created_at: "2026-06-25T00:00:00Z" },
    ];

    server.use(
      http.get(`${API_BASE_URL}/jobs`, () => HttpResponse.json(fixture)),
    );

    const jobs = await listJobs();

    expect(jobs).toEqual(fixture);
    expect(jobs[0].id).toBe(1);
    expect(jobs[1].title).toBeNull();
  });

  it("0 件のとき空配列を返す", async () => {
    server.use(http.get(`${API_BASE_URL}/jobs`, () => HttpResponse.json([])));

    const jobs = await listJobs();

    expect(jobs).toEqual([]);
  });
});

describe("deleteJob", () => {
  it("DELETE /jobs/{id} を叩き、204 を正常処理する", async () => {
    let called = false;
    server.use(
      http.delete(`${API_BASE_URL}/jobs/7`, () => {
        called = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    await expect(deleteJob(7)).resolves.toBeUndefined();
    expect(called).toBe(true);
  });
});
