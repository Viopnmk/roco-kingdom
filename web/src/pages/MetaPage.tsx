import { Link } from "react-router-dom";
import metaRaw from "../data/meta.json";

interface PetBrief { id: number; name: string; tp: string; ts?: string | null; role: string }
interface Meta {
  generated_at: string;
  sample: { runs: number; teams: number; candidates: number };
  appearance: (PetBrief & { rate: number; count: number })[];
  top_pairs: { a: PetBrief; b: PetBrief; count: number }[];
  type_dist: { type: string; count: number }[];
  role_dist: { role: string; count: number }[];
  speed_buckets: { bucket: string; count: number }[];
  blindspots: { type: string; pct: number }[];
  clusters: { name: string; desc: string; core: string[]; size: number; pets: { id: number; name: string }[] }[];
}
const meta = metaRaw as unknown as Meta;

function Bar({ pct, color }: { pct: number; color?: string }) {
  return (
    <div className="meta-bar">
      <div className="meta-bar-fill" style={{ width: `${Math.min(100, pct)}%`, background: color ?? "var(--accent)" }} />
    </div>
  );
}

export default function MetaPage() {
  const maxType = Math.max(...meta.type_dist.map((t) => t.count));
  const maxRole = Math.max(...meta.role_dist.map((r) => r.count));
  const maxSpeed = Math.max(...meta.speed_buckets.map((s) => s.count));
  const maxAppear = Math.max(...meta.appearance.map((a) => a.rate));

  return (
    <div className="meta-page">
      <h2 className="ai-title">Meta 数据分析</h2>
      <p className="ai-subtitle">
        基于本站 AI 配队引擎的模拟样本统计：对 {meta.sample.candidates} 只候选精灵运行 {meta.sample.runs} 轮
        遗传搜索、采样 {meta.sample.teams} 支最优队伍后统计。数据生成于 {meta.generated_at}，
        随图鉴数据更新而刷新。<strong>这是引擎视角的强度与流行度分析，不是游戏官方实战遥测。</strong>
      </p>

      <section className="meta-card">
        <h3>🏆 精灵出场率 Top 15（最优队伍中的出现比例）</h3>
        {meta.appearance.map((p, i) => (
          <div key={p.id} className="meta-row">
            <span className="meta-rank">{i + 1}</span>
            <Link to={`/pet/${p.id}`} className="meta-name">{p.name}</Link>
            <span className="meta-tag">{p.tp}{p.ts ? `/${p.ts}` : ""} · {p.role}</span>
            <Bar pct={(p.rate / maxAppear) * 100} />
            <span className="meta-val">{p.rate}%</span>
          </div>
        ))}
      </section>

      <section className="meta-card">
        <h3>🤝 热门组合 Top 10（同一队伍中共现次数）</h3>
        {meta.top_pairs.map((pair, i) => (
          <div key={i} className="meta-row">
            <span className="meta-rank">{i + 1}</span>
            <span className="meta-name">
              <Link to={`/pet/${pair.a.id}`}>{pair.a.name}</Link>
              {" + "}
              <Link to={`/pet/${pair.b.id}`}>{pair.b.name}</Link>
            </span>
            <Bar pct={(pair.count / meta.top_pairs[0].count) * 100} color="#ab7df8" />
            <span className="meta-val">{pair.count} 次</span>
          </div>
        ))}
      </section>

      <section className="meta-card">
        <h3>🧩 战术体系一览（NLP 聚类）</h3>
        <div className="meta-clusters">
          {meta.clusters.map((c) => (
            <div key={c.name} className="meta-cluster">
              <div className="meta-cluster-head">
                <strong>{c.name}</strong>
                <span className="meta-tag">{c.size} 只相关精灵</span>
              </div>
              <p>{c.desc}</p>
              <div className="meta-cluster-pets">
                {c.pets.map((p) => (
                  <Link key={p.id} to={`/pet/${p.id}`} className="meta-chip">{p.name}</Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="meta-grid2">
        <section className="meta-card">
          <h3>🎨 候选池主属性分布</h3>
          {meta.type_dist.map((t) => (
            <div key={t.type} className="meta-row">
              <span className="meta-name-sm">{t.type}</span>
              <Bar pct={(t.count / maxType) * 100} />
              <span className="meta-val">{t.count}</span>
            </div>
          ))}
        </section>
        <section className="meta-card">
          <h3>🎭 职责分布</h3>
          {meta.role_dist.map((r) => (
            <div key={r.role} className="meta-row">
              <span className="meta-name-sm">{r.role}</span>
              <Bar pct={(r.count / maxRole) * 100} color="#66bb6a" />
              <span className="meta-val">{r.count}</span>
            </div>
          ))}
          <h3 style={{ marginTop: 18 }}>💨 速度分档</h3>
          {meta.speed_buckets.map((s) => (
            <div key={s.bucket} className="meta-row">
              <span className="meta-name-sm">{s.bucket}</span>
              <Bar pct={(s.count / maxSpeed) * 100} color="#ffa726" />
              <span className="meta-val">{s.count}</span>
            </div>
          ))}
        </section>
      </div>

      <section className="meta-card">
        <h3>🎯 打击面盲区（能以 2 倍以上打中该属性的候选精灵比例，越低越难打）</h3>
        {meta.blindspots.map((b) => (
          <div key={b.type} className="meta-row">
            <span className="meta-name-sm">{b.type}</span>
            <Bar pct={b.pct} color="#ef5350" />
            <span className="meta-val">{b.pct}%</span>
          </div>
        ))}
        <p className="meta-note">配队时优先给队伍补上榜单前列属性的打击手段，避免遇到打不动的对手。</p>
      </section>
    </div>
  );
}
