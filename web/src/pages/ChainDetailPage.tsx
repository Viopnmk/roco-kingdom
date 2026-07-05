import { useParams, useNavigate } from "react-router-dom";
import type { Pet, PetType } from "../types";
import { pets, evolutionChains } from "../data";
import { getTypeColor } from "../utils/typeChart";

export default function ChainDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // 解析家族ID（支持 family_xxx 格式）
  const baseId = parseInt(id?.replace("family_", "").replace("chain_", "") || "0", 10);

  // 找到该家族的所有进化链
  const petMap = new Map<number, Pet>();
  for (const pet of pets) {
    petMap.set(pet.id, pet);
  }

  // 找到所有以该基础精灵开头的进化链
  const relatedChains = evolutionChains.chains.filter((chain) => {
    const firstMember = petMap.get(chain.members[0]);
    return firstMember?.id === baseId;
  });

  if (relatedChains.length === 0) {
    return (
      <div>
        <button className="back-btn" onClick={() => navigate("/")}>
          ← 返回家族列表
        </button>
        <div className="empty-state">
          <h3>家族不存在</h3>
          <p>未找到编号为 {id} 的家族</p>
        </div>
      </div>
    );
  }

  // 合并所有成员（去重）
  const memberSet = new Map<number, Pet>();
  let apexPet: Pet | undefined;
  let apexTotal = 0;

  for (const chain of relatedChains) {
    for (const mid of chain.members) {
      const pet = petMap.get(mid);
      if (pet) {
        memberSet.set(mid, pet);
        if (pet.stats.total > apexTotal) {
          apexTotal = pet.stats.total;
          apexPet = pet;
        }
      }
    }
  }

  // 按种族值分组，同种族值不同外观不单独展示（保留编号最小的）
  const uniqueMembers = Array.from(memberSet.values()).sort((a, b) => a.id - b.id);
  const seenTotals = new Map<number, Pet>();
  const filteredMembers = uniqueMembers.filter((pet) => {
    if (!seenTotals.has(pet.stats.total)) {
      seenTotals.set(pet.stats.total, pet);
      return true;
    }
    return false;
  });

  const members = filteredMembers;
  const basePet = members.find((p) => p.id === baseId) || uniqueMembers.find((p) => p.id === baseId);

  return (
    <div>
      <button className="back-btn" onClick={() => navigate("/")}>
        ← 返回家族列表
      </button>

      {/* 家族信息 */}
      <div className="chain-detail-header">
        <div className="chain-detail-info">
          <h1 className="chain-detail-name">{basePet?.name || "未知"}家族</h1>
          <p className="chain-detail-desc" dangerouslySetInnerHTML={{
            __html: `共 ${members.length} 种形态${relatedChains.length > 1 ? `，包含 ${relatedChains.length} 个进化分支` : ''}${apexPet ? `，最强形态为 <strong>${apexPet.name}</strong>` : ''}`
          }}></p>
          {apexPet && (
            <div className="chain-detail-types">
              {[apexPet.type_primary, apexPet.type_secondary]
                .filter((t): t is PetType => t !== undefined)
                .map((t) => (
                  <span
                    key={t}
                    className="type-badge"
                    style={{ background: getTypeColor(t) }}
                  >
                    {t}
                  </span>
                ))}
            </div>
          )}
        </div>
      </div>

      {/* 进化分支信息 */}
      <div className="chain-detail-section">
        <h3>进化分支 ({relatedChains.length})</h3>
        <div className="branch-list">
          {relatedChains.map((chain, idx) => (
            <div key={chain.id} className="branch-item">
              <span className="branch-number">{idx + 1}.</span>
              <span className="branch-path">
                {chain.member_names.join(" → ")}
              </span>
              {chain.conditions && Object.keys(chain.conditions).length > 0 && (
                <span className="branch-conditions">
                  ({Object.entries(chain.conditions).map(([k, v]) => `${k} ${v}`).join(", ")})
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 精灵列表 */}
      <div className="chain-detail-section">
        <h3>家族成员 ({members.length})</h3>
        <div className="chain-pet-grid">
          {members.map((pet) => {
            const isApex = pet.id === apexPet?.id;
            const types = [pet.type_primary, pet.type_secondary].filter(
              (t): t is PetType => t !== undefined
            );

            return (
              <div
                key={pet.id}
                className={`chain-pet-card ${isApex ? "apex" : ""}`}
                onClick={() => navigate(`/pet/${pet.id}`)}
              >
                <div className="chain-pet-order">
                  {pet.id}
                  {isApex && <span className="apex-badge">顶</span>}
                </div>
                <div className="chain-pet-info">
                  <div className="chain-pet-name">{pet.name}</div>
                  <div className="chain-pet-types">
                    {types.map((t) => (
                      <span
                        key={t}
                        className="type-badge"
                        style={{ background: getTypeColor(t) }}
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                  <div className="chain-pet-total">种族值 {pet.stats.total}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}