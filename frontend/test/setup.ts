import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./server";

// MSW server を全テストで起動し、各テスト後にハンドラをリセットする。
// 未モックのリクエストはエラーにして、モック漏れを検知する。
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
