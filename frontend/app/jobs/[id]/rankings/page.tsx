"use client";

import * as React from "react";
import { useParams, notFound } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";
import {
  getCandidateDetail,
  listRankings,
  type CandidateDetailOut,
  type CandidateRankingItem,
  type RequirementCheck,
} from "@/lib/rankings";
import { getJob, type JobOut } from "@/lib/jobs";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabList, Tab, TabPanel } from "@/components/ui/tabs";

/** スコア未算出の候補者がいる間のポーリング間隔（ms）。 */
const POLL_INTERVAL = 3000;

/** スコア未算出（total_score === null）の候補者が1件以上あるか。 */
function hasPendingScore(items: CandidateRankingItem[]): boolean {
  return items.some((item) => item.total_score === null);
}

export default function JobRankingsPage() {
  const params = useParams<{ id: string }>();
  const jobId = Number(params.id);

  const [detailCandidateId, setDetailCandidateId] = React.useState<
    number | null
  >(null);

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId),
    enabled: Number.isFinite(jobId),
  });

  const rankingsQuery = useQuery({
    queryKey: ["rankings", jobId],
    queryFn: () => listRankings(jobId),
    enabled: Number.isFinite(jobId),
    // スコア未算出の候補者がいる間だけポーリングし、全員確定したら止める。
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && hasPendingScore(data)) {
        return POLL_INTERVAL;
      }
      return false;
    },
  });

  // 求人が存在しない（404）場合は Next.js の not-found を表示する。
  if (
    rankingsQuery.isError &&
    rankingsQuery.error instanceof ApiError &&
    rankingsQuery.error.status === 404
  ) {
    notFound();
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">候補者ランキング</h1>
        {jobQuery.isSuccess && (
          <p className="text-base font-medium">
            {jobQuery.data.title ?? "（無題）"}
          </p>
        )}
        <p className="text-sm text-muted-foreground">
          スコア降順で候補者を表示します。スコア算出中の候補者は自動で更新されます。
        </p>
      </header>

      {jobQuery.isSuccess && <JobDetailsPanel job={jobQuery.data} />}

      {rankingsQuery.isPending ? (
        <p className="text-sm text-muted-foreground">読み込み中...</p>
      ) : rankingsQuery.isError ? (
        <p role="alert" className="text-sm text-destructive">
          ランキングの取得に失敗しました。
        </p>
      ) : rankingsQuery.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          この求人に紐づく候補者はまだいません。
        </p>
      ) : (
        <RankingsTable
          items={rankingsQuery.data}
          onShowDetail={(candidateId) => setDetailCandidateId(candidateId)}
        />
      )}

      <CandidateDetailDialog
        candidateId={detailCandidateId}
        onClose={() => setDetailCandidateId(null)}
      />
    </main>
  );
}

/** 求人要件確認パネル（折りたたみ可能・読み取り専用）。 */
function JobDetailsPanel({ job }: { job: JobOut }) {
  const [open, setOpen] = React.useState(false);
  const [rawOpen, setRawOpen] = React.useState(false);

  return (
    <div className="rounded-lg border">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium hover:bg-muted/30"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>求人要件を確認する</span>
        <span className="text-muted-foreground">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t px-4 py-4">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            <JobField label="タイトル" value={job.title} className="sm:col-span-2" />
            <JobField label="説明" value={job.description} className="sm:col-span-2" />
            <JobTagField label="必須スキル" values={job.required_skills} className="sm:col-span-2" />
            <JobTagField label="歓迎スキル" values={job.preferred_skills} className="sm:col-span-2" />
            <JobField label="理想の人物像" value={job.ideal_profile} className="sm:col-span-2" />
            <JobField label="雇用形態" value={job.employment_type} />
            <JobField label="勤務地" value={job.location} />
            <JobField label="リモート" value={job.remote_work} />
            <JobField
              label="単価（最低）"
              value={job.rate_min !== null ? `${job.rate_min} 万円/月` : null}
            />
            <JobField
              label="単価（最高）"
              value={job.rate_max !== null ? `${job.rate_max} 万円/月` : null}
            />
            <JobField
              label="最低経験年数"
              value={job.min_experience_years !== null ? `${job.min_experience_years} 年` : null}
            />
            <JobField label="ポジションレベル" value={job.position_level} />
            <JobField label="業界経験" value={job.industry_experience} />
            <JobTagField label="資格" values={job.certifications} className="sm:col-span-2" />
          </dl>

          <div className="mt-4">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRawOpen(true)}
            >
              原文を見る
            </Button>
          </div>
        </div>
      )}

      <Dialog open={rawOpen} onOpenChange={(o) => { if (!o) setRawOpen(false); }}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>求人票 原文</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <pre className="rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">
              {job.raw_text}
            </pre>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** 求人フィールド（単一値）。null は「未記載」表示。 */
