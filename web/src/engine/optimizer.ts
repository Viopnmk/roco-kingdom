/**
 * 浏览器本地配队引擎 — 移植自 ml/src/optimize/fitness.py 与 genetic.py
 *
 * 与 Python 版相同的 7 维适应度（打击面/抗性互补/联动/有效种族值/职责/速度/能量）、
 * 相同的约束规则与 NSGA-II 流程；默认参数与 FastAPI 模式一致（种群 100 × 100 代）。
 * 遗传算法本身带随机性，两次搜索结果不同属正常现象。
 */

export interface ProfileData {
  name: string;
  tp: string;
  ts: string | null;
  role: string;
  hp: number; atk: number; def: number; spa: number; spd: number; spe: number;
  total: number; ea: number; esa: number;
  energy: number;
  tags: string[];
  cov: Record<string, number>;
  weak: Record<string, number>;
  skills: string[];
  bs?: string[]; // 对战模拟用招式表（optimal_skills 为空的精灵已按学习面补齐）
}

export interface TeamData {
  pet_ids: number[];
  profiles: Record<string, ProfileData>;
  synergy: [number, number, number][];
}

export interface OptimizeRequestLike {
  must_include?: number[];
  must_exclude?: number[];
  prefer_type?: string;
  style?: string;
  team_type?: string;
  min_coverage?: number;
  top_k?: number;
  pop_size?: number;
  generations?: number;
}

export interface TeamMemberResult {
  pet_id: number;
  name: string;
  type_primary: string;
  type_secondary?: string;
  role: string;
  skills: string[];
  stats: { hp: number; atk: number; def: number; sp_atk: number; sp_def: number; speed: number };
}

export interface TeamResult {
  team: TeamMemberResult[];
  scores: {
    coverage: number; defense: number; synergy: number; stats: number;
    role_balance: number; speed: number; energy: number; total: number;
  };
}

const TYPES = [
  "普通", "草", "火", "水", "光", "地", "冰", "龙",
  "电", "幻", "毒", "虫", "翼", "恶", "萌", "幽灵", "武", "机械",
];

const FALLBACK_SKILLS = ["一拳", "丢冰块", "防御", "休息回复"];

// ── 可复现随机源（mulberry32）────────────────────────────────
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Rng = () => number;
const randInt = (rng: Rng, n: number) => Math.floor(rng() * n);
const choice = <T,>(rng: Rng, arr: T[]): T => arr[randInt(rng, arr.length)];

function sample<T>(rng: Rng, arr: T[], k: number): T[] {
  const copy = [...arr];
  const out: T[] = [];
  const n = Math.min(k, copy.length);
  for (let i = 0; i < n; i++) {
    const j = randInt(rng, copy.length);
    out.push(copy.splice(j, 1)[0]);
  }
  return out;
}

const mean = (xs: number[]) => xs.reduce((s, x) => s + x, 0) / xs.length;
const variance = (xs: number[]) => {
  const m = mean(xs);
  return mean(xs.map((x) => (x - m) * (x - m))); // 总体方差，与 numpy 默认一致
};

// ── 适应度引擎（对应 fitness.py TeamFitness）────────────────────
interface Member { id: number; skills: string[] }

class TeamFitness {
  profiles = new Map<number, ProfileData>();
  synergy = new Map<string, number>();

  constructor(data: TeamData) {
    for (const [id, p] of Object.entries(data.profiles)) {
      this.profiles.set(Number(id), p);
    }
    for (const [a, b, s] of data.synergy) {
      this.synergy.set(`${Math.min(a, b)},${Math.max(a, b)}`, s);
    }
  }

  coverageScore(team: Member[]): number {
    const teamCov = new Map<string, number>();
    for (const m of team) {
      const pet = this.profiles.get(m.id);
      if (!pet) continue;
      for (const [t, mult] of Object.entries(pet.cov)) {
        teamCov.set(t, Math.max(teamCov.get(t) ?? 0, mult));
      }
    }
    const scores = TYPES.map((t) => teamCov.get(t) ?? 1.0);
    const blankPenalty = scores.filter((s) => s <= 1.0).length * 2;
    return mean(scores) * 10 - variance(scores) * 0.1 - blankPenalty;
  }

