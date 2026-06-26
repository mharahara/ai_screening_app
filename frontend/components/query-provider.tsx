"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * App Router 用の TanStack Query Provider ラッパ。
 *
 * QueryClient はリクエストごとに共有されないよう useState 内で生成し、
 * クライアント側で一度だけインスタンス化する。
 * スコア算出完了のポーリング等は各画面の useQuery 側で refetchInterval を設定する。
 */
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // 画面復帰のたびに過剰に再取得しないための既定値。
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
