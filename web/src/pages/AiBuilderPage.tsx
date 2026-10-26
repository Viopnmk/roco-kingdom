import { useState } from "react";
import type { OptimizeRequest, OptimizeResult, OptimizeResponse } from "../types/api";
import { optimizeLocal } from "../engine/client";
import ConstraintPanel, { Constraints, defaultConstraints } from "../components/ConstraintPanel";
import { pets, skills } from "../data";
import TeamCard from "../components/TeamCard";

type SearchState = "idle" | "loading" | "done" | "error";

export default function AiBuilderPage() {
  const [constraints, setConstraints] = useState<Constraints>(defaultConstraints);
  const [results, setResults] = useState<OptimizeResult[]>([]);
  const [state, setState] = useState<SearchState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleSearch = async () => {
    setState("loading");
    setErrorMsg("");
    setResults([]);

    const body: OptimizeRequest = {
      top_k: constraints.top_k,
      pop_size: constraints.pop_size,
      generations: constraints.generations,
    };
    if (constraints.must_include.length > 0) {
      body.must_include = constraints.must_include;
    }
    if (constraints.must_exclude.length > 0) {
      body.must_exclude = constraints.must_exclude;
    }
    if (constraints.prefer_type) {
      body.prefer_type = constraints.prefer_type;
    }
    if (constraints.style) {
      body.style = constraints.style;
    }
    if (constraints.team_type) {
      body.team_type = constraints.team_type;
    }

    try {
      // 本地引擎：在浏览器内运行遗传算法，无需后端服务器
      const data: OptimizeResponse = await optimizeLocal(body);
      setResults(data.teams);
      setState("done");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "搜索失败");
      setState("error");
    }
  };

  return (
    <div className="ai-builder">
      <h2 className="ai-title">AI 配队助手</h2>
      <p className="ai-subtitle">
        基于多目标遗传算法（NSGA-II），搜索最优 6 精灵配队。支持约束条件过滤。算法已内置于网页，在你的设备上本地计算，无需服务器。
      </p>

      <div className="ai-layout">
        {/* 左侧约束面板 */}
        <aside className="ai-sidebar">
          <ConstraintPanel
            constraints={constraints}
            onChange={setConstraints}
            onSearch={handleSearch}
            loading={state === "loading"}
          />
        </aside>

        {/* 右侧结果区 */}
        <main className="ai-main">
          {/* 加载态 */}
          {state === "loading" && (
            <div className="ai-loading">
              <div className="ai-spinner" />
              <p className="ai-loading-text">正在搜索最优配队...</p>
              <p className="ai-loading-hint">
                种群 {constraints.pop_size} × 代数 {constraints.generations}，预计需要 10–60 秒
              </p>
            </div>
          )}

          {/* 错误态 */}
          {state === "error" && (
            <div className="ai-error">
              <h3>搜索出错</h3>
              <p>{errorMsg}</p>
              <button
                className="btn btn-primary"
                onClick={handleSearch}
                style={{ marginTop: 16 }}
              >
                重试
              </button>
            </div>
          )}

          {/* 空结果 */}
          {state === "done" && results.length === 0 && (
            <div className="empty-state">
              <h3>未找到符合条件的队伍</h3>
              <p>试试放宽约束条件，或减少必须包含的精灵数量。</p>
            </div>
          )}

          {/* 结果列表 */}
          {state === "done" && results.length > 0 && (
            <div className="ai-results">
              <p className="ai-results-summary">
                找到 {results.length} 支队伍
              </p>
              <div className="ai-teams">
                {results.map((r, i) => (
                  <TeamCard key={i} result={r} rank={i + 1} />
                ))}
              </div>
            </div>
          )}

          {/* 初始态 */}
          {state === "idle" && (
            <div className="ai-idle">
              <p className="ai-idle-icon">🧬</p>
              <p className="ai-idle-text">设置约束条件后点击搜索</p>
              <p className="ai-idle-hint">
                遗传算法将自动在 {pets.length} 只精灵 × {skills.length} 个技能中搜索最优组合
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
