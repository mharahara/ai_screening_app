"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "/jobs/new", label: "求人取り込み" },
  { href: "/candidates/new", label: "候補者取り込み" },
] as const;

export function GlobalHeader() {
  const pathname = usePathname();

  return (
    <header className="border-b border-border bg-background">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-6">
        {/* 左: サイト名 */}
        <Link
          href="/"
          className="text-lg font-bold tracking-tight text-foreground hover:opacity-80 transition-opacity"
        >
          RabbitPick
        </Link>

        {/* 右: ナビリンク */}
        <nav aria-label="グローバルナビゲーション">
          <ul className="flex items-center gap-6">
            {NAV_LINKS.map(({ href, label }) => {
              const isActive = pathname === href;
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={isActive ? "page" : undefined}
                    className={cn(
                      "text-sm transition-colors hover:text-foreground",
                      isActive
                        ? "border-b-2 border-current font-medium text-foreground pb-0.5"
                        : "text-muted-foreground",
                    )}
                  >
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