  private weakSet(pid: number): Set<string> {
    const pet = this.profiles.get(pid);
    const out = new Set<string>();
    if (pet) {
      for (const [t, mult] of Object.entries(pet.weak)) {
        if (mult >= 2.0) out.add(t);
      }
    }
    return out;
  }

  defenseScore(team: Member[]): number {
    const weaknesses = team.filter((m) => this.profiles.has(m.id)).map((m) => this.weakSet(m.id));
    let score = 10.0;
    for (let i = 0; i < weaknesses.length; i++) {
      for (let j = i + 1; j < weaknesses.length; j++) {
        let shared = 0;
        for (const t of weaknesses[i]) if (weaknesses[j].has(t)) shared++;
        score -= 3 * shared;
      }
    }
    return Math.max(0, score);
  }

  synergyScore(team: Member[]): number {
    let total = 0, pairs = 0;
    for (let i = 0; i < team.length; i++) {
      for (let j = i + 1; j < team.length; j++) {
        const key = `${Math.min(team[i].id, team[j].id)},${Math.max(team[i].id, team[j].id)}`;
        total += this.synergy.get(key) ?? 0;
        pairs++;
      }
    }
    return pairs > 0 ? total / pairs : 0;
  }

  statsScore(team: Member[]): number {
    let total = 0;
    for (const m of team) {
      const pet = this.profiles.get(m.id);
      if (!pet) continue;
      const eff = Math.max(pet.ea, pet.esa);
      total += pet.total > 0 ? eff / pet.total : 0;
    }
    return (total / team.length) * 100;
  }

  roleScore(team: Member[]): number {
    let a = 0, t = 0, s = 0;
    for (const m of team) {
      const pet = this.profiles.get(m.id);
      if (!pet) continue;
      const r = pet.role;
      if (r === "坦克") t++;
      else if (r === "辅助" || r === "控场" || r === "天气手") s++;
      else a++; // 输出类与未分类都算输出（与 Python 一致）
    }
    const dot = 3 * a + 2 * t + 1 * s;
    const norm = Math.sqrt(14) * Math.sqrt(a * a + t * t + s * s);
    return norm > 0 ? (dot / norm) * 10 : 0;
  }

  speedScore(team: Member[]): number {
    const speeds: number[] = [];
    for (const m of team) {
      const pet = this.profiles.get(m.id);
      if (pet) speeds.push(pet.spe);
    }
    if (speeds.length === 0) return 5;
    return Math.max(0, 10 - Math.abs(variance(speeds) - 200) / 50);
  }

  energyScore(team: Member[]): number {
    let total = 0;
    for (const m of team) {
      const pet = this.profiles.get(m.id);
      if (pet) total += pet.energy;
    }
    const avg = total / team.length;
    return Math.max(0, 10 - Math.abs(avg - 3.0) * 2);
  }

  evaluate(team: Member[]): number[] {
    return [
      this.coverageScore(team),
      this.defenseScore(team),
      this.synergyScore(team),
      this.statsScore(team),
      this.roleScore(team),
      this.speedScore(team),
      this.energyScore(team),
    ];
  }

  totalScore(team: Member[], teamType?: string | null): number {
    let w = [3, 3, 2, 1.5, 1, 0.5, 0.5];
    if (teamType === "synergy") w = [1.5, 1.5, 5.0, 2.0, 1.0, 0.5, 0.5];
    else if (teamType === "balanced") w = [4.0, 4.0, 0.5, 1.5, 1.0, 0.5, 0.5];
    const v = this.evaluate(team);
    return v.reduce((s, vi, i) => s + w[i] * vi, 0);
  }

