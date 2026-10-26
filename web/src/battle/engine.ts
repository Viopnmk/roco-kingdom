/**
 * 回合制对战模拟引擎（简化规则版）— 粉丝自制模拟器，非游戏官方机制
 *
 * 规则要点（页面上有完整说明）：
 *  - 等级固定 100，最大生命 = 体力种族值×2 + 200；伤害用经典回合制公式
 *    ⌊(42 × 威力 × 攻击/防御 ÷ 50) + 2⌋ × 属性相克 × 本系加成1.25 × 乱数0.85~1.0
 *  - 能量：开局 6 点、上限 10，每回合结束回复 2；技能按数据能耗扣除，
 *    付不起时自动「休息」回复 4 点
 *  - 先后手：技能优先度 > 速度；异常状态按层数结算（灼烧/中毒每层每回合
 *    扣 1/16 最大生命，冻结每层 8% 行动失败率，星陨每层 +5% 受伤，
 *    萌化每层 -5% 输出，寄生每回合吸取 1/16）；变化类强化技简化为
 *    攻击强化层数（每层 +15%，最多 3 层）
 *  - AI 自动选招（按期望伤害/状态价值估算），阵亡后按队序自动换宠，
 *    不模拟主动换宠、天气与特性
 */

export interface BattlePetInput {
  id: number;
  name: string;
  tp: string;
  ts?: string | null;
  hp: number; atk: number; def: number; spa: number; spd: number; spe: number;
  skills: string[];
}

export interface SkillData {
  t: string; c: string; p: number; a: number; e: number; pri: number;
  st: string[]; ls: boolean;
}

export interface LogEvent {
  turn: number;
  kind: "enter" | "attack" | "status" | "faint" | "info" | "win";
  text: string;
  aIdx: number; bIdx: number;
  aHp: number[]; bHp: number[];
  aEn: number; bEn: number;
}

export interface BattleResult {
  winner: 0 | 1 | null;
  log: LogEvent[];
  maxHpA: number[];
  maxHpB: number[];
}

