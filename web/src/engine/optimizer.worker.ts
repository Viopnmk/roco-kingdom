/**
 * 配队引擎 Web Worker — 在后台线程运行遗传搜索，避免冻结页面。
 * 数据包（team-data.json）只随本 worker 分块加载，打开 AI 配队页前不下载。
 */
import { optimizeTeams } from "./optimizer";
import type { TeamData, OptimizeRequestLike } from "./optimizer";
import rawData from "./team-data.json";

const data = rawData as unknown as TeamData;

(self as unknown as {
  onmessage: ((e: MessageEvent) => void) | null;
  postMessage: (msg: unknown) => void;
}).onmessage = (e: MessageEvent) => {
  try {
    const teams = optimizeTeams(data, e.data as OptimizeRequestLike);
    (self as unknown as { postMessage: (msg: unknown) => void }).postMessage({ ok: true, teams });
  } catch (err) {
    (self as unknown as { postMessage: (msg: unknown) => void }).postMessage({
      ok: false,
      error: err instanceof Error ? err.message : String(err),
    });
  }
};