  checkConstraints(
    team: Member[],
    opts: {
      mustInclude?: number[]; mustExclude?: number[]; preferType?: string;
      style?: string; teamType?: string | null; minCoverage?: number;
    },
  ): boolean {
    const teamIds = new Set(team.map((m) => m.id));

    if (opts.mustInclude && !opts.mustInclude.every((id) => teamIds.has(id))) return false;
    if (opts.mustExclude && opts.mustExclude.some((id) => teamIds.has(id))) return false;

    if (opts.preferType) {
      let count = 0;
      for (const id of teamIds) {
        const p = this.profiles.get(id);
        if (p && (p.tp === opts.preferType || p.ts === opts.preferType)) count++;
      }
      if (count < 1) return false;
    }

    if (opts.style) {
      const styleTags: Record<string, string> = {
        "灼烧体系": "灼烧", "中毒消耗": "中毒", "冻结控场": "冻结",
        "星陨爆发": "星陨", "天气队": "天气", "传动体系": "传动",
        "印记运营": "印记", "应对返还": "应对攻击",
        "先手压制": "先手", "吸血续航": "吸血",
        "增益传递": "增益传递", "巧变切换": "巧变",
        "萌化退化": "萌化",
      };
      const tag = styleTags[opts.style] ?? opts.style;
      let tagged = 0;
      for (const id of teamIds) {
        if (this.profiles.get(id)?.tags.includes(tag)) tagged++;
      }
      if (tagged < 2) return false;
    }

    if (opts.teamType === "synergy" || opts.teamType === "balanced") {
      const counter = new Map<string, number>();
      for (const id of teamIds) {
        const tp = this.profiles.get(id)?.tp ?? "";
        if (tp) counter.set(tp, (counter.get(tp) ?? 0) + 1);
      }
      const maxCount = Math.max(0, ...counter.values());
      if (opts.teamType === "synergy" && maxCount < 3) return false;
      if (opts.teamType === "balanced") {
        if (maxCount > 2) return false;
        const sets = [...teamIds].map((id) => this.weakSet(id));
        let totalShared = 0;
        for (let i = 0; i < sets.length; i++) {
          for (let j = i + 1; j < sets.length; j++) {
            for (const t of sets[i]) if (sets[j].has(t)) totalShared++;
          }
        }
        if (totalShared > 3) return false;
      }
    }

    if ((opts.minCoverage ?? 0) > 0 && this.coverageScore(team) < (opts.minCoverage ?? 0)) {
      return false;
    }
    return true;
  }
}

// ── NSGA-II（对应 genetic.py）───────────────────────────────────
interface Individual {
  team: Member[];
  fitness: number[];
  rank: number;
  crowding: number;
}

const CROSSOVER_RATE = 0.8;
const MUTATION_RATE = 0.15;
const ELITE_RATE = 0.1;
const TOURNAMENT_SIZE = 3;

