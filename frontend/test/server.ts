import { setupServer } from "msw/node";

/**
 * テスト用の MSW server。
 *
 * 既定のハンドラは空。各テストで `server.use(...)` を使って
 * その場のレスポンスを定義する（fetch をネットワーク層でモックする）。
 */
export const server = setupServer();
