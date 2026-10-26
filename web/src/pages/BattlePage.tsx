import { useEffect, useMemo, useRef, useState } from "react";
import teamDataRaw from "../engine/team-data.json";
import battleDataRaw from "../engine/battle-data.json";
import type { TeamData, ProfileData } from "../engine/optimizer";
import { optimizeLocal } from "../engine/client";
import { simulate } from "../battle/engine";
import type { BattlePetInput, BattleResult, SkillData } from "../battle/engine";
import { typeChart } from "../data";

const teamData = teamDataRaw as unknown as TeamData;
const battleData = battleDataRaw as unknown as Record<string, SkillData>;
const chart = (typeChart as { chart: Record<string, Record<string, number>> }).chart;

function toBattlePet(id: number): BattlePetInput {
  const p: ProfileData = teamData.profiles[String(id)];
  return {
    id, name: p.name, tp: p.tp, ts: p.ts,
    hp: p.hp, atk: p.atk, def: p.def, spa: p.spa, spd: p.spd, spe: p.spe,
    skills: (p.bs ?? p.skills).slice(0, 4),
  };
}

function TeamPicker({
  side, label, team, setTeam,
}: {
  side: string; label: string; team: number[]; setTeam: (t: number[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const matches = useMemo(() => {
    const q = query.trim();
    if (!q) return [];
    return Object.entries(teamData.profiles)
      .filter(([, p]) => p.name.includes(q))
      .slice(0, 10)
      .map(([id]) => Number(id));
  }, [query]);

  const add = (id: number) => {
    if (team.length < 6 && !team.includes(id)) setTeam([...team, id]);
    setQuery("");
  };
  const randomTeam = () => {
    const pool = [...teamData.pet_ids];
    const picked: number[] = [];
    while (picked.length < 6) {
      const id = pool[Math.floor(Math.random() * pool.length)];
      if (!picked.includes(id)) picked.push(id);
    }
    setTeam(picked);
  };
  const aiTeam = async () => {
    setBusy(true);
    try {
      const res = await optimizeLocal({ top_k: 1 });
      if (res.teams[0]) setTeam(res.teams[0].team.map((m) => m.pet_id));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="battle-picker">
      <h3>{label}</h3>
      <div className="battle-slots">
        {team.map((id) => {
          const p = teamData.profiles[String(id)];
          return (
            <span key={id} className="battle-slot">
              {p.name}
              <button onClick={() => setTeam(team.filter((x) => x !== id))} aria-label="移除">×</button>
            </span>
          );
        })}
        {team.length === 0 && <span className="battle-slot-empty">尚未选择精灵</span>}
      </div>
      <div className="battle-search">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`搜索精灵名添加到${side}方…`}
        />
        {matches.length > 0 && (
          <div className="battle-matches">
            {matches.map((id) => {
              const p = teamData.profiles[String(id)];
              return (
                <button key={id} onClick={() => add(id)}>
                  {p.name} <span>{p.tp}{p.ts ? `/${p.ts}` : ""} · {p.role}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      <div className="battle-presets">
        <button onClick={randomTeam}>🎲 随机六只</button>
        <button onClick={aiTeam} disabled={busy}>{busy ? "AI 计算中…" : "🤖 AI 最优队"}</button>
        <button onClick={() => setTeam([])}>清空</button>
      </div>
    </div>
  );
}

export default function BattlePage() {
  const [teamA, setTeamA] = useState<number[]>([]);
  const [teamB, setTeamB] = useState<number[]>([]);
  const [result, setResult] = useState<BattleResult | null>(null);
  const [inputs, setInputs] = useState<{ a: BattlePetInput[]; b: BattlePetInput[] } | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const canFight = teamA.length > 0 && teamB.length > 0;

  const start = () => {
    const a = teamA.map(toBattlePet);
    const b = teamB.map(toBattlePet);
    const res = simulate(a, b, battleData, chart);
    setInputs({ a, b });
    setResult(res);
    setStep(0);
    setPlaying(true);
  };

  useEffect(() => {
    if (!playing || !result) return;
    if (step >= result.log.length - 1) { setPlaying(false); return; }
    const t = setTimeout(() => setStep((s) => s + 1), 620);
    return () => clearTimeout(t);
  }, [playing, step, result]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [step]);

  const ev = result?.log[Math.min(step, result.log.length - 1)];
  const finished = result !== null && step >= result.log.length - 1;

  const hpBar = (hp: number, max: number) => {
    const pct = Math.max(0, (hp / max) * 100);
    const color = pct > 50 ? "#66bb6a" : pct > 25 ? "#ffa726" : "#ef5350";
    return (
      <div className="battle-hpbar">
        <div style={{ width: `${pct}%`, background: color }} />
      </div>
    );
  };

  const sidePanel = (side: 0 | 1) => {
    if (!result || !inputs || !ev) return null;
    const ins = side === 0 ? inputs.a : inputs.b;
    const hps = side === 0 ? ev.aHp : ev.bHp;
    const maxs = side === 0 ? result.maxHpA : result.maxHpB;
    const idx = side === 0 ? ev.aIdx : ev.bIdx;
    const en = side === 0 ? ev.aEn : ev.bEn;
    const cur = ins[idx];
    return (
      <div className="battle-side">
        <div className="battle-active-name">
          {side === 0 ? "左方" : "右方"} · {cur.name}
          <span className="meta-tag">{cur.tp}{cur.ts ? `/${cur.ts}` : ""}</span>
        </div>
        {hpBar(hps[idx], maxs[idx])}
        <div className="battle-hp-text">
          HP {hps[idx]} / {maxs[idx]} · 能量 {en}
        </div>
        <div className="battle-bench">
          {ins.map((p, i) => (
            <span key={p.id} className={`battle-bench-dot ${hps[i] <= 0 ? "fainted" : ""} ${i === idx ? "active" : ""}`}>
              {p.name.slice(0, 4)} {hps[i]}/{maxs[i]}
            </span>
          ))}
        </div>
        <div className="battle-moves">
          {cur.skills.map((s) => (
            <span key={s} className="meta-chip">{s}</span>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="battle-page">
      <h2 className="ai-title">配队对战模拟器</h2>
      <p className="ai-subtitle">
        回合制自动对战：双方各选最多 6 只精灵，AI 按简化规则自动选招打完一场。
        粉丝自制模拟，<strong>不是游戏官方战斗机制</strong>，规则见页底说明。
      </p>

      <div className="battle-pickers">
        <TeamPicker side="左" label="🔵 左方队伍" team={teamA} setTeam={setTeamA} />
        <TeamPicker side="右" label="🔴 右方队伍" team={teamB} setTeam={setTeamB} />
      </div>

      <div className="battle-controls">
        <button className="btn btn-primary" onClick={start} disabled={!canFight}>
          ⚔️ 开始模拟
        </button>
        {result && (
          <>
            <button onClick={() => setPlaying((p) => !p)}>{playing ? "⏸ 暂停" : "▶ 继续"}</button>
            <button onClick={() => { setStep(result.log.length - 1); setPlaying(false); }}>⏭ 直接看结果</button>
            <button onClick={start}>🔀 换个运气重打</button>
          </>
        )}
      </div>

      {result && ev && (
        <>
          <div className="battle-arena">
            {sidePanel(0)}
            <div className="battle-vs">
              <div>第 {ev.turn} 回合</div>
              {finished && (
                <div className="battle-winner">
                  {result.winner === null ? "平局" : result.winner === 0 ? "🏆 左方获胜" : "🏆 右方获胜"}
                </div>
              )}
            </div>
            {sidePanel(1)}
          </div>
          <div className="battle-log" ref={logRef}>
            {result.log.slice(0, step + 1).map((e, i) => (
              <div key={i} className={`battle-log-line kind-${e.kind}`}>
                <span className="battle-log-turn">R{e.turn}</span> {e.text}
              </div>
            ))}
          </div>
        </>
      )}

      <section className="meta-card" style={{ marginTop: 24 }}>
        <h3>📖 简化规则说明</h3>
        <ul className="battle-rules">
          <li>等级固定 100；最大生命 = 体力种族值 ×2 + 200；伤害按经典回合制公式计算（威力 × 攻防比 × 属性相克 × 本系加成 1.25 × 0.85~1.0 乱数）。</li>
          <li>每只精灵携带其「最优技能」前 4 个；能量开局 6、上限 10、每回合回复 2，技能按真实能耗扣除，付不起时自动休息回 4 点。</li>
          <li>出手顺序：技能优先度 → 速度。异常状态按层结算：灼烧/中毒每层每回合扣 1/16 最大生命；冻结每层 +8% 行动失败率；星陨每层 +5% 受伤；萌化每层 -5% 输出；寄生每回合吸取 1/16 并回复对方。</li>
          <li>变化类强化技简化为攻击强化（每层 +15%，最多 3 层）；吸血技能回复 30% 造成伤害。</li>
          <li>不模拟：主动换宠、天气、特性、印记与连锁引爆等进阶机制；阵亡后按队伍顺序自动换宠，最多 120 回合后按剩余生命比例判定。</li>
        </ul>
      </section>
    </div>
  );
}