export function optimizeTeams(data: TeamData, req: OptimizeRequestLike): TeamResult[] {
  const engine = new TeamFitness(data);
  const rng = mulberry32((Math.random() * 0xffffffff) >>> 0);
  const popSize = req.pop_size ?? 100;
  const generations = req.generations ?? 100;
  const topK = req.top_k ?? 10;
  const mustInclude = req.must_include ?? undefined;
  const mustExclude = req.must_exclude ?? undefined;
  const teamType = req.team_type ? req.team_type : null;
  const constraintOpts = {
    mustInclude, mustExclude,
    preferType: req.prefer_type ?? undefined,
    style: req.style ?? undefined,
    teamType, minCoverage: req.min_coverage ?? 0,
  };

  // 与 Python API 一致：技能池只含候选池精灵（optimal_skills）
  const petSkills = new Map<number, string[]>();
  for (const id of data.pet_ids) {
    petSkills.set(id, data.profiles[String(id)]?.skills ?? []);
  }

  const pickSkills = (pid: number): string[] => {
    const skills = petSkills.get(pid) ?? [];
    if (skills.length >= 4) return sample(rng, skills, 4);
    if (skills.length > 0) {
      const out = [...skills];
      while (out.length < 4) out.push(skills[0]);
      return out;
    }
    return [...FALLBACK_SKILLS];
  };

  const randomTeam = (): Member[] => {
    const available = data.pet_ids.filter((id) => !(mustExclude ?? []).includes(id));
    const selected = new Set<number>(mustInclude ?? []);
    const remaining = sample(rng, available.filter((id) => !selected.has(id)), available.length);
    for (const pid of remaining) {
      if (selected.size >= 6) break;
      selected.add(pid);
    }
    return [...selected].map((id) => ({ id, skills: pickSkills(id) }));
  };

  const isZeroFitness = (f: number[]) => f.length === 0 || f.every((v) => v === 0);

  // 初始种群
  let pop: Individual[] = [];
  for (let i = 0; i < popSize; i++) {
    pop.push({ team: randomTeam(), fitness: [], rank: 0, crowding: 0 });
  }

  const dominates = (a: number[], b: number[]) =>
    a.every((v, i) => v >= b[i]) && a.some((v, i) => v > b[i]);

  const nonDominatedSort = (population: Individual[]): Individual[][] => {
    const n = population.length;
    const domCount = new Array<number>(n).fill(0);
    const dominatedList: Set<number>[] = Array.from({ length: n }, () => new Set<number>());
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (i === j) continue;
        if (dominates(population[i].fitness, population[j].fitness)) dominatedList[i].add(j);
        else if (dominates(population[j].fitness, population[i].fitness)) domCount[i]++;
      }
    }
    const fronts: Individual[][] = [];
    let current: number[] = [];
    for (let i = 0; i < n; i++) {
      if (domCount[i] === 0) { population[i].rank = 0; current.push(i); }
    }
    let rank = 0;
    while (current.length > 0) {
      fronts.push(current.map((i) => population[i]));
      const next: number[] = [];
      for (const i of current) {
        for (const j of dominatedList[i]) {
          domCount[j]--;
          if (domCount[j] === 0) { population[j].rank = rank + 1; next.push(j); }
        }
      }
      current = next;
      rank++;
    }
    return fronts;
  };

  const crowdingDistance = (front: Individual[]) => {
    if (front.length <= 2) {
      for (const ind of front) ind.crowding = Infinity;
      return;
    }
    for (const ind of front) ind.crowding = 0;
    const nObj = front[0].fitness.length;
    for (let o = 0; o < nObj; o++) {
      const sorted = [...front].sort((x, y) => x.fitness[o] - y.fitness[o]);
      const fMin = sorted[0].fitness[o], fMax = sorted[sorted.length - 1].fitness[o];
      if (fMax === fMin) continue;
      sorted[0].crowding = Infinity;
      sorted[sorted.length - 1].crowding = Infinity;
      for (let i = 1; i < sorted.length - 1; i++) {
        sorted[i].crowding += (sorted[i + 1].fitness[o] - sorted[i - 1].fitness[o]) / (fMax - fMin);
      }
    }
  };

  const tournament = (population: Individual[]): Individual => {
    const candidates = sample(rng, population, Math.min(TOURNAMENT_SIZE, population.length));
    let best = candidates[0];
    for (const c of candidates.slice(1)) {
      if (c.rank < best.rank || (c.rank === best.rank && c.crowding > best.crowding)) best = c;
    }
    return best;
  };

  const crossover = (pa: Individual, pb: Individual): [Individual, Individual] => {
    const teamA = [...pa.team], teamB = [...pb.team];
    if (rng() < CROSSOVER_RATE) {
      const idx = randInt(rng, 6);
      [teamA[idx], teamB[idx]] = [teamB[idx], teamA[idx]];
      const idsA = new Set(teamA.map((m) => m.id)), idsB = new Set(teamB.map((m) => m.id));
      if (idsA.size < 6 || idsB.size < 6) {
        [teamA[idx], teamB[idx]] = [teamB[idx], teamA[idx]]; // 出现重复则回退
      }
    }
    return [
      { team: teamA, fitness: [], rank: 0, crowding: 0 },
      { team: teamB, fitness: [], rank: 0, crowding: 0 },
    ];
  };

  const mutate = (ind: Individual): Individual => {
    const team = [...ind.team];
    const mustSet = new Set(mustInclude ?? []);
    if (rng() < MUTATION_RATE) {
      const idx = randInt(rng, 6);
      if (rng() < 0.5) {
        if (!mustSet.has(team[idx].id)) {
          const inTeam = new Set(team.map((m) => m.id));
          const available = data.pet_ids.filter(
            (id) => !inTeam.has(id) && !(mustExclude ?? []).includes(id),
          );
          if (available.length > 0) {
            const newPid = choice(rng, available);
            const skills = petSkills.get(newPid) ?? [];
            const newSkills = skills.length >= 4 ? sample(rng, skills, 4) : skills.slice(0, 4);
            team[idx] = { id: newPid, skills: newSkills };
          }
        }
      } else {
        const pid = team[idx].id;
        const skills = petSkills.get(pid) ?? [];
        if (skills.length > 4) {
          const current = new Set(team[idx].skills);
          const alternatives = skills.filter((s) => !current.has(s));
          if (alternatives.length > 0) {
            const newSkills = [...team[idx].skills];
            newSkills[randInt(rng, 4)] = choice(rng, alternatives);
            team[idx] = { id: pid, skills: newSkills };
          }
        }
      }
    }
    return { team, fitness: [], rank: 0, crowding: 0 };
  };

  // 主循环
  for (let gen = 0; gen < generations; gen++) {
    for (const ind of pop) {
      if (isZeroFitness(ind.fitness)) ind.fitness = engine.evaluate(ind.team);
    }
    for (const ind of pop) {
      if (!engine.checkConstraints(ind.team, constraintOpts)) {
        ind.team = randomTeam();
        ind.fitness = engine.evaluate(ind.team);
      }
    }
    const fronts = nonDominatedSort(pop);
    for (const front of fronts) crowdingDistance(front);

    const eliteCount = Math.max(1, Math.floor(popSize * ELITE_RATE));
    const newPop: Individual[] = [];
    for (const front of fronts) {
      for (const ind of front) {
        if (newPop.length < eliteCount) {
          newPop.push({ team: [...ind.team], fitness: ind.fitness, rank: ind.rank, crowding: ind.crowding });
        }
      }
    }
    while (newPop.length < popSize) {
      const [childA, childB] = crossover(tournament(pop), tournament(pop));
      newPop.push(mutate(childA));
      if (newPop.length < popSize) newPop.push(mutate(childB));
    }
    pop = newPop;
  }

  // 最终评估与排序
  for (const ind of pop) ind.fitness = engine.evaluate(ind.team);
  const valid = pop.filter((ind) => engine.checkConstraints(ind.team, constraintOpts));
  valid.sort((x, y) => engine.totalScore(y.team, teamType) - engine.totalScore(x.team, teamType));

  const round1 = (x: number) => Math.round(x * 10) / 10;
  const results: TeamResult[] = [];
  const seen = new Set<string>();
  for (const ind of valid) {
    const key = ind.team.map((m) => m.id).sort((a, b) => a - b).join(",");
    if (seen.has(key)) continue;
    seen.add(key);
    const s = ind.fitness;
    results.push({
      team: ind.team.map((m) => {
        const pet = engine.profiles.get(m.id);
        return {
          pet_id: m.id,
          name: pet?.name ?? `#${m.id}`,
          type_primary: pet?.tp ?? "",
          type_secondary: pet?.ts ?? undefined,
          role: pet?.role ?? "",
          skills: m.skills,
          stats: {
            hp: pet?.hp ?? 0, atk: pet?.atk ?? 0, def: pet?.def ?? 0,
            sp_atk: pet?.spa ?? 0, sp_def: pet?.spd ?? 0, speed: pet?.spe ?? 0,
          },
        };
      }),
      scores: {
        coverage: round1(s[0]), defense: round1(s[1]), synergy: round1(s[2]),
        stats: round1(s[3]), role_balance: round1(s[4]), speed: round1(s[5]),
        energy: round1(s[6]), total: round1(engine.totalScore(ind.team, teamType)),
      },
    });
    if (results.length >= topK) break;
  }
  return results;
}
