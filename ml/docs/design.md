# 洛克王国配队助手 — 方案设计

> 状态：设计中，待用户确认后执行
> 最后更新：2026-06-16

---

## 一、目标

在现有精灵图鉴基础上，构建一个**交互式 AI 配队探索工具**：用户设定约束条件，系统搜索并推荐最优 6 精灵 × 4 技能队伍。

### 核心能力
1. 基于精灵特性 + 技能打击面 + 抗性面 + 有效种族值 + 技能联动，搜索最优配队
2. 可约束（必须包含某精灵、偏好某属性、某战术风格）
3. 可钻取（展开看为什么 A 和 B 联动好）
4. 可比较（多队并排对比）
5. 集成到现有 React 前端

---

## 二、整体架构

```
pets.json + skills.json + learnset.json + type_chart.json
数据来源: rocom.qq.com (官方) → BWIKI → 其他攻略站 (三级验证)
        │
        ▼
┌───────────────────────────┐
│ ① 技能解析器 (规则引擎)    │  离线，首次运行
│  - 结构化标注每技能        │
│  - synergy_tag 提取       │
│  - 有效种族值判定         │
│  输出: parsed_skills.json  │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ ② 精灵画像生成            │  离线，首次运行
│  - 每只精灵的特征向量      │
│  - 最优 4 技能配置         │
│  - 打击面/抗性面向量       │
│  输出: pet_profiles.json   │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ ③ 联动发现引擎            │  离线
│  - 技能文本 NLP embedding  │
│  - 战术聚类               │
│  - 联动链路图             │
│  输出: synergy_graph.json  │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ ④ 优化搜索引擎            │  在线（可缓存）
│  - 多目标遗传算法          │
│  - 帕累托前沿             │
│  - 约束过滤器             │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ ⑤ FastAPI 服务            │  在线
│  - /api/optimize          │
│  - /api/synergy           │
│  - /api/pet-profile       │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ ⑥ React 前端集成          │
│  - /ai-builder 新路由     │
│  - 约束面板 + 结果列表     │
│  - 联动钻取视图           │
└───────────────────────────┘
```

---

## 三、各模块详细设计

### 模块 1：技能解析器

对 494 个技能做规则化标注，输入技能 JSON，输出每技能的标签结构。

```python
@dataclass
class ParsedSkill:
    name: str
    type: str                          # 属性
    category: str                      # 物理/魔法/变化
    power: int
    energy: int
    accuracy: int

    # 标注字段
    is_attack: bool                    # 是否为攻击技（物理或魔法）
    attack_type: str | None            # "physical" / "magical" / None
    effective_stat: str | None         # "atk" / "sp_atk" / None（变化技为 None）

    has_counter_attack: bool           # 应对攻击分支
    has_counter_defense: bool          # 应对防御分支
    has_priority: bool                 # 先手
    priority_value: int                # 先手值（默认 0）
    has_charge: bool                   # 蓄力
    has_retreat: bool                  # 脱离
    has_transmission: bool             # 传动
    transmission_value: int

    applies_status: list[str]          # 施加的异常状态
    applies_buff: list[str]            # 施加的增益
    applies_debuff: list[str]          # 施加的减益
    has_weather: bool                  # 改变天气
    weather_type: str | None

    team_effects: list[str]            # 奉献/场下/借用等队伍效果
    synergy_tags: list[str]            # 联动标签

    effect_raw: str                    # 原始效果文本
```

标注方式：正则 + 关键词匹配。不依赖 ML。

#### synergy_tag 体系

| 标签 | 触发词 |
|------|--------|
| 灼烧 | 灼烧, 灼伤 |
| 中毒 | 中毒, 毒 |
| 冻结 | 冻结, 冰 |
| 星陨 | 星陨 |
| 萌化 | 萌化 |
| 能量操控 | 回能, 偷取, 失去能量, 能耗+ |
| 连击 | 连击 |
| 蓄力 | 蓄力 |
| 先手 | 先手 |
| 传动 | 传动 |
| 脱离 | 脱离, 替换 |
| 天气 | 暴风雪, 沙暴, 雨天, 天气 |
| 增益传递 | 继承增益, 奉献 |
| 吸血 | 吸血 |
| 打断 | 打断 |
| 减伤 | 减伤 |
| 印记 | 印记 |

---

### 模块 2：精灵画像生成

每只精灵生成一个特征对象：

