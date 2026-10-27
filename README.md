# 🏰 洛克王国：世界 — 精灵图鉴 & AI 配队引擎

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/React-18-61DAFB.svg" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-5.5-3178C6.svg" alt="TypeScript">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/ML-NLP%20%2B%20Genetic-orange.svg" alt="ML">
  <img src="https://img.shields.io/badge/Vite-5.4-646CFF.svg" alt="Vite">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

## 📖 项目简介

**洛克王国：世界** 的完整数据生态与 AI 工具链——从多源数据采集、结构化存储，到 React 交互式图鉴，再到基于 NLP 与遗传算法的 AI 配队推荐引擎。

> 🎯 **一句话**：爬取 465 只精灵 × 497 个技能的完整数据，构建精灵图鉴前端，并用 NLP + 遗传算法实现智能 PvP 配队搜索。

> 🔄 **2026-10-26 数据更新（fork 维护）**：对当前 BWIKI 重新爬取并重建全部数据——精灵 375 → 465 只、技能 494 → 497 个、学习面 20,671 条；进化链基于精灵页字段重建（210 条链，覆盖 445 只，20 只首领形态单列）；AI 配队完成第 4 轮训练（NLP 联动 + 战术聚类）。同时修复了清洗管道的三处缺陷（LCX 旧数据覆盖新数据、技能详情被占位条目冲空、两套编号混用撞号）。原项目作者 sssswei，本 fork 仅作数据更新与维护。
>
> 🌐 **2026-10-27 在线版**：已修复 GitHub Pages 部署（类型错误、子路径 base），图鉴在线可访：https://roco-kingdom-73v.pages.devAI； 配队已将 NSGA-II 引擎移植为浏览器本地版（`web/src/engine/`，Web Worker 运行），在线版无需后端即可搜索配队，Python 后端仍可本地运行、结果一致。另新增「对战模拟」页（简化规则回合制自动对战，粉丝自制、非官方机制）与「数据分析」页（基于引擎样本的出场率/热门组合/战术体系/打击面盲区统计）。

```
📊 数据层             🖥️ 展示层              🧠 AI 层
┌──────────┐      ┌──────────┐      ┌──────────────┐
│  Scraper  │ ───→ │  React   │ ←─── │  ML Engine   │
│ BWIKI API │      │ 图鉴/配队 │      │ NLP + 遗传   │
│ 多源验证  │      │ 属性克制  │      │ 联动发现     │
└──────────┘      └──────────┘      └──────────────┘
  465 精灵           交互式前端          AI 配队搜索
  497 技能           响应式设计          帕累托最优
```

## 🗂️ 项目结构

