/** 属性列表 */
export const TYPES = [
  "普通", "草", "火", "水", "光", "地", "冰", "龙",
  "电", "幻", "毒", "虫", "翼", "恶", "萌", "幽灵", "武", "机械",
] as const;

export type PetType = (typeof TYPES)[number];

/** 精灵基础信息 */
export interface Pet {
  id: number;
  name: string;
  type_primary: PetType;
  type_secondary?: PetType;
  stats: {
    hp: number;
    atk: number;
    defense: number;
    sp_atk: number;
    sp_def: number;
    speed: number;
    total: number;
  };
  ability: string;
  height: string;
  weight: string;
  description: string;
  evolution_chain: { name: string; level: number | null }[];
  how_to_get: string;
  skills: string[];
  stone_skills?: string[];
  bloodline_skills?: string[];
  source: string;
}

/** 技能 */
export interface Skill {
  name: string;
  type: PetType;
  category: "物理" | "魔法" | "变化";
  power: number;
  pp: number;
  accuracy: number;
  energy: number;
  effect: string;
}

/** 精灵-技能关联 */
export interface LearnsetEntry {
  pet_id: number;
  pet_name: string;
  skill_name: string;
  source: "level" | "stone" | "bloodline";
}

/** 属性克制数据 */
export interface TypeChartData {
  types: PetType[];
  chart: Record<PetType, Record<PetType, number>>;
  matrix: Record<PetType, Record<PetType, number>>;
}

/** 统计信息 */
export interface Stats {
  total_pets: number;
  total_skills: number;
  total_learnset: number;
  types: Record<string, number>;
}
