import type { Pet, Skill, LearnsetEntry, TypeChartData } from "../types";

import petsData from "./pets.json";
import skillsData from "./skills.json";
import learnsetData from "./learnset.json";
import typeChartData from "./type_chart.json";
import evolutionChainsData from "./evolution_chains.json";

export const pets: Pet[] = petsData as Pet[];
export const skills: Skill[] = skillsData as Skill[];
export const learnset: LearnsetEntry[] = learnsetData as LearnsetEntry[];
export const typeChart: TypeChartData = typeChartData as TypeChartData;
export const evolutionChains = evolutionChainsData;