```
洛克王国/
├── scraper/                    # 🕷️ 数据采集层
│   ├── spiders/
│   │   ├── bwiki.py            # BWIKI MediaWiki API 爬虫（主数据源）
│   │   ├── lcx.py              # 第三方攻略站爬虫
│   │   ├── biubiu.py           # 外部攻略站爬虫
│   │   ├── rocom.py            # 官方站点信息爬虫
│   │   └── type_chart.py       # 属性克制表解析
│   ├── config.py               # 爬虫配置（数据源注册、字段映射）
│   ├── data/                   # 原始数据
│   └── output/                 # 结构化输出
│
├── web/                        # 🖥️ React 前端
│   ├── src/
│   │   ├── pages/
│   │   │   ├── HomePage.tsx         # 首页（精灵总览）
│   │   │   ├── PetDetailPage.tsx    # 精灵详情 + Radar 图
│   │   │   ├── SkillPage.tsx        # 技能浏览器
│   │   │   ├── TeamBuilderPage.tsx  # 配队编辑器
│   │   │   ├── AiBuilderPage.tsx    # AI 配队助手页面
│   │   │   ├── TypeChartPage.tsx    # 18属性克制表
│   │   │   └── ChainDetailPage.tsx  # 进化链查看器
│   │   ├── components/
│   │   │   ├── PetCard.tsx          # 精灵卡片
│   │   │   ├── SkillTable.tsx       # 技能表格
│   │   │   ├── StatsRadar.tsx       # 种族值雷达图 (Recharts)
│   │   │   ├── FilterPanel.tsx      # 多维筛选面板
│   │   │   ├── TeamCard.tsx         # 配队卡片
│   │   │   ├── ConstraintPanel.tsx  # AI 配队约束面板
│   │   │   ├── PetPicker.tsx        # 精灵选择器
│   │   │   └── EvolutionChainCard.tsx # 进化链卡片
│   │   ├── data/                    # 静态数据 (JSON)
│   │   │   ├── pets.json            # 465 精灵完整数据
│   │   │   ├── skills.json          # 497 技能完整数据
│   │   │   ├── learnset.json        # 精灵-技能学习关系
│   │   │   ├── type_chart.json      # 18×18 属性克制矩阵
│   │   │   └── evolution_chains.json # 进化链数据
│   │   ├── types/                   # TypeScript 类型定义
│   │   └── utils/
│   │       └── typeChart.ts         # 克制计算工具
│   ├── package.json
│   └── vite.config.ts
│
└── ml/                         # 🧠 AI 配队引擎
    ├── pyproject.toml
    ├── src/
    │   ├── parser/
    │   │   ├── skill_parser.py      # 技能结构化标注（规则引擎）
    │   │   ├── ability_tagger.py    # 特性/血脉标注
    │   │   └── synergy_tagger.py    # 联动标签提取
    │   ├── profiles/
    │   │   └── build_profiles.py    # 精灵画像生成
    │   ├── discovery/
    │   │   ├── embed.py             # 技能文本 NLP embedding
    │   │   ├── cluster.py           # 战术聚类
    │   │   └── graph.py             # 精灵-技能超图构建
    │   ├── optimize/
    │   │   ├── genetic.py           # NSGA-II 遗传算法
    │   │   └── fitness.py           # 多目标适应度函数
    │   ├── api/
    │   │   ├── main.py              # FastAPI 入口
    │   │   ├── routes.py            # API 路由
    │   │   └── schemas.py           # Pydantic 数据模型
    │   └── train.py                 # 离线训练入口
    ├── data/                        # 中间数据产出
    │   ├── parsed_skills.json       # 标注后的技能 (494)
    │   ├── pet_profiles.json        # 精灵特征向量 (375)
    │   ├── synergy_graph.json       # 联动关系图
    │   ├── tactical_clusters.json   # 战术聚类结果
    │   └── optimization_results.json # 优化搜索结果
    ├── docs/
    │   ├── design.md                # 架构设计文档
    │   └── mechanics.md             # 游戏机制参考
    └── tests/
```

## 🕷️ Scraper — 数据采集

### 数据源层次
| 等级 | 来源 | 说明 |
|------|------|------|
| L1 权威 | 腾讯官方站点 | 游戏特性确认，不宜直接爬取 |
| L2 主要 | BWIKI 社区百科 | 核心数据库，MediaWiki API |
| L3 备用 | 第三方攻略站 | 数据交叉验证 |

### 采集流程
```
精灵图鉴首页 → 提取所有精灵链接 → 逐个抓取 wikitext
                                        ↓
技能页面    → 解析技能模板参数   → 结构化输出
                                        ↓
属性克制表  → 18×18 矩阵解析     → type_chart.json
```

### 数据规模
- 🐾 **375 只精灵**（含不同形态）
- ⚡ **494 个技能**（含完整效果文本）
- 📊 **18 属性克制矩阵**
- 🔗 **完整进化链 + 技能学习关系**

## 🖥️ Web — React 前端

### 技术栈
| 技术 | 用途 |
|------|------|
| React 18 + TypeScript | 组件化框架 |
| Vite 5 | 构建工具 |
| React Router v6 | 路由 |
| Recharts | 种族值雷达图 |
| CSS Modules | 样式方案 |