interface Fighter {
  pet: BattlePetInput;
  hp: number;
  maxHp: number;
  energy: number;
  status: Map<string, number>;
  buff: number;
  alive: boolean;
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const MAX_TURNS = 120;

export function simulate(
  teamAIn: BattlePetInput[],
  teamBIn: BattlePetInput[],
  skillsData: Record<string, SkillData>,
  chart: Record<string, Record<string, number>>,
  seed?: number,
): BattleResult {
  const rng = mulberry32(seed ?? ((Math.random() * 0xffffffff) >>> 0));
  const mk = (pet: BattlePetInput): Fighter => ({
    pet,
    maxHp: pet.hp * 2 + 200,
    hp: pet.hp * 2 + 200,
    energy: 6,
    status: new Map(),
    buff: 0,
    alive: true,
  });
  const teams: Fighter[][] = [teamAIn.map(mk), teamBIn.map(mk)];
  const active = [0, 0];
  const log: LogEvent[] = [];

  const eff = (atkType: string, defPet: BattlePetInput): number => {
    const row = chart[atkType] ?? {};
    let m = row[defPet.tp] ?? 1;
    if (defPet.ts) m *= row[defPet.ts] ?? 1;
    return m;
  };

  const snapshot = (turn: number, kind: LogEvent["kind"], text: string) => {
    log.push({
      turn, kind, text,
      aIdx: active[0], bIdx: active[1],
      aHp: teams[0].map((f) => Math.max(0, Math.round(f.hp))),
      bHp: teams[1].map((f) => Math.max(0, Math.round(f.hp))),
      aEn: teams[0][active[0]]?.energy ?? 0,
      bEn: teams[1][active[1]]?.energy ?? 0,
    });
  };

  interface Action { skillName: string | null; skill: SkillData | null; rest: boolean }
  const chooseAction = (me: Fighter, foe: Fighter): Action => {
    const options: { name: string; skill: SkillData; value: number }[] = [];
    for (const name of me.pet.skills.slice(0, 4)) {
      const sk = skillsData[name];
      if (!sk || sk.e > me.energy) continue;
      let value: number;
      if (sk.p > 0) {
        const stab = sk.t === me.pet.tp || sk.t === me.pet.ts ? 1.25 : 1;
        value = sk.p * (sk.a / 100) * eff(sk.t, foe.pet) * stab;
        if (sk.st.some((s) => !foe.status.has(s))) value += 12;
        if (sk.ls && me.hp < me.maxHp * 0.5) value += 10;
      } else if (sk.st.length > 0) {
        value = sk.st.some((s) => !foe.status.has(s)) ? 55 : 8;
      } else {
        value = me.buff < 2 ? 45 : 6; // 变化类强化技
      }
      options.push({ name, skill: sk, value: value + rng() * 4 });
    }
    if (options.length === 0) return { skillName: null, skill: null, rest: true };
    options.sort((x, y) => y.value - x.value);
    return { skillName: options[0].name, skill: options[0].skill, rest: false };
  };

  const doAction = (turn: number, atkSide: 0 | 1, act: Action): boolean => {
    // 返回 true 表示对面被击倒（战斗可能结束）
    const me = teams[atkSide][active[atkSide]];
    const foeSide = (1 - atkSide) as 0 | 1;
    const foe = teams[foeSide][active[foeSide]];
    if (!me.alive) return false;

    if (act.rest) {
      me.energy = Math.min(10, me.energy + 4);
      snapshot(turn, "info", `${me.pet.name} 能量不足，选择休息（回复至 ${me.energy} 点）`);
      return false;
    }
    const sk = act.skill!;
    me.energy -= sk.e;

    // 冻结判定
    const freezeLayers = me.status.get("冻结") ?? 0;
    if (freezeLayers > 0 && rng() < Math.min(0.4, freezeLayers * 0.08)) {
      snapshot(turn, "status", `${me.pet.name} 被冻住了，无法行动！`);
      return false;
    }

    if (sk.p > 0) {
      if (rng() * 100 > sk.a) {
        snapshot(turn, "attack", `${me.pet.name} 使用 ${act.skillName}，但没有命中！`);
        return false;
      }
      const phys = sk.c !== "魔法";
      // 攻防各 +70 再算比率，压缩种族值差距带来的极端倍率（避免一招秒与刮痧两极）
      const atkStat = ((phys ? me.pet.atk : me.pet.spa) + 70) * (1 + me.buff * 0.15);
      const defStat = (phys ? foe.pet.def : foe.pet.spd) + 70;
      const stab = sk.t === me.pet.tp || sk.t === me.pet.ts ? 1.25 : 1;
      const typeEff = eff(sk.t, foe.pet);
      const vuln = 1 + 0.05 * (foe.status.get("星陨") ?? 0);
      const weak = Math.max(0.7, 1 - 0.05 * (me.status.get("萌化") ?? 0));
      const base = Math.floor((42 * sk.p * (atkStat / Math.max(1, defStat))) / 50) + 2;
      const dmg = Math.max(1, Math.floor(base * stab * typeEff * vuln * weak * (0.85 + rng() * 0.15)));
      foe.hp -= dmg;
      const effTxt = typeEff >= 2 ? "（效果拔群！）" : typeEff <= 0.5 && typeEff > 0 ? "（效果不佳…）" : typeEff === 0 ? "（没有效果！）" : "";
      snapshot(turn, "attack", `${me.pet.name} 使用 ${act.skillName}，对 ${foe.pet.name} 造成 ${dmg} 点伤害${effTxt}`);
      for (const stName of sk.st) {
        if (foe.hp > 0) {
          foe.status.set(stName, (foe.status.get(stName) ?? 0) + 1);
          snapshot(turn, "status", `${foe.pet.name} 陷入${stName}（${foe.status.get(stName)} 层）`);
        }
      }
      if (sk.ls && dmg > 0 && me.hp > 0) {
        const heal = Math.floor(dmg * 0.3);
        me.hp = Math.min(me.maxHp, me.hp + heal);
        snapshot(turn, "status", `${me.pet.name} 吸取了 ${heal} 点生命`);
      }
      if (foe.hp <= 0) {
        foe.hp = 0; foe.alive = false;
        snapshot(turn, "faint", `${foe.pet.name} 倒下了！`);
        return true;
      }
    } else if (sk.st.length > 0) {
      if (rng() * 100 > sk.a) {
        snapshot(turn, "attack", `${me.pet.name} 使用 ${act.skillName}，但没有命中！`);
        return false;
      }
      for (const stName of sk.st) {
        foe.status.set(stName, (foe.status.get(stName) ?? 0) + 1);
        snapshot(turn, "status", `${me.pet.name} 使用 ${act.skillName}，${foe.pet.name} 陷入${stName}（${foe.status.get(stName)} 层）`);
      }
    } else {
      if (me.buff < 3) me.buff += 1;
      snapshot(turn, "status", `${me.pet.name} 使用 ${act.skillName}，攻击强化至 ${me.buff} 层`);
    }
    return false;
  };

  const nextAlive = (side: 0 | 1): number => teams[side].findIndex((f) => f.alive);

  snapshot(0, "enter", `战斗开始！左方派出 ${teams[0][0].pet.name}，右方派出 ${teams[1][0].pet.name}`);
  let winner: 0 | 1 | null = null;

  for (let turn = 1; turn <= MAX_TURNS; turn++) {
    // 换宠（回合开始）
    for (const side of [0, 1] as const) {
      if (!teams[side][active[side]].alive) {
        const nxt = nextAlive(side);
        if (nxt === -1) { winner = (1 - side) as 0 | 1; break; }
        active[side] = nxt;
        snapshot(turn, "enter", `${side === 0 ? "左" : "右"}方派出 ${teams[side][nxt].pet.name}！`);
      }
    }
    if (winner !== null) break;

    const acts: [Action, Action] = [
      chooseAction(teams[0][active[0]], teams[1][active[1]]),
      chooseAction(teams[1][active[1]], teams[0][active[0]]),
    ];
    const prio = (a: Action) => a.skill?.pri ?? 0;
    let order: (0 | 1)[] = [0, 1];
    if (prio(acts[1]) > prio(acts[0])) order = [1, 0];
    else if (prio(acts[0]) === prio(acts[1])) {
      const spA = teams[0][active[0]].pet.spe, spB = teams[1][active[1]].pet.spe;
      if (spB > spA || (spB === spA && rng() < 0.5)) order = [1, 0];
    }

    for (const side of order) {
      const foeSide = (1 - side) as 0 | 1;
      if (!teams[side][active[side]].alive || !teams[foeSide][active[foeSide]].alive) continue;
      doAction(turn, side, acts[side]);
    }

    // 回合结束：异常状态结算 + 能量回复
    for (const side of [0, 1] as const) {
      const f = teams[side][active[side]];
      if (!f.alive) continue;
      for (const dotName of ["灼烧", "中毒"] as const) {
        const layers = f.status.get(dotName) ?? 0;
        if (layers > 0 && f.alive) {
          const dmg = Math.floor((f.maxHp / 16) * layers);
          f.hp -= dmg;
          snapshot(turn, "status", `${f.pet.name} 受到${dotName}伤害 ${dmg} 点`);
          if (f.hp <= 0) { f.hp = 0; f.alive = false; snapshot(turn, "faint", `${f.pet.name} 倒下了！`); }
        }
      }
      const leech = f.status.get("寄生") ?? 0;
      if (leech > 0 && f.alive) {
        const foeSide = (1 - side) as 0 | 1;
        const foe = teams[foeSide][active[foeSide]];
        const dmg = Math.floor((f.maxHp / 16) * leech);
        f.hp -= dmg;
        if (foe.alive) foe.hp = Math.min(foe.maxHp, foe.hp + dmg);
        snapshot(turn, "status", `寄生吸取了 ${f.pet.name} ${dmg} 点生命`);
        if (f.hp <= 0) { f.hp = 0; f.alive = false; snapshot(turn, "faint", `${f.pet.name} 倒下了！`); }
      }
      if (f.alive) f.energy = Math.min(10, f.energy + 2);
    }

    if (nextAlive(0) === -1 || nextAlive(1) === -1) {
      winner = nextAlive(0) === -1 ? 1 : 0;
      break;
    }
  }

  if (winner === null) {
    const frac = (side: 0 | 1) =>
      teams[side].reduce((s, f) => s + Math.max(0, f.hp) / f.maxHp, 0);
    winner = frac(0) === frac(1) ? null : frac(0) > frac(1) ? 0 : 1;
    snapshot(MAX_TURNS, "info", `回合数耗尽，按剩余生命比例判定`);
  }
  snapshot(log.length ? log[log.length - 1].turn : MAX_TURNS, "win",
    winner === null ? "双方战平！" : `${winner === 0 ? "左" : "右"}方获胜！🎉`);

  return {
    winner,
    log,
    maxHpA: teams[0].map((f) => f.maxHp),
    maxHpB: teams[1].map((f) => f.maxHp),
  };
}