function JobField({
  label,
  value,
  className,
}: {
  label: string;
  value: string | null | undefined;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">
        {value != null ? value : <span className="text-muted-foreground">未記載</span>}
      </dd>
    </div>
  );
}

/** 求人フィールド（タグ配列）。空配列・null は「未記載」表示。 */
function JobTagField({
  label,
  values,
  className,
}: {
  label: string;
  values: string[] | null | undefined;
  className?: string;
}) {
  const safeValues = values ?? [];
  return (
    <div className={className}>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 flex flex-wrap gap-1.5">
        {safeValues.length === 0 ? (
          <span className="text-sm text-muted-foreground">未記載</span>
        ) : (
          safeValues.map((value) => (
            <span
              key={value}
              className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs"
            >
              {value}
            </span>
          ))
        )}
      </dd>
    </div>
  );
}

/** ランキング一覧テーブル。 */
function RankingsTable({
  items,
  onShowDetail,
}: {
  items: CandidateRankingItem[];
  onShowDetail: (candidateId: number) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b bg-muted/50 text-left text-muted-foreground">
            <th className="px-3 py-2 font-medium">氏名</th>
            <th className="px-3 py-2 text-right font-medium">総合</th>
            <th className="px-3 py-2 text-right font-medium">スキル</th>
            <th className="px-3 py-2 text-right font-medium">経験</th>
            <th className="px-3 py-2 text-right font-medium">業界</th>
            <th className="px-3 py-2 text-right font-medium">ポジション</th>
            <th className="px-3 py-2 text-right font-medium">必須充足</th>
            <th className="px-3 py-2 font-medium" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const pending = item.total_score === null;
            return (
              <tr
                key={item.candidate_id}
                className="border-b last:border-b-0 hover:bg-muted/30"
              >
                <td className="px-3 py-2">{item.name ?? "（氏名不明）"}</td>
                {pending ? (
                  <td
                    colSpan={6}
                    className="px-3 py-2 text-muted-foreground"
                  >
                    算出中...
                  </td>
                ) : (
                  <>
                    <td className="px-3 py-2 text-right font-semibold tabular-nums">
                      {item.total_score}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {item.skill_score}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {item.experience_score}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {item.industry_score}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {item.position_score}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {item.required_met} / {item.required_total}
                    </td>
                  </>
                )}
                <td className="px-3 py-2 text-right">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={pending}
                    onClick={() => onShowDetail(item.candidate_id)}
                  >
                    詳細
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** 候補者詳細ダイアログ。candidateId が null のとき閉じる。 */
function CandidateDetailDialog({
  candidateId,
  onClose,
}: {
  candidateId: number | null;
  onClose: () => void;
}) {
  const detailQuery = useQuery({
    queryKey: ["candidate-detail", candidateId],
    queryFn: () => getCandidateDetail(candidateId as number),
    enabled: candidateId !== null,
  });

  return (
    <Dialog
      open={candidateId !== null}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {detailQuery.data?.name ?? "候補者詳細"}
          </DialogTitle>
        </DialogHeader>
        <DialogBody>
          {detailQuery.isPending ? (
            <p className="text-sm text-muted-foreground">読み込み中...</p>
          ) : detailQuery.isError ? (
            <p role="alert" className="text-sm text-destructive">
              候補者詳細の取得に失敗しました。
            </p>
          ) : (
            <DetailTabs detail={detailQuery.data} />
          )}
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}

/** 詳細ダイアログのタブ本体。 */
function DetailTabs({ detail }: { detail: CandidateDetailOut }) {
  const { score } = detail;

  return (
    <Tabs defaultValue="profile">
      <TabList>
        <Tab value="profile">基本プロフィール</Tab>
        <Tab value="score">スコア根拠</Tab>
        <Tab value="summary">AIサマリー</Tab>
        <Tab value="raw">応募書類</Tab>
      </TabList>

      <TabPanel value="profile">
        <ProfilePanel detail={detail} />
      </TabPanel>

      <TabPanel value="score">
        {score === null ? (
          <p className="text-sm text-muted-foreground">スコア算出中です。</p>
        ) : (
          <RequirementCheckList checks={score.requirement_checks} />
        )}
      </TabPanel>

      <TabPanel value="summary">
        {score === null ? (
          <p className="text-sm text-muted-foreground">スコア算出中です。</p>
        ) : (
          <SummaryPanel
            strengths={score.strengths}
            concerns={score.concerns}
            interviewPoints={score.interview_points}
          />
        )}
      </TabPanel>

      <TabPanel value="raw">
        <pre className="rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">
          {detail.raw_text}
        </pre>
      </TabPanel>
    </Tabs>
  );
}

/** 基本プロフィールパネル。 */
function ProfilePanel({ detail }: { detail: CandidateDetailOut }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      <Field label="氏名" value={detail.name} />
      <Field
        label="年齢"
        value={detail.age !== null ? `${detail.age} 歳` : null}
      />
      <Field label="最寄り駅" value={detail.nearest_station} />
      <Field
        label="希望単価"
        value={
          detail.desired_rate !== null ? `${detail.desired_rate} 万円/月` : null
        }
      />
      <Field
        label="経験年数"
        value={
          detail.experience_years !== null
            ? `${detail.experience_years} 年`
            : null
        }
      />
      <Field label="学歴" value={detail.education} />
      <TagField label="スキル" values={detail.skills} className="sm:col-span-2" />
      <TagField
        label="資格"
        values={detail.certifications}
        className="sm:col-span-2"
      />
    </dl>
  );
}

/** 単一値フィールド。null は「未登録」表示。 */
function Field({
  label,
  value,
  className,
}: {
  label: string;
  value: string | null;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">
        {value ?? <span className="text-muted-foreground">未登録</span>}
      </dd>
    </div>
  );
}

/** タグ配列フィールド。空配列は「未登録」表示。 */
function TagField({
  label,
  values,
  className,
}: {
  label: string;
  values: string[];
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 flex flex-wrap gap-1.5">
        {values.length === 0 ? (
          <span className="text-sm text-muted-foreground">未登録</span>
        ) : (
          values.map((value) => (
            <span
              key={value}
              className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs"
            >
              {value}
            </span>
          ))
        )}
      </dd>
    </div>
  );
}

/** 必須要件チェック一覧。 */
function RequirementCheckList({ checks }: { checks: RequirementCheck[] }) {
  if (checks.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">必須要件はありません。</p>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {checks.map((check, index) => (
        <li
          key={`${check.requirement}-${index}`}
          className="flex flex-col gap-1 rounded-md border p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium">{check.requirement}</span>
            <StatusBadge status={check.status} />
          </div>
          {check.evidence !== null && (
            <p className="text-xs text-muted-foreground">{check.evidence}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

/** 充足 / 未充足のカラーバッジ。 */
function StatusBadge({ status }: { status: RequirementCheck["status"] }) {
  const met = status === "充足";
  return (
    <span
      className={
        met
          ? "inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/40 dark:text-green-300"
          : "inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/40 dark:text-red-300"
      }
    >
      {status}
    </span>
  );
}

/** AIサマリーパネル。 */
function SummaryPanel({
  strengths,
  concerns,
  interviewPoints,
}: {
  strengths: string;
  concerns: string;
  interviewPoints: string;
}) {
  return (
    <div className="flex flex-col gap-4">
      <SummarySection title="強み" body={strengths} />
      <SummarySection title="懸念点" body={concerns} />
      <SummarySection title="面接での確認事項" body={interviewPoints} />
    </div>
  );
}

function SummarySection({ title, body }: { title: string; body: string }) {
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-sm font-medium">{title}</h3>
      <p className="text-sm whitespace-pre-wrap text-muted-foreground">
        {body}
      </p>
    </section>
  );
}