### 页面功能
| 页面 | 路由 | 功能 |
|------|------|------|
| 🏠 首页 | `/` | 精灵总览、属性筛选、搜索 |
| 📋 精灵详情 | `/pet/:id` | 六维雷达图、技能列表、进化链 |
| ⚡ 技能浏览 | `/skills` | 494 技能搜索、属性筛选 |
| 🛠️ 配队构建 | `/team-builder` | 6精灵×4技能配队编辑 |
| 🤖 AI 配队 | `/ai-builder` | AI 约束搜索（预留接口） |
| 📊 属性克制 | `/type-chart` | 18×18 交互式克制表 |
| 🔗 进化链 | `/chain/:id` | 进化关系可视化 |

## 🧠 ML Engine — AI 配队引擎

### 架构概览
```
pets.json + skills.json + learnset.json + type_chart.json
        │
        ▼
┌─────────────────────────┐
│ ① 技能解析器（规则引擎） │  正则 + 关键词 → synergy_tag 标注
│  parsed_skills.json      │  15+ 标签：灼烧/中毒/能量操控/连击…
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ② 精灵画像生成           │  有效种族值 + 职责分类 + 打击面/抗性面
│  pet_profiles.json       │  物理输出/魔法输出/坦克/辅助/控场/天气手
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ③ 联动发现引擎           │  sentence-transformers embedding
│  synergy_graph.json      │  技能文本 NLP 聚类 + 超图构建
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ④ 优化搜索引擎           │  NSGA-II 多目标遗传算法
│  FastAPI 在线服务        │  种群 300 × 200 代 → 帕累托前沿
└─────────────────────────┘
```

### 适应度函数（7 维优化）
| 目标 | 权重 | 说明 |
|------|------|------|
| 🎯 打击面覆盖 | 高 | 18 属性 × 最大克制倍率 |
| 🛡️ 抗性互补 | 高 | 无共同 ≥2× 弱点加分 |
| 📈 有效种族值 | 中 | 物理/魔法最优分配 |
| 🔗 联动得分 | 中 | synergy_tag 匹配度 |
| ⚡ 速度梯度 | 低 | 速度方差适中 |
| ⚖️ 职责平衡 | 中 | 输出:坦克:辅助 ≈ 3:2:1 |
| 🔋 能量平衡 | 低 | 总能量消耗 < 阈值 |

### 遗传算法参数
- 种群大小: 300
- 迭代代数: 200
- 交叉: 队伍间交换精灵（技能选择保留）
- 变异: 随机替换精灵或技能
- 精英保留: Top 10%
- 算法: NSGA-II 帕累托排序

### API 接口
```
POST /api/optimize           # 约束搜索最优配队
GET  /api/pet/{id}/profile   # 精灵画像详情
GET  /api/synergy/{a}/{b}    # 精灵联动分析
```

## 🚀 快速开始

### 前端
```bash
cd web
npm install
npm run dev        # 开发模式 http://localhost:5173
npm run build      # 生产构建
```

### ML 引擎
```bash
cd ml
pip install -r requirements.txt
python src/train.py           # 离线：数据预处理 + 训练
uvicorn src.api.main:app      # 在线：启动 API 服务
```

## 📸 技术亮点

### 数据工程
- **多源爬虫架构**：可配置的数据源注册 + 三级验证，支持启用/禁用切换
- **MediaWiki API 解析**：wikitext 模板参数提取，鲁棒的错误处理
- **数据交叉验证**：官方信息确认社区数据正确性

### AI / ML
- **规则 + 统计混合**：技能标签用规则引擎（100% 准确），战术发现用 NLP embedding
- **NSGA-II 多目标优化**：7 维适应度函数，帕累托前沿输出非劣解集
- **超图建模**：精灵-技能关系建模为超图，捕获高阶联动模式

### 前端
- **完整 TypeScript 类型系统**：375 精灵 + 494 技能的完整类型覆盖
- **Recharts 雷达图**：种族值六维可视化
- **组件化设计**：可复用的 FilterPanel / PetPicker / SkillPicker

## 🔮 未来方向

- [ ] 配队对战模拟器（回合制 PvP 模拟）
- [ ] 实时 meta 数据分析
- [ ] 用户配队评分系统
- [ ] 更多 NLP 模型实验（聚类质量对比）
- [ ] CI/CD 数据自动更新

## 📄 License

MIT