```python
@dataclass
class PetProfile:
    id: int
    name: str
    type_primary: str
    type_secondary: str | None

    # 有效种族值（基于最优 4 技能判定）
    effective_atk: int       # 物攻有效值（如果携带了物理技能）
    effective_sp_atk: int    # 魔攻有效值
    effective_def: int       # 物防
    effective_sp_def: int    # 魔防
    effective_speed: int     # 速度（永远有效）
    effective_hp: int        # 生命（永远有效）

    # 职责分类
    role: str                # "物理输出"/"魔法输出"/"双刀"/"坦克"/"辅助"/"控场"/"天气手"

    # 最优 4 技能配置
    optimal_skills: list[str]  # 按有效种族值最大化选择的技能

    # 打击面向量（18维，对本精灵最优4技能覆盖的18种防御属性）
    coverage_vector: dict[str, float]

    # 抗性面向量（18维，本精灵被各属性攻击的受伤倍率）
    weakness_vector: dict[str, float]

    # 能量效率
    avg_energy_cost: float
    energy_recovery: float    # 是否有回能手段

    # 联动标签汇总
    synergy_tags: list[str]
```

#### 有效种族值计算

```
对一只精灵：
1. 从它的技能列表中，按攻击类型分组（物理组/魔法组/变化组）
2. 如果物攻 > 魔攻 → 选物理技能，有效物攻 = 物攻种族值，有效魔攻 ≈ 0
3. 如果魔攻 > 物攻 → 选魔法技能，有效魔攻 = 魔攻种族值，有效物攻 ≈ 0
4. 有效速度 = 速度种族值 × 0.9（如果性格减速）~ 1.1（性格加速）
5. 有效耐久 = HP × (物防 + 魔防) / 2

但需要进一步考虑：
- 如果精灵的物理技能质量远高于魔法（威力高、效果好），即使魔攻更高也可能选择物理
- 所以先做最优 4 技能选择，反推有效种族值
```

#### 职责分类逻辑

| 条件 | 职责 |
|------|------|
| 主要技能为变化技 + 有回血/减伤 | 坦克 |
| 主要技能为变化技 + 有增益/buff | 辅助 |
| 高攻 + 高威力攻击技 | 物理/魔法输出 |
| 有天气技 | 天气手 |
| 有大量异常状态技 | 控场 |
| 高速 + 先手技 | 高速游击 |

---

### 模块 3：联动发现引擎

#### NLP 聚类
- 使用 `paraphrase-multilingual-MiniLM-L12-v2` 对技能效果文本做 embedding
- 在嵌入空间聚类，发现战术模式（灼烧体系/冻结控场/星陨爆发/传动体系等）

#### 精灵-技能超图
```
超图：精灵 → 技能（通过 learnset.json）
边权重：如果 A 精灵的技能施加灼烧，B 精灵的技能"灼烧翻倍"→ 联动权重 += X
       如果 A 和 B 共享某一异常状态的完整性（A 上 → B 引爆 → C 获益）→ 联动权重 ++
```

输出：每对精灵之间的联动得分矩阵（375×375）。

---

### 模块 4：优化搜索引擎

#### 编码
```
染色体 = [(pet_id_1, [skill_1, skill_2, skill_3, skill_4]), ...  ×6]
```

#### 适应度函数（多目标）

| 目标 | 权重 | 计算方式 |
|------|------|----------|
| 打击面覆盖 | 高 | 18 属性 × 最大克制倍率，方差惩罚 |
| 抗性互补 | 高 | 无共同 ≥2× 弱点 +1，有 4× 共同弱点 -1 |
| 有效种族值利用率 | 中 | Σ(每个精灵的 effective_damage_stat / 总种族值) |
| 联动得分 | 中 | Σ(精灵对之间 synergy_tag 匹配度) / C(6,2) |
| 速度梯度 | 低 | 速度方差适中（不要太集中也别太分散） |
| 职责平衡 | 中 | 输出:坦克:辅助 接近 3:2:1 |
| 能量平衡 | 低 | Σ(avg_energy_cost) < 阈值 |

#### 遗传算法
```
种群大小: 300
代数: 200
交叉: 队伍间交换精灵（保持技能选择）
变异: 随机替换 1 只精灵或 1 个技能
精英保留: Top 10%
帕累托排序: NSGA-II 多目标
```

