import * as React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { API_BASE_URL } from "@/lib/api";
import type { CandidateParseResponse } from "@/lib/candidates";
import CandidateNewPage from "@/app/candidates/new/page";
import { server } from "./server";

/**
 * 応募書類取り込み画面（app/candidates/new/page.tsx）の振る舞いテスト。
 *
 * - parse 失敗系の文言出し分け（ApiError.code ごと）
 * - parse 成功でフォームに全フィールドが反映されること
 * - 求人0件・GET /jobs 失敗のエラー表示
 * - 求人選択で保存ボタンが有効化されること
 * - 保存時に全フィールド（job_id 含む）が送られること
 * - 保存成功後の成功メッセージとフォームリセット
 * - 保存失敗時のエラーメッセージ
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
      <CandidateNewPage />
    </QueryClientProvider>,
  );
}

const PARSE_RESPONSE: CandidateParseResponse = {
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
};

const JOB_LIST = [
  { id: 1, title: "Backend Engineer", created_at: "2026-06-26T00:00:00Z" },
  { id: 2, title: "Frontend Engineer", created_at: "2026-06-25T00:00:00Z" },
];

beforeEach(() => {
  // 既定: 求人一覧は 2 件。個別テストで上書きする。
  server.use(http.get(`${API_BASE_URL}/jobs`, () => HttpResponse.json(JOB_LIST)));
});

afterEach(() => {
  // @base-ui/react の Select は Portal を通じて body にポジショナーを常時マウントする。
  // cleanup() でコンポーネントツリーを unmount した後も body に残骸が残る場合があるため
  // body を空にしてテスト間の干渉を防ぐ。
  cleanup();
  document.body.innerHTML = "";
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
        http.post(`${API_BASE_URL}/candidates/parse`, () =>
          HttpResponse.json({ detail: { code, message: "boom" } }, { status }),
        ),
      );

      const user = userEvent.setup();
      renderPage();

      await user.type(screen.getByLabelText("応募書類テキスト"), "テキスト");
      await user.click(screen.getByRole("button", { name: "解析する" }));

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(text);
    },
  );
});

describe("parse 成功 → フォーム反映", () => {
  it("parse 成功で全フィールドがフォームに反映される", async () => {
    server.use(
      http.post(`${API_BASE_URL}/candidates/parse`, () =>
        HttpResponse.json(PARSE_RESPONSE),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    // parse 前はフォームが出ていない。
    expect(
      screen.getByText("「解析する」を実行すると、ここに編集フォームが表示されます。"),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("応募書類テキスト"), "原文");
    await user.click(screen.getByRole("button", { name: "解析する" }));

    // 氏名フィールドが反映される。
    const nameInput = await screen.findByLabelText<HTMLInputElement>("氏名");
    expect(nameInput.value).toBe("山田 太郎");

    // 年齢フィールドが反映される。
    const ageInput = screen.getByLabelText<HTMLInputElement>("年齢（歳）");
    expect(ageInput.value).toBe("35");

    // 経験年数フィールドが反映される。
    const expInput = screen.getByLabelText<HTMLInputElement>("経験年数（年）");
    expect(expInput.value).toBe("10");

    // 希望単価フィールドが反映される。
    const rateInput = screen.getByLabelText<HTMLInputElement>("希望単価（万円/月）");
    expect(rateInput.value).toBe("80");

    // 最寄り駅フィールドが反映される。
    const stationInput = screen.getByLabelText<HTMLInputElement>("最寄り駅");
    expect(stationInput.value).toBe("渋谷");

    // スキルのタグが反映される。
    expect(
      screen.getByRole("button", { name: "Python を削除" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "TypeScript を削除" }),
    ).toBeInTheDocument();

    // 資格のタグが反映される。
    expect(
      screen.getByRole("button", { name: "AWS SAA を削除" }),
    ).toBeInTheDocument();

    // 職歴テキストエリアが反映される。
    const workHistoryTextarea = screen.getByLabelText<HTMLTextAreaElement>("職歴");
    expect(workHistoryTextarea.value).toBe(
      "2015年〜現在: 株式会社サンプル エンジニア",
    );

    // 学歴テキストエリアが反映される。
    const educationTextarea = screen.getByLabelText<HTMLTextAreaElement>("学歴");
    expect(educationTextarea.value).toBe("○○大学 情報工学部 卒業");

    // 自己PRテキストエリアが反映される。
    const selfPrTextarea = screen.getByLabelText<HTMLTextAreaElement>("自己PR");
    expect(selfPrTextarea.value).toBe(
      "フルスタックエンジニアとして活動してきました。",
    );
  });
});

describe("求人セレクターの状態", () => {
  it("GET /jobs が空配列のとき「先に求人を登録してください」が表示される", async () => {
    server.use(
      http.get(`${API_BASE_URL}/jobs`, () => HttpResponse.json([])),
      http.post(`${API_BASE_URL}/candidates/parse`, () =>
        HttpResponse.json(PARSE_RESPONSE),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    // parse してフォームを表示する。
    await user.type(screen.getByLabelText("応募書類テキスト"), "原文");
    await user.click(screen.getByRole("button", { name: "解析する" }));

    // フォームが表示された後で求人0件メッセージを確認する。
    await screen.findByLabelText("氏名");
    expect(
      screen.getByText("先に求人を登録してください。"),
    ).toBeInTheDocument();
  });

  it("GET /jobs がエラーのとき「求人一覧の取得に失敗しました。」が表示される", async () => {
    server.use(
      http.get(`${API_BASE_URL}/jobs`, () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
      http.post(`${API_BASE_URL}/candidates/parse`, () =>
        HttpResponse.json(PARSE_RESPONSE),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    // parse してフォームを表示する。
    await user.type(screen.getByLabelText("応募書類テキスト"), "原文");
    await user.click(screen.getByRole("button", { name: "解析する" }));

    // フォームが表示された後でエラーメッセージを確認する。
    await screen.findByLabelText("氏名");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("求人一覧の取得に失敗しました。");
  });

  it("求人を選択すると保存ボタンが有効になる（未選択は disabled）", async () => {
    server.use(
      http.post(`${API_BASE_URL}/candidates/parse`, () =>
        HttpResponse.json(PARSE_RESPONSE),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("応募書類テキスト"), "原文");
    await user.click(screen.getByRole("button", { name: "解析する" }));

    // フォームが表示されるまで待つ。
    await screen.findByLabelText("氏名");

    // 保存ボタンは求人未選択なので disabled。
    const saveButton = screen.getByRole("button", { name: "保存する" });
    expect(saveButton).toBeDisabled();

    // 求人セレクターから Backend Engineer を選択する。
    await user.click(screen.getByRole("combobox"));
    const option = await screen.findByRole("option", { name: /Backend Engineer #1/ });
    await user.click(option);

    // 保存ボタンが有効になる。
    expect(saveButton).not.toBeDisabled();
  });
});

describe("保存の状態遷移", () => {
  it("保存時に全フィールド（job_id 含む）が POST /candidates に送られる", async () => {
    let createBody: Record<string, unknown> | undefined;
    server.use(
      http.post(`${API_BASE_URL}/candidates/parse`, () =>
        HttpResponse.json(PARSE_RESPONSE),
      ),
      http.post(`${API_BASE_URL}/candidates`, async ({ request }) => {
        createBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { ...createBody, id: 1, created_at: "2026-06-26T00:00:00Z" },
          { status: 201 },
        );
      }),
    );

    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("応募書類テキスト"), "原文");
    await user.click(screen.getByRole("button", { name: "解析する" }));

    // フォームが表示されるまで待つ。
    await screen.findByLabelText("氏名");

    // 求人を選択する。
    await user.click(screen.getByRole("combobox"));
    const option = await screen.findByRole("option", { name: /Backend Engineer #1/ });
    await user.click(option);

    // 保存する。
    await user.click(screen.getByRole("button", { name: "保存する" }));

    await waitFor(() => expect(createBody).toBeDefined());

    // 全フィールドが含まれている。
    expect(createBody?.name).toBe("山田 太郎");
    expect(createBody?.age).toBe(35);
    expect(createBody?.nearest_station).toBe("渋谷");
    expect(createBody?.desired_rate).toBe(80);
    expect(createBody?.experience_years).toBe(10);
    expect(createBody?.skills).toEqual(["Python", "TypeScript"]);
    expect(createBody?.certifications).toEqual(["AWS SAA"]);
    expect(createBody?.work_history).toBe(
      "2015年〜現在: 株式会社サンプル エンジニア",
    );
    expect(createBody?.education).toBe("○○大学 情報工学部 卒業");
    expect(createBody?.self_pr).toBe(
      "フルスタックエンジニアとして活動してきました。",
    );
    // job_id が含まれている。
    expect(createBody?.job_id).toBe(1);
    // raw_text は parse 時の原文がそのまま送られる。
    expect(createBody?.raw_text).toBe("応募書類の原文テキスト");
  });

  it("保存成功後に成功メッセージが表示されフォームがリセットされる", async () => {
    server.use(
      http.post(`${API_BASE_URL}/candidates/parse`, () =>
        HttpResponse.json(PARSE_RESPONSE),
      ),
      http.post(`${API_BASE_URL}/candidates`, async ({ request }) => {
        const body = await request.json();
        return HttpResponse.json(
          { ...(body as object), id: 1, created_at: "2026-06-26T00:00:00Z" },
          { status: 201 },
        );
      }),
    );

    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("応募書類テキスト"), "原文");
    await user.click(screen.getByRole("button", { name: "解析する" }));

    await screen.findByLabelText("氏名");

    // 求人を選択する。
    await user.click(screen.getByRole("combobox"));
    const option = await screen.findByRole("option", { name: /Backend Engineer #1/ });
    await user.click(option);

    // 保存する。
    await user.click(screen.getByRole("button", { name: "保存する" }));

    // 成功メッセージが表示される。
    expect(await screen.findByRole("status")).toHaveTextContent(
      "候補者を保存しました。",
    );

    // フォームがリセットされる（parse 前の状態に戻る）。
    expect(
      screen.getByText("「解析する」を実行すると、ここに編集フォームが表示されます。"),
    ).toBeInTheDocument();
  });

  it("POST /candidates 失敗時に「保存に失敗しました。再試行してください。」が表示される", async () => {
    server.use(
      http.post(`${API_BASE_URL}/candidates/parse`, () =>
        HttpResponse.json(PARSE_RESPONSE),
      ),
      http.post(`${API_BASE_URL}/candidates`, () =>
        HttpResponse.json({ detail: "Internal Server Error" }, { status: 500 }),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("応募書類テキスト"), "原文");
    await user.click(screen.getByRole("button", { name: "解析する" }));

    await screen.findByLabelText("氏名");

    // 求人を選択する。
    await user.click(screen.getByRole("combobox"));
    const option = await screen.findByRole("option", { name: /Backend Engineer #1/ });
    await user.click(option);

    // 保存する。
    await user.click(screen.getByRole("button", { name: "保存する" }));

    // エラーメッセージが表示される。
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("保存に失敗しました。再試行してください。");
  });
});
