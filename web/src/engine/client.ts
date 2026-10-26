/**
 * 本地配队搜索入口 — 优先在 Web Worker 中运行，失败时回退主线程。
 * 返回结构与原 FastAPI /api/optimize 完全一致，页面层无需区分。
 */
import type { OptimizeRequest, OptimizeResponse, OptimizeResult } from "../types/api";

function runInWorker(body: OptimizeRequest): Promise<OptimizeResult[]> {
  return new Promise((resolve, reject) => {
    let worker: Worker;
    try {
      worker = new Worker(new URL("./optimizer.worker.ts", import.meta.url), {
        type: "module",
      });
    } catch (e) {
      reject(e);
      return;
    }
    const timer = setTimeout(() => {
      worker.terminate();
      reject(new Error("搜索超时（2分钟），请减少代数或种群大小后重试"));
    }, 115_000);
    worker.onmessage = (e: MessageEvent) => {
      clearTimeout(timer);
      worker.terminate();
      const msg = e.data as { ok: boolean; teams?: OptimizeResult[]; error?: string };
      if (msg.ok && msg.teams) resolve(msg.teams);
      else reject(new Error(msg.error ?? "本地引擎返回异常"));
    };
    worker.onerror = (e) => {
      clearTimeout(timer);
      worker.terminate();
      reject(new Error(e.message || "Worker 启动失败"));
    };
    worker.postMessage(body);
  });
}

export async function optimizeLocal(body: OptimizeRequest): Promise<OptimizeResponse> {
  const generations = body.generations ?? 100;
  const pop_size = body.pop_size ?? 100;
  try {
    const teams = await runInWorker(body);
    return { teams, generations, pop_size };
  } catch (workerErr) {
    // 回退：主线程直接计算（较慢但可用）
    try {
      const [{ optimizeTeams }, dataMod] = await Promise.all([
        import("./optimizer"),
        import("./team-data.json"),
      ]);
      const teams = optimizeTeams(
        dataMod.default as unknown as Parameters<typeof optimizeTeams>[0],
        body,
      );
      return { teams, generations, pop_size };
    } catch {
      throw workerErr;
    }
  }
}
