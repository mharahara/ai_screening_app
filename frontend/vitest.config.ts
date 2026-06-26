import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * frontend のテスト設定。
 *
 * - 環境は jsdom（React のレンダリングを扱うため）。
 * - `@/` エイリアスを tsconfig と同じくプロジェクトルートに解決する。
 * - setup ファイルで jest-dom と MSW server を有効化する。
 * - `@vitejs/plugin-react` で JSX/TSX を変換し、React コンポーネントの
 *   描画テスト（@testing-library/react）を可能にする。
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "."),
    },
  },
});
