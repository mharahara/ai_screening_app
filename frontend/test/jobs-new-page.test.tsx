import * as React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { API_BASE_URL } from "@/lib/api";
import type { JobParseResponse } from "@/lib/jobs";
import JobNewPage from "@/app/jobs/new/page";
import { server } from "./server";

/**
 * 求人取り込み画面（app/jobs/new/page.tsx）の振る舞いテスト。
 *
 * - parse 失敗系の文言出し分け（ApiError.code ごと）
 * - parse → 編集 → 保存の状態遷移（createJob が raw_text 込みで送ること）
 * - 保存済み一覧の描画と削除後の invalidate（一覧更新）
 *
 * backend は MSW でモック。CSS ではなく振る舞い・状態遷移を見る。
 */

function renderPage() {
  // テスト用 QueryClient。リトライ無効で失敗系を決定的にする。
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <JobNewPage />
    </QueryClientProvider>,
  );
}

const PARSE_RESPONSE: JobParseResponse = {
  title: "Backend Engineer",
  description: "API 開発",
  required_skills: ["Python"],
  preferred_skills: [],
  ideal_profile: null,
  employment_type: "業務委託",
  location: "東京",
  remote_work: "フルリモート",
  rate_min: 60,
  rate_max: 90,
  min_experience_years: 3,
  position_level: "シニア",
  industry_experience: null,
  certifications: [],
  raw_text: "求人票の原文テキスト",
};

beforeEach(() => {
  // 既定: 一覧は空（個別テストで上書きする）。
  server.use(http.get(`${API_BASE_URL}/jobs`, () => HttpResponse.json([])));
});

afterEach(() => {
  // 念のため confirm 等のグローバル状態はないが、ハンドラは setup.ts でリセット。
});

describe("parse 失敗系の文言出し分け", () => {
  it.each([
    {
      status: 502,
      code: "PARSE_FAILED",
      text: "構造化に失敗しました。テキストを確認して再試行してください。",
    },
    {
      status: 503,
      code: "LLM_UNAVAILABLE",
      text: "Ollama に接続できません。起動を確認してください。",
    },
    {
      status: 502,
      code: "LLM_TIMEOUT",
      text: "構造化がタイムアウトしました。再試行してください。",
    },
  ])(
    "$code のとき専用文言を表示する",
    async ({ status, code, text }) => {
      server.use(
        http.post(`${API_BASE_URL}/jobs/parse`, () =>
          HttpResponse.json({ detail: { code, message: "boom" } }, { status }),
        ),
      );

      const user = userEvent.setup();
      renderPage();

      await user.type(
        screen.getByLabelText("求人票テキスト"),
        "テキスト",
      );
      await user.click(screen.getByRole("button", { name: "構造化する" }));

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(text);
    },
  );

  it("未知のエラーコードでは汎用文言を表示する", async () => {
    server.use(
      http.post(`${API_BASE_URL}/jobs/parse`, () =>
        HttpResponse.json({ detail: { code: "WHATEVER" } }, { status: 500 }),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("求人票テキスト"), "テキスト");
    await user.click(screen.getByRole("button", { name: "構造化する" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "構造化中にエラーが発生しました。しばらくして再試行してください。",
    );
  });
});

describe("parse → 編集 → 保存の状態遷移", () => {
  it("parse 成功でフォームに値が反映され、保存で raw_text 込みのボディを送る", async () => {
    let createBody: Record<string, unknown> | undefined;
    server.use(
      http.post(`${API_BASE_URL}/jobs/parse`, () =>
        HttpResponse.json(PARSE_RESPONSE),
      ),
      http.post(`${API_BASE_URL}/jobs`, async ({ request }) => {
        createBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { ...createBody, id: 1, created_at: "2026-06-26T00:00:00Z" },
          { status: 201 },
        );
      }),
    );

    const user = userEvent.setup();
    renderPage();

    // parse 前はフォームが出ていない。
    expect(
      screen.getByText(
        "「構造化する」を実行すると、ここに編集フォームが表示されます。",
      ),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("求人票テキスト"), "原文");
    await user.click(screen.getByRole("button", { name: "構造化する" }));

    // parse 成功でフォームに値が反映される。
    const titleInput = await screen.findByLabelText<HTMLInputElement>(
      "タイトル",
    );
    expect(titleInput.value).toBe("Backend Engineer");
    // 必須スキルのタグが反映される。
    expect(
      screen.getByRole("button", { name: "Python を削除" }),
    ).toBeInTheDocument();

    // タイトルを編集する。
    await user.clear(titleInput);
    await user.type(titleInput, "Edited Title");

    await user.click(screen.getByRole("button", { name: "保存する" }));

    await waitFor(() => expect(createBody).toBeDefined());

    // raw_text は parse 時の原文がそのまま送られる。
    expect(createBody?.raw_text).toBe("求人票の原文テキスト");
    // 編集したタイトルが反映されている。
    expect(createBody?.title).toBe("Edited Title");
    // 構造化結果のフィールドも送られる。
    expect(createBody?.required_skills).toEqual(["Python"]);
    expect(createBody?.employment_type).toBe("業務委託");

    // 保存成功で成功メッセージが出る。
    expect(await screen.findByRole("status")).toHaveTextContent(
      "求人を保存しました。",
    );
  });
});

describe("保存済み一覧と削除", () => {
  it("listJobs の結果を描画し、削除後に一覧が更新される", async () => {
    let listCallCount = 0;
    const initial = [
      { id: 1, title: "Job A", created_at: "2026-06-26T00:00:00Z" },
      { id: 2, title: "Job B", created_at: "2026-06-25T00:00:00Z" },
    ];
    const afterDelete = [initial[0]];

    server.use(
      http.get(`${API_BASE_URL}/jobs`, () => {
        listCallCount += 1;
        // 1 回目は 2 件、削除後（invalidate での再取得）は 1 件。
        return HttpResponse.json(listCallCount === 1 ? initial : afterDelete);
      }),
      http.delete(`${API_BASE_URL}/jobs/2`, () => {
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const user = userEvent.setup();
    renderPage();

    // 一覧が描画される。
    expect(await screen.findByText("Job A")).toBeInTheDocument();
    expect(screen.getByText("Job B")).toBeInTheDocument();

    // Job B の削除ボタン（行内）を押す → 確認ダイアログ。
    const jobBItem = screen.getByText("Job B").closest("li");
    expect(jobBItem).not.toBeNull();
    await user.click(
      within(jobBItem as HTMLElement).getByRole("button", { name: /削除/ }),
    );

    // 確認ダイアログの「削除する」を押す。
    const confirmButton = await screen.findByRole("button", {
      name: "削除する",
    });
    await user.click(confirmButton);

    // invalidate → 再取得で Job B が消える。
    await waitFor(() =>
      expect(screen.queryByText("Job B")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Job A")).toBeInTheDocument();
    expect(listCallCount).toBeGreaterThanOrEqual(2);
  });

  it("一覧が 0 件のとき空状態の文言を表示する", async () => {
    server.use(http.get(`${API_BASE_URL}/jobs`, () => HttpResponse.json([])));

    renderPage();

    expect(
      await screen.findByText("保存済みの求人はありません。"),
    ).toBeInTheDocument();
  });

  it("一覧取得に失敗してもクラッシュせずエラー文言を表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/jobs`, () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );

    renderPage();

    expect(
      await screen.findByText("求人一覧の取得に失敗しました。"),
    ).toBeInTheDocument();
  });
});
