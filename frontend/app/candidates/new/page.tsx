"use client";

import * as React from "react";
import Link from "next/link";
import { ClipboardIcon, ClipboardCheckIcon } from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";
import {
  createCandidate,
  parseCandidate,
  type CandidateParseResult,
  type CandidateParseResponse,
} from "@/lib/candidates";
import { listJobs } from "@/lib/jobs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { TagInput } from "@/components/tag-input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const JOBS_QUERY_KEY = ["jobs"] as const;

const CANDIDATE_TEMPLATE = `【氏名】


【年齢】
〇〇歳

【最寄り駅】


【希望単価】
〇〇万円/月

【経験年数】
〇年

【スキル】
・

【資格・学位】
・

【職歴】
〇〇年〇月〜〇〇年〇月　株式会社〇〇
・職種：
・業務内容：

〇〇年〇月〜〇〇年〇月　株式会社〇〇
・職種：
・業務内容：

【学歴】
〇〇年〇月　〇〇大学〇〇学部卒業

【自己PR】
`;

/** parse の空フォーム初期値。 */
const EMPTY_FORM: CandidateParseResult = {
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
};

/**
 * parse 失敗時の文言を `ApiError.detail.code` で出し分ける。
 * code が無い／未知のエラーは汎用文言を返す。
 */
function parseErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "LLM_UNAVAILABLE":
        return "Ollama に接続できません。起動を確認してください。";
      case "LLM_TIMEOUT":
        return "構造化がタイムアウトしました。再試行してください。";
      case "PARSE_FAILED":
        return "構造化に失敗しました。テキストを確認して再試行してください。";
      default:
        return "構造化中にエラーが発生しました。しばらくして再試行してください。";
    }
  }
  return "予期しないエラーが発生しました。しばらくして再試行してください。";
}

/** 未選択（null）を表す番兵値。 */
const NONE_VALUE = "__none__";

/** 数値 Input の値を null 許容で扱う。 */
function NumberField({
  id,
  value,
  placeholder,
  onChange,
}: {
  id: string;
  value: number | null;
  placeholder?: string;
  onChange: (next: number | null) => void;
}) {
  return (
    <Input
      id={id}
      type="number"
      inputMode="numeric"
      placeholder={placeholder}
      value={value ?? ""}
      onChange={(e) => {
        const raw = e.target.value;
        onChange(raw === "" ? null : Number(raw));
      }}
    />
  );
}

export default function CandidateNewPage() {
  const [rawText, setRawText] = React.useState("");
  const [hasCopiedTemplate, setHasCopiedTemplate] = React.useState(false);
  const [savedRawText, setSavedRawText] = React.useState("");
  const [form, setForm] = React.useState<CandidateParseResult>(EMPTY_FORM);
  const [hasParsed, setHasParsed] = React.useState(false);
  const [saveSuccess, setSaveSuccess] = React.useState(false);
  const [selectedJobId, setSelectedJobId] = React.useState<number | null>(null);
  const [savedJobId, setSavedJobId] = React.useState<number | null>(null);

  function patch<K extends keyof CandidateParseResult>(
    key: K,
    val: CandidateParseResult[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: val }));
    setSaveSuccess(false);
  }

  const parseMutation = useMutation({
    mutationFn: (text: string) => parseCandidate(text),
    onSuccess: (data: CandidateParseResponse) => {
      const { raw_text, ...rest } = data;
      setForm(rest);
      setSavedRawText(raw_text);
      setHasParsed(true);
      setSaveSuccess(false);
    },
  });

  const createMutation = useMutation({
    mutationFn: () => {
      if (selectedJobId === null) {
        throw new Error("求人が選択されていません。");
      }
      return createCandidate({
        ...form,
        job_id: selectedJobId,
        raw_text: savedRawText,
      });
    },
    onSuccess: (data) => {
      // ランキング誘導用に保存先の求人 id を控えてから選択状態をリセットする。
      setSavedJobId(data.job_id);
      setForm(EMPTY_FORM);
      setRawText("");
      setSavedRawText("");
      setHasParsed(false);
      setSelectedJobId(null);
      setSaveSuccess(true);
    },
  });

  const jobsQuery = useQuery({
    queryKey: JOBS_QUERY_KEY,
    queryFn: listJobs,
  });

  const isSaveDisabled =
    createMutation.isPending ||
    selectedJobId === null ||
    (jobsQuery.isSuccess && jobsQuery.data.length === 0);

  const jobSelectorElement = (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="job-select">対象求人</Label>
      {jobsQuery.isError ? (
        <p role="alert" className="text-sm text-destructive">
          求人一覧の取得に失敗しました。
        </p>
      ) : jobsQuery.isSuccess && jobsQuery.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          先に求人を登録してください。
        </p>
      ) : (
        <Select
          value={selectedJobId !== null ? String(selectedJobId) : NONE_VALUE}
          onValueChange={(next) => {
            if (next === NONE_VALUE || next == null) {
              setSelectedJobId(null);
            } else {
              setSelectedJobId(Number(next));
            }
          }}
        >
          <SelectTrigger id="job-select" className="w-full">
            <SelectValue placeholder="求人を選択してください" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE_VALUE}>（未選択）</SelectItem>
            {jobsQuery.isSuccess &&
              jobsQuery.data.map((job) => (
                <SelectItem key={job.id} value={String(job.id)}>
                  {job.title ?? "（無題）"} #{job.id}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
      )}
    </div>
  );

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">
          応募書類の取り込み
        </h1>
        <p className="text-sm text-muted-foreground">
          応募書類の生テキストを構造化し、編集して保存します。
        </p>
      </header>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 左: 生テキスト入力 */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="raw-text">応募書類テキスト</Label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                navigator.clipboard.writeText(CANDIDATE_TEMPLATE).then(() => {
                  setHasCopiedTemplate(true);
                  setTimeout(() => setHasCopiedTemplate(false), 2000);
                });
              }}
            >
              {hasCopiedTemplate ? (
                <>
                  <ClipboardCheckIcon />
                  コピーしました
                </>
              ) : (
                <>
                  <ClipboardIcon />
                  テンプレをコピー
                </>
              )}
            </Button>
          </div>
          <Textarea
            id="raw-text"
            className="min-h-72 max-h-72"
            placeholder="職務経歴書・履歴書の本文を貼り付けてください。"
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
          />
          <div className="flex items-center gap-3">
            <Button
              type="button"
              onClick={() => parseMutation.mutate(rawText)}
              disabled={rawText.trim() === "" || parseMutation.isPending}
            >
              {parseMutation.isPending ? "解析中..." : "解析する"}
            </Button>
            {parseMutation.isError && (
              <p role="alert" className="text-sm text-destructive">
                {parseErrorMessage(parseMutation.error)}
              </p>
            )}
          </div>
        </div>

        {/* 右: 構造化結果の編集フォーム */}
        <div className="flex flex-col gap-4">
          {parseMutation.isPending && !hasParsed ? (
            <div className="flex flex-col gap-4">
              {/* 対象求人セレクターはLLM出力ではないため通常表示 */}
              {jobSelectorElement}
              <div className="flex flex-col gap-1.5">
                <Label>氏名</Label>
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <Label>年齢（歳）</Label>
                  <Skeleton className="h-9 w-full" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>経験年数（年）</Label>
                  <Skeleton className="h-9 w-full" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>希望単価（万円/月）</Label>
                  <Skeleton className="h-9 w-full" />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>最寄り駅</Label>
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>スキル</Label>
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>資格・学位</Label>
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>職歴</Label>
                <Skeleton className="h-20 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>学歴</Label>
                <Skeleton className="h-20 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>自己PR</Label>
                <Skeleton className="h-20 w-full" />
              </div>
            </div>
          ) : !hasParsed ? (
            <p className="text-sm text-muted-foreground">
              「解析する」を実行すると、ここに編集フォームが表示されます。
            </p>
          ) : (
            <>
              {/* 求人セレクター */}
              {jobSelectorElement}

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="name">氏名</Label>
                <Input
                  id="name"
                  value={form.name ?? ""}
                  onChange={(e) =>
                    patch("name", e.target.value === "" ? null : e.target.value)
                  }
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="age">年齢（歳）</Label>
                  <NumberField
                    id="age"
                    value={form.age}
                    onChange={(next) => patch("age", next)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="experience-years">経験年数（年）</Label>
                  <NumberField
                    id="experience-years"
                    value={form.experience_years}
                    onChange={(next) => patch("experience_years", next)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="desired-rate">希望単価（万円/月）</Label>
                  <NumberField
                    id="desired-rate"
                    value={form.desired_rate}
                    onChange={(next) => patch("desired_rate", next)}
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="nearest-station">最寄り駅</Label>
                <Input
                  id="nearest-station"
                  value={form.nearest_station ?? ""}
                  onChange={(e) =>
                    patch(
                      "nearest_station",
                      e.target.value === "" ? null : e.target.value,
                    )
                  }
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="skills">スキル</Label>
                <TagInput
                  id="skills"
                  value={form.skills}
                  onChange={(next) => patch("skills", next)}
                  placeholder="Enter またはカンマで追加"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="certifications">資格・学位</Label>
                <TagInput
                  id="certifications"
                  value={form.certifications}
                  onChange={(next) => patch("certifications", next)}
                  placeholder="Enter またはカンマで追加"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="work-history">職歴</Label>
                <Textarea
                  id="work-history"
                  value={form.work_history ?? ""}
                  onChange={(e) =>
                    patch(
                      "work_history",
                      e.target.value === "" ? null : e.target.value,
                    )
                  }
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="education">学歴</Label>
                <Textarea
                  id="education"
                  value={form.education ?? ""}
                  onChange={(e) =>
                    patch(
                      "education",
                      e.target.value === "" ? null : e.target.value,
                    )
                  }
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="self-pr">自己PR</Label>
                <Textarea
                  id="self-pr"
                  value={form.self_pr ?? ""}
                  onChange={(e) =>
                    patch(
                      "self_pr",
                      e.target.value === "" ? null : e.target.value,
                    )
                  }
                />
              </div>

              <div className="flex items-center gap-3">
                <Button
                  type="button"
                  onClick={() => createMutation.mutate()}
                  disabled={isSaveDisabled}
                >
                  {createMutation.isPending ? "保存中..." : "保存する"}
                </Button>
                {createMutation.isError && (
                  <p role="alert" className="text-sm text-destructive">
                    保存に失敗しました。再試行してください。
                  </p>
                )}
              </div>
            </>
          )}

          {saveSuccess && (
            <div className="flex flex-col gap-2">
              <p role="status" className="text-sm text-green-600">
                候補者を保存しました。
              </p>
              {savedJobId !== null && (
                <Button
                  render={<Link href={`/jobs/${savedJobId}/rankings`} />}
                  nativeButton={false}
                  variant="outline"
                  className="w-fit"
                >
                  ランキングを見る
                </Button>
              )}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
