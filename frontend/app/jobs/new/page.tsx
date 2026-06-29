"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2Icon } from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  createJob,
  deleteJob,
  listJobs,
  parseJob,
  EMPLOYMENT_TYPES,
  REMOTE_WORKS,
  POSITION_LEVELS,
  type EmploymentType,
  type JobParseResult,
  type JobParseResponse,
  type PositionLevel,
  type RemoteWork,
} from "@/lib/jobs";
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

const JOBS_QUERY_KEY = ["jobs"] as const;

/** parse の空フォーム初期値。 */
const EMPTY_FORM: JobParseResult = {
  title: null,
  description: null,
  required_skills: [],
  preferred_skills: [],
  ideal_profile: null,
  employment_type: null,
  location: null,
  remote_work: null,
  rate_min: null,
  rate_max: null,
  min_experience_years: null,
  position_level: null,
  industry_experience: null,
  certifications: [],
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

/** 未選択（null）を表す番兵値。enum 値とは衝突しない文字列にする。 */
const NONE_VALUE = "__none__";

/** null 許容の enum Select。未選択（null）を選べる。 */
function EnumSelect<T extends string>({
  id,
  value,
  options,
  placeholder,
  onChange,
}: {
  id: string;
  value: T | null;
  options: readonly T[];
  placeholder: string;
  onChange: (next: T | null) => void;
}) {
  return (
    <Select
      value={value ?? NONE_VALUE}
      onValueChange={(next) =>
        onChange(next === NONE_VALUE || next == null ? null : (next as T))
      }
    >
      <SelectTrigger id={id} className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE_VALUE}>（未選択）</SelectItem>
        {options.map((opt) => (
          <SelectItem key={opt} value={opt}>
            {opt}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

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

export default function JobNewPage() {
  const queryClient = useQueryClient();

  const [rawText, setRawText] = React.useState("");
  // parse 時に受け取った原文。保存（createJob）でそのまま送る。
  const [savedRawText, setSavedRawText] = React.useState("");
  const [form, setForm] = React.useState<JobParseResult>(EMPTY_FORM);
  const [hasParsed, setHasParsed] = React.useState(false);
  const [saveSuccess, setSaveSuccess] = React.useState(false);

  function patch<K extends keyof JobParseResult>(
    key: K,
    val: JobParseResult[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: val }));
    setSaveSuccess(false);
  }

  const parseMutation = useMutation({
    mutationFn: (text: string) => parseJob(text),
    onSuccess: (data: JobParseResponse) => {
      const { raw_text, ...rest } = data;
      setForm(rest);
      setSavedRawText(raw_text);
      setHasParsed(true);
      setSaveSuccess(false);
    },
  });

  const createMutation = useMutation({
    mutationFn: () => createJob({ ...form, raw_text: savedRawText }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: JOBS_QUERY_KEY });
      // フォームをクリアして次の入力に備える。
      setForm(EMPTY_FORM);
      setRawText("");
      setSavedRawText("");
      setHasParsed(false);
      setSaveSuccess(true);
    },
  });

  const jobsQuery = useQuery({
    queryKey: JOBS_QUERY_KEY,
    queryFn: listJobs,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteJob(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: JOBS_QUERY_KEY });
    },
  });

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">
          求人要件の取り込み
        </h1>
        <p className="text-sm text-muted-foreground">
          求人票の生テキストを構造化し、編集して保存します。
        </p>
      </header>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 左: 生テキスト入力 */}
        <div className="flex flex-col gap-3">
          <Label htmlFor="raw-text">求人票テキスト</Label>
          <Textarea
            id="raw-text"
            className="min-h-72"
            placeholder="求人票の本文を貼り付けてください。"
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
          />
          <div className="flex items-center gap-3">
            <Button
              type="button"
              onClick={() => parseMutation.mutate(rawText)}
              disabled={rawText.trim() === "" || parseMutation.isPending}
            >
              {parseMutation.isPending ? "構造化中..." : "構造化する"}
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
              <div className="flex flex-col gap-1.5">
                <Label>タイトル</Label>
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>業務内容</Label>
                <Skeleton className="h-20 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>必須スキル</Label>
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>歓迎スキル</Label>
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>資格要件</Label>
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>求める人物像</Label>
                <Skeleton className="h-20 w-full" />
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <Label>雇用形態</Label>
                  <Skeleton className="h-9 w-full" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>リモート可否</Label>
                  <Skeleton className="h-9 w-full" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>ポジションレベル</Label>
                  <Skeleton className="h-9 w-full" />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <Label>単価下限（万円/月）</Label>
                  <Skeleton className="h-9 w-full" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>単価上限（万円/月）</Label>
                  <Skeleton className="h-9 w-full" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>最低経験年数（年）</Label>
                  <Skeleton className="h-9 w-full" />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>勤務地</Label>
                <Skeleton className="h-9 w-full" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>求める業界経験</Label>
                <Skeleton className="h-9 w-full" />
              </div>
            </div>
          ) : !hasParsed ? (
            <p className="text-sm text-muted-foreground">
              「構造化する」を実行すると、ここに編集フォームが表示されます。
            </p>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="title">タイトル</Label>
                <Input
                  id="title"
                  value={form.title ?? ""}
                  onChange={(e) =>
                    patch(
                      "title",
                      e.target.value === "" ? null : e.target.value,
                    )
                  }
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="description">業務内容</Label>
                <Textarea
                  id="description"
                  value={form.description ?? ""}
                  onChange={(e) =>
                    patch(
                      "description",
                      e.target.value === "" ? null : e.target.value,
                    )
                  }
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="required-skills">必須スキル</Label>
                <TagInput
                  id="required-skills"
                  value={form.required_skills}
                  onChange={(next) => patch("required_skills", next)}
                  placeholder="Enter またはカンマで追加"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="preferred-skills">歓迎スキル</Label>
                <TagInput
                  id="preferred-skills"
                  value={form.preferred_skills}
                  onChange={(next) => patch("preferred_skills", next)}
                  placeholder="Enter またはカンマで追加"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="certifications">資格要件</Label>
                <TagInput
                  id="certifications"
                  value={form.certifications}
                  onChange={(next) => patch("certifications", next)}
                  placeholder="Enter またはカンマで追加"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="ideal-profile">求める人物像</Label>
                <Textarea
                  id="ideal-profile"
                  value={form.ideal_profile ?? ""}
                  onChange={(e) =>
                    patch(
                      "ideal_profile",
                      e.target.value === "" ? null : e.target.value,
                    )
                  }
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="employment-type">雇用形態</Label>
                  <EnumSelect<EmploymentType>
                    id="employment-type"
                    value={form.employment_type}
                    options={EMPLOYMENT_TYPES}
                    placeholder="未選択"
                    onChange={(next) => patch("employment_type", next)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="remote-work">リモート可否</Label>
                  <EnumSelect<RemoteWork>
                    id="remote-work"
                    value={form.remote_work}
                    options={REMOTE_WORKS}
                    placeholder="未選択"
                    onChange={(next) => patch("remote_work", next)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="position-level">ポジションレベル</Label>
                  <EnumSelect<PositionLevel>
                    id="position-level"
                    value={form.position_level}
                    options={POSITION_LEVELS}
                    placeholder="未選択"
                    onChange={(next) => patch("position_level", next)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="rate-min">単価下限（万円/月）</Label>
                  <NumberField
                    id="rate-min"
                    value={form.rate_min}
                    onChange={(next) => patch("rate_min", next)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="rate-max">単価上限（万円/月）</Label>
                  <NumberField
                    id="rate-max"
                    value={form.rate_max}
                    onChange={(next) => patch("rate_max", next)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="min-experience-years">
                    最低経験年数（年）
                  </Label>
                  <NumberField
                    id="min-experience-years"
                    value={form.min_experience_years}
                    onChange={(next) => patch("min_experience_years", next)}
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="location">勤務地</Label>
                <Input
                  id="location"
                  value={form.location ?? ""}
                  onChange={(e) =>
                    patch(
                      "location",
                      e.target.value === "" ? null : e.target.value,
                    )
                  }
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="industry-experience">求める業界経験</Label>
                <Input
                  id="industry-experience"
                  value={form.industry_experience ?? ""}
                  onChange={(e) =>
                    patch(
                      "industry_experience",
                      e.target.value === "" ? null : e.target.value,
                    )
                  }
                />
              </div>

              <div className="flex items-center gap-3">
                <Button
                  type="button"
                  onClick={() => createMutation.mutate()}
                  disabled={createMutation.isPending}
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
            <p role="status" className="text-sm text-green-600">
              求人を保存しました。
            </p>
          )}
        </div>
      </section>

      {/* 保存済み求人一覧 */}
      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">保存済みの求人</h2>
        {jobsQuery.isPending ? (
          <p className="text-sm text-muted-foreground">読み込み中...</p>
        ) : jobsQuery.isError ? (
          <p className="text-sm text-destructive">
            求人一覧の取得に失敗しました。
          </p>
        ) : jobsQuery.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            保存済みの求人はありません。
          </p>
        ) : (
          <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
            {jobsQuery.data.map((job) => (
              <li
                key={job.id}
                className="flex items-center justify-between gap-4 px-4 py-3"
              >
                <div className="flex min-w-0 flex-col">
                  <span className="truncate font-medium">
                    {job.title ?? "（無題）"}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    #{job.id} ・{" "}
                    {new Date(job.created_at).toLocaleString("ja-JP")}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    render={<Link href={`/jobs/${job.id}/rankings`} />}
                    nativeButton={false}
                    variant="outline"
                    size="sm"
                  >
                    ランキング
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger
                      render={
                        <Button variant="destructive" size="sm">
                          <Trash2Icon />
                          削除
                        </Button>
                      }
                    />
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>求人を削除しますか？</AlertDialogTitle>
                        <AlertDialogDescription>
                          「{job.title ?? "（無題）"}
                          」を削除します。この操作は取り消せません。
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>キャンセル</AlertDialogCancel>
                        <AlertDialogAction
                          variant="destructive"
                          onClick={() => deleteMutation.mutate(job.id)}
                        >
                          削除する
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </li>
            ))}
          </ul>
        )}
        {deleteMutation.isError && (
          <p role="alert" className="text-sm text-destructive">
            削除に失敗しました。再試行してください。
          </p>
        )}
      </section>
    </main>
  );
}
