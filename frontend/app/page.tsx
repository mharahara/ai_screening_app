import Link from "next/link";
import { Briefcase, User } from "lucide-react";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 p-8 text-center">
      <div className="flex flex-col items-center gap-2">
        <h1 className="text-4xl font-bold tracking-tight">RabbitPick</h1>
        <p className="text-muted-foreground">
          AIエンジニア採用スクリーニングシステム
        </p>
      </div>
      <div className="flex flex-col gap-4 sm:flex-row">
        <Link
          href="/jobs/new"
          className="flex flex-col items-center gap-3 rounded-lg border p-6 text-left hover:bg-muted/50 transition-colors w-60"
        >
          <Briefcase className="h-8 w-8 text-muted-foreground" />
          <div className="flex flex-col gap-1">
            <span className="font-semibold">求人取り込み</span>
            <span className="text-sm text-muted-foreground">
              求人票を貼り付けてAIで構造化・保存する
            </span>
          </div>
        </Link>
        <Link
          href="/candidates/new"
          className="flex flex-col items-center gap-3 rounded-lg border p-6 text-left hover:bg-muted/50 transition-colors w-60"
        >
          <User className="h-8 w-8 text-muted-foreground" />
          <div className="flex flex-col gap-1">
            <span className="font-semibold">候補者取り込み</span>
            <span className="text-sm text-muted-foreground">
              応募書類を貼り付けてAIで構造化・保存する
            </span>
          </div>
        </Link>
      </div>
    </main>
  );
}