#### 约束支持
- must_include: [pet_id] — 必须包含的精灵
- must_exclude: [pet_id] — 不能包含的精灵
- prefer_type: str — 偏好属性
- style: str — 战术风格（灼烧体系/高速快攻/消耗/平衡）
- min_coverage: float — 最少打击面覆盖率

---

### 模块 5：FastAPI 服务

```
POST /api/optimize
Body: {
  "must_include": [1, 5],        // 可选
  "must_exclude": [],             // 可选
  "prefer_type": "火",            // 可选
  "style": "灼烧体系",            // 可选
  "top_k": 10
}
Response: {
  "teams": [
    {
      "team": [{pet_id, name, skills, ...}, ×6],
      "scores": {coverage, defense, synergy, ...},
      "synergy_highlights": ["A的引燃 → B的充分燃烧", ...]
    }, ...
  ],
  "pareto_front": [...]
}

GET /api/pet/{id}/profile
GET /api/synergy/{pet_id_a}/{pet_id_b}
```

---

### 模块 6：前端集成

在 `web/src/` 新增：

```
src/pages/AiBuilderPage.tsx    — 配队助手主页
src/components/TeamCard.tsx     — 队伍卡片（精灵列表+雷达图+联动说明）
src/components/ConstraintPanel.tsx — 约束设置面板
```

路由：`/ai-builder`

UI 布局：
```
┌─────────────────────────────────────────┐
│  约束面板（可折叠）                       │
│  必须: [__] 排除: [__] 风格: [灼烧▼]    │
│  [搜索最优配队]                           │
├─────────────────────────────────────────┤
│  结果列表                                │
│  ┌──────┐ ┌──────┐ ┌──────┐            │
│  │Team 1│ │Team 2│ │Team 3│  ...       │
│  │综合S │ │打击A │ │抗性S │            │
│  │联动🔥│ │联动❄️│ │联动⭐│            │
│  └──────┘ └──────┘ └──────┘            │
│  [展开详情] → 精灵详情+联动链路说明       │
│  [导入编队] → 跳转 /team-builder        │
└─────────────────────────────────────────┘
```

---

## 四、项目结构

```
洛克王国/
├── scraper/            (已有，不动)
├── web/                (已有，新增路由/组件)
└── ml/                 (新建)
    ├── pyproject.toml
    ├── requirements.txt
    ├── docs/
    │   ├── mechanics.md     ← 游戏机制参考
    │   └── design.md        ← 本文档
    ├── src/
    │   ├── __init__.py
    │   ├── parser/
    │   │   ├── skill_parser.py      # 技能结构化标注
    │   │   ├── effective_stats.py   # 有效种族值计算
    │   │   └── synergy_tagger.py    # synergy_tag 标注
    │   ├── profiles/
    │   │   └── build_profiles.py    # 精灵画像生成
    │   ├── discovery/
    │   │   ├── embed.py             # 技能文本 embedding
    │   │   ├── cluster.py           # 战术聚类
    │   │   └── graph.py             # 精灵-技能超图
    │   ├── optimize/
    │   │   ├── genetic.py           # 遗传算法
    │   │   ├── fitness.py           # 多目标适应度
    │   │   └── pareto.py            # 帕累托前沿
    │   └── api/
    │       ├── main.py              # FastAPI 入口
    │       ├── routes.py            # API 路由
    │       └── schemas.py           # Pydantic 模型
    ├── data/                        # 中间数据产出
    │   ├── parsed_skills.json
    │   ├── pet_profiles.json
    │   └── synergy_graph.json
    └── tests/
```

---

## 五、技术栈

| 层 | 技术 |
|-----|------|
| 规则引擎 | Python (dataclasses, re) |
| NLP | sentence-transformers (仅用于技能聚类) |
| 优化搜索 | DEAP / 自实现 NSGA-II |
| API | FastAPI + Pydantic v2 |
| 前端 | React + TypeScript (复用现有 Vite 项目) |

---

## 六、实现路线

| Phase | 内容 | 预计文件数 |
|-------|------|-----------|
| Phase 1 | 技能解析器 + synergy_tag 标注 | 3 |
| Phase 2 | 精灵画像生成 + 有效种族值 | 1 |
| Phase 3 | 联动发现 + NLP 聚类 | 3 |
| Phase 4 | 遗传算法搜索 + 适应度函数 | 3 |
| Phase 5 | FastAPI 服务 | 3 |
| Phase 6 | React 前端集成 | 3-4 |

按 Phase 1→6 顺序开发，每 Phase 可独立验证。
