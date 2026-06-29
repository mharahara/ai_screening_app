import * as React from "react";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { API_BASE_URL } from "@/lib/api";
import type {
  CandidateDetailOut,
  CandidateRankingItem,
} from "@/lib/rankings";
import JobRankingsPage from "@/app/jobs/[id]/rankings/page";
import { notFound, useParams } from "next/navigation";
import { server } from "./server";

/**
 * 候補者ランキング画面（app/jobs/[id]/rankings/page.tsx）の振る舞いテスト。
 *
 * - スコア算出済み候補者がスコア付きで表示される
 * - スコア未算出候補者は「算出中...」表示・「詳細」ボタン disabled
 * - 「詳細」押下で詳細ダイアログが開き 4 タブが描画される
 * - job_id が 404 のとき notFound() が呼ばれる
 * - ポーリング: 未算出→算出済みでスコア反映・ポーリング停止（fake timers）
 *
 * backend は MSW でモック。CSS ではなく振る舞い・状態遷移を見る。
 * next/navigation（useParams / notFound）はモックする。
 */

vi.mock("next/navigation", () => ({
  useParams: vi.fn(),
  notFound: vi.fn(),
}));

/** スコア未算出が残る間のポーリング間隔（ms）。ページ実装と一致させる。 */
const POLL_INTERVAL = 3000;

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
    ],
    strengths: "幅広い技術スタックを扱える。",
    concerns: "マネジメント経験が浅い。",
    interview_points: "チームリードの意欲を確認する。",
    scored_at: "2026-06-26T01:00:00Z",
  },
};

function newQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderPage() {
  return render(
    <QueryClientProvider client={newQueryClient()}>
      <JobRankingsPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  // base-ui の Dialog は Portal で body にマウントするため、残骸を掃除する。
  cleanup();
  document.body.innerHTML = "";
  vi.mocked(useParams).mockReset();
  vi.mocked(notFound).mockReset();
});

describe("ランキング表示", () => {
  it("スコア算出済みの候補者がスコア付きで表示される", async () => {
    vi.mocked(useParams).mockReturnValue({ id: "10" });
    server.use(
      http.get(`${API_BASE_URL}/jobs/10`, () =>
        HttpResponse.json({ id: 10, title: "テスト求人", created_at: "2024-01-01T00:00:00" }),
      ),
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () =>
        HttpResponse.json([SCORED_ITEM]),
      ),
    );

    renderPage();

    // 氏名と総合スコアが表示される。
    expect(await screen.findByText("山田 太郎")).toBeInTheDocument();
    expect(screen.getByText("87")).toBeInTheDocument();
    expect(screen.getByText("90")).toBeInTheDocument();
    // 必須充足は "3 / 4" 形式。
    expect(screen.getByText("3 / 4")).toBeInTheDocument();
    // 算出済みなので詳細ボタンは有効。
    expect(screen.getByRole("button", { name: "詳細" })).not.toBeDisabled();
  });

  it("候補者0件のとき空メッセージを表示する", async () => {
    vi.mocked(useParams).mockReturnValue({ id: "10" });
    server.use(
      http.get(`${API_BASE_URL}/jobs/10`, () =>
        HttpResponse.json({ id: 10, title: "テスト求人", created_at: "2024-01-01T00:00:00" }),
      ),
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () => HttpResponse.json([])),
    );

    renderPage();

    expect(
      await screen.findByText("この求人に紐づく候補者はまだいません。"),
    ).toBeInTheDocument();
  });

  it("スコア未算出の行は「算出中...」表示で詳細ボタンが disabled", async () => {
    vi.mocked(useParams).mockReturnValue({ id: "10" });
    server.use(
      http.get(`${API_BASE_URL}/jobs/10`, () =>
        HttpResponse.json({ id: 10, title: "テスト求人", created_at: "2024-01-01T00:00:00" }),
      ),
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () =>
        HttpResponse.json([PENDING_ITEM]),
      ),
    );

    renderPage();

    expect(await screen.findByText("佐藤 花子")).toBeInTheDocument();
    expect(screen.getByText("算出中...")).toBeInTheDocument();
    // 未算出行の詳細ボタンは押せない。
    expect(screen.getByRole("button", { name: "詳細" })).toBeDisabled();
  });
});

describe("詳細ダイアログ", () => {
  it("詳細ボタン押下でダイアログが開き 4 タブが描画される", async () => {
    vi.mocked(useParams).mockReturnValue({ id: "10" });
    server.use(
      http.get(`${API_BASE_URL}/jobs/10`, () =>
        HttpResponse.json({ id: 10, title: "テスト求人", created_at: "2024-01-01T00:00:00" }),
      ),
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () =>
        HttpResponse.json([SCORED_ITEM]),
      ),
      http.get(`${API_BASE_URL}/candidates/1/detail`, () =>
        HttpResponse.json(SCORED_DETAIL),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "詳細" }));

    // 4 タブが描画される。
    expect(
      await screen.findByRole("tab", { name: "基本プロフィール" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "スコア根拠" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "AIサマリー" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "応募書類" })).toBeInTheDocument();
  });

  it("スコア未算出（score: null）のときスコア根拠・AIサマリータブに算出中表示が出る", async () => {
    vi.mocked(useParams).mockReturnValue({ id: "10" });
    server.use(
      http.get(`${API_BASE_URL}/jobs/10`, () =>
        HttpResponse.json({ id: 10, title: "テスト求人", created_at: "2024-01-01T00:00:00" }),
      ),
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () =>
        HttpResponse.json([SCORED_ITEM]),
      ),
      // 一覧は算出済みでも、詳細取得時点ではスコアがまだ無いケース。
      http.get(`${API_BASE_URL}/candidates/1/detail`, () =>
        HttpResponse.json({ ...SCORED_DETAIL, score: null }),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "詳細" }));

    // base-ui の Tabs は選択中パネルのみ描画するため、各タブを開いて確認する。
    await user.click(await screen.findByRole("tab", { name: "スコア根拠" }));
    expect(await screen.findByText("スコア算出中です。")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "AIサマリー" }));
    expect(await screen.findByText("スコア算出中です。")).toBeInTheDocument();
  });
});

describe("404 ハンドリング", () => {
  it("求人が 404 のとき notFound() を呼ぶ", async () => {
    vi.mocked(useParams).mockReturnValue({ id: "999" });
    server.use(
      http.get(`${API_BASE_URL}/jobs/999/rankings`, () =>
        HttpResponse.json({ detail: "Job not found" }, { status: 404 }),
      ),
    );

    renderPage();

    await waitFor(() => expect(notFound).toHaveBeenCalled());
  });
});

describe("求人タイトル表示", () => {
  it("求人タイトルが取得できたとき <p> として表示される", async () => {
    vi.mocked(useParams).mockReturnValue({ id: "10" });
    server.use(
      http.get(`${API_BASE_URL}/jobs/10`, () =>
        HttpResponse.json({ id: 10, title: "シニア Rust エンジニア", created_at: "2026-06-01T00:00:00Z" }),
      ),
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () => HttpResponse.json([])),
    );

    renderPage();

    expect(await screen.findByText("シニア Rust エンジニア")).toBeInTheDocument();
  });

  it("title が null のとき「（無題）」が表示される", async () => {
    vi.mocked(useParams).mockReturnValue({ id: "10" });
    server.use(
      http.get(`${API_BASE_URL}/jobs/10`, () =>
        HttpResponse.json({ id: 10, title: null, created_at: "2026-06-01T00:00:00Z" }),
      ),
      http.get(`${API_BASE_URL}/jobs/10/rankings`, () => HttpResponse.json([])),
    );

    renderPage();

    expect(await screen.findByText("（無題）")).toBeInTheDocument();
  });
});

describe("スコア完了ポーリング", () => {
  it("未算出→算出済みに切り替わるとスコアが反映されポーリングが止まる", async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(useParams).mockReturnValue({ id: "10" });

      let callCount = 0;
      server.use(
        http.get(`${API_BASE_URL}/jobs/10`, () =>
          HttpResponse.json({ id: 10, title: "テスト求人", created_at: "2024-01-01T00:00:00" }),
        ),
        http.get(`${API_BASE_URL}/jobs/10/rankings`, () => {
          callCount += 1;
          // 1 回目は未算出、2 回目以降は算出済み（同一候補者）。
          const item =
            callCount === 1
              ? { ...PENDING_ITEM, candidate_id: 1, name: "山田 太郎" }
              : SCORED_ITEM;
          return HttpResponse.json([item]);
        }),
      );

      renderPage();

      // 初回フェッチを解決させる（state 反映を act でコミットさせる）。
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(screen.getByText("算出中...")).toBeInTheDocument();
      expect(callCount).toBe(1);

      // ポーリング間隔だけ進めると再フェッチされる。
      await act(async () => {
        await vi.advanceTimersByTimeAsync(POLL_INTERVAL);
      });
      expect(callCount).toBe(2);

      // 再フェッチ応答の配信・state 反映を流し込む（数 tick かかる）。
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
      expect(screen.getByText("87")).toBeInTheDocument();
      expect(screen.queryByText("算出中...")).not.toBeInTheDocument();

      // 全員確定したのでポーリングは停止する（以降フェッチが増えない）。
      await act(async () => {
        await vi.advanceTimersByTimeAsync(POLL_INTERVAL * 3);
      });
      expect(callCount).toBe(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
