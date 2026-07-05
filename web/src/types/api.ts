/** API 请求/响应类型 — 与 FastAPI 后端对齐 */

export interface OptimizeRequest {
  must_include?: number[];
  must_exclude?: number[];
  prefer_type?: string;
  style?: string;
  team_type?: string;  // "synergy" | "balanced"
  min_coverage?: number;
  top_k?: number;
  pop_size?: number;
  generations?: number;
}

export interface ApiPetStats {
  hp: number;
  atk: number;
  def: number;
  sp_atk: number;
  sp_def: number;
  speed: number;
}

export interface ApiTeamMember {
  pet_id: number;
  name: string;
  type_primary: string;
  type_secondary?: string;
  role: string;
  skills: string[];
  stats: ApiPetStats;
}

export interface TeamScores {
  coverage: number;
  defense: number;
  synergy: number;
  stats: number;
  role_balance: number;
  speed: number;
  energy: number;
  total: number;
}

export interface OptimizeResult {
  team: ApiTeamMember[];
  scores: TeamScores;
}

export interface OptimizeResponse {
  teams: OptimizeResult[];
  generations: number;
  pop_size: number;
}

/** API base URL — 开发时指向本地 FastAPI */
export const API_BASE = "http://localhost:8002";
