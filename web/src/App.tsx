import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import HomePage from "./pages/HomePage";
import ChainDetailPage from "./pages/ChainDetailPage";
import PetDetailPage from "./pages/PetDetailPage";
import SkillPage from "./pages/SkillPage";
import TypeChartPage from "./pages/TypeChartPage";
import TeamBuilderPage from "./pages/TeamBuilderPage";
import AiBuilderPage from "./pages/AiBuilderPage";
import BattlePage from "./pages/BattlePage";
import MetaPage from "./pages/MetaPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/chain/:id" element={<ChainDetailPage />} />
        <Route path="/pet/:id" element={<PetDetailPage />} />
        <Route path="/skills" element={<SkillPage />} />
        <Route path="/type-chart" element={<TypeChartPage />} />
        <Route path="/team-builder" element={<TeamBuilderPage />} />
        <Route path="/ai-builder" element={<AiBuilderPage />} />
        <Route path="/battle" element={<BattlePage />} />
        <Route path="/meta" element={<MetaPage />} />
      </Routes>
    </Layout>
  );
}
