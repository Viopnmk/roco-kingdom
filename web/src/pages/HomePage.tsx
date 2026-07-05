import { useState, useMemo } from "react";
import type { Pet } from "../types";
import { pets, evolutionChains } from "../data";
import SearchBar from "../components/SearchBar";
import FilterPanel from "../components/FilterPanel";
import EvolutionChainCard from "../components/EvolutionChainCard";

interface EvolutionChainWithPets {
  id: string;
  name: string;
  members: Pet[];
  apex_id: number;
  apex_name: string;
  base_id: number;
  base_name: string;
}

interface FamilyGroup {
  base_name: string;
  base_id: number;
  chains: EvolutionChainWithPets[];
  members: Pet[];
}

export default function HomePage() {
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState("id");

  const toggleFilter = (type: string) => {
    setFilters((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const petMap = useMemo(() => {
    const map = new Map<number, Pet>();
    for (const pet of pets) {
      map.set(pet.id, pet);
    }
    return map;
  }, []);

  // 将分支进化链按基础精灵分组
  const familyGroups = useMemo((): FamilyGroup[] => {
    const chainsWithPets = evolutionChains.chains
      .map((chain) => {
        const members = chain.members
          .map((id) => petMap.get(id))
          .filter((p): p is Pet => p !== undefined);
        if (members.length === 0) return null;
        
        return {
          ...chain,
          members,
          base_id: members[0].id,
          base_name: members[0].name,
        };
      })
      .filter((chain): chain is EvolutionChainWithPets => chain !== null);

    // 按基础精灵分组（分支进化归类）
    const groupMap = new Map<number, FamilyGroup>();
    for (const chain of chainsWithPets) {
      const existing = groupMap.get(chain.base_id);
      if (existing) {
        existing.chains.push(chain);
        // 合并成员（去重）
        const existingIds = new Set(existing.members.map(m => m.id));
        for (const member of chain.members) {
          if (!existingIds.has(member.id)) {
            existing.members.push(member);
            existingIds.add(member.id);
          }
        }
      } else {
        groupMap.set(chain.base_id, {
          base_name: chain.base_name,
          base_id: chain.base_id,
          chains: [chain],
          members: [...chain.members],
        });
      }
    }

    return Array.from(groupMap.values());
  }, [petMap]);

  const filtered = useMemo(() => {
    let result = [...familyGroups];

    // 搜索
    if (search.trim()) {
      const kw = search.trim().toLowerCase();
      result = result.filter((group) => {
        const groupMatch = group.base_name.toLowerCase().includes(kw);
        const chainMatch = group.chains.some(
          (chain) => chain.name.toLowerCase().includes(kw)
        );
        const memberMatch = group.members.some(
          (pet) =>
            pet.name.toLowerCase().includes(kw) ||
            String(pet.id).includes(kw) ||
            pet.type_primary.toLowerCase().includes(kw)
        );
        return groupMatch || chainMatch || memberMatch;
      });
    }

    // 属性筛选
    if (filters.length) {
      result = result.filter((group) => {
        const groupTypes = new Set<string>();
        for (const pet of group.members) {
          if (pet.type_primary) groupTypes.add(pet.type_primary);
          if (pet.type_secondary) groupTypes.add(pet.type_secondary);
        }
        return filters.some((f) => groupTypes.has(f));
      });
    }

    // 排序（按基础精灵编号）
    result.sort((a, b) => {
      switch (sortBy) {
        case "id":
          return a.base_id - b.base_id;
        case "name":
          return a.base_name.localeCompare(b.base_name, "zh");
        case "count_desc":
          return b.members.length - a.members.length;
        case "count_asc":
          return a.members.length - b.members.length;
        case "total_desc":
          const totalA = a.members.reduce((sum, p) => sum + p.stats.total, 0);
          const totalB = b.members.reduce((sum, p) => sum + p.stats.total, 0);
          return totalB - totalA;
        case "total_asc":
          const tA = a.members.reduce((sum, p) => sum + p.stats.total, 0);
          const tB = b.members.reduce((sum, p) => sum + p.stats.total, 0);
          return tA - tB;
        default:
          return a.base_id - b.base_id;
      }
    });

    return result;
  }, [familyGroups, search, filters, sortBy]);

  // 将家族组转换为展示用的链数据
  const displayChains = useMemo(() => {
    return filtered.map((group) => {
      // 找到最高种族值的精灵作为代表
      const apexPet = group.members.reduce((best, current) => 
        current.stats.total > best.stats.total ? current : best
      );
      
      return {
        id: `family_${group.base_id}`,
        name: `${group.base_name}家族${group.chains.length > 1 ? ` (${group.chains.length}个分支)` : ""}`,
        members: group.members.sort((a, b) => a.id - b.id),
        apex_id: apexPet.id,
        apex_name: apexPet.name,
        base_id: group.base_id,
        base_name: group.base_name,
      };
    });
  }, [filtered]);

  if (!pets.length) {
    return (
      <div className="empty-state">
        <h3>还没有数据</h3>
        <p>
          请先运行爬虫获取数据：<br />
          <code>cd scraper && pip install -r requirements.txt && python main.py</code>
          <br /><br />
          然后将 <code>scraper/output/</code> 中的 JSON 文件复制到 <code>web/src/data/</code>
          <br />
          最后重新运行 <code>npm run dev</code>
        </p>
      </div>
    );
  }

  return (
    <div>
      <SearchBar value={search} onChange={setSearch} />
      <FilterPanel
        selected={filters}
        onToggle={toggleFilter}
        sortBy={sortBy}
        onSortChange={setSortBy}
      />
      <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 16 }}>
        共 {filtered.length} 个精灵家族
      </p>
      <div className="evo-chain-grid">
        {displayChains.map((chain) => (
          <EvolutionChainCard key={chain.id} chain={chain} />
        ))}
      </div>
    </div>
  );
}