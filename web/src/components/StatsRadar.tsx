import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";

interface Props {
  stats: {
    hp: number;
    atk: number;
    defense: number;
    sp_atk: number;
    sp_def: number;
    speed: number;
  };
}

const LABELS: Record<string, string> = {
  hp: "生命",
  atk: "物攻",
  defense: "物防",
  sp_atk: "魔攻",
  sp_def: "魔防",
  speed: "速度",
};

export default function StatsRadar({ stats }: Props) {
  const data = Object.entries(stats)
    .filter(([key]) => key !== "total")
    .map(([key, value]) => ({
      name: LABELS[key] || key,
      value,
      fullMark: 150,
    }));

  return (
    <div className="radar-container">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke="#2a2a4a" />
          <PolarAngleAxis
            dataKey="name"
            tick={{ fill: "#888", fontSize: 11 }}
          />
          <Radar
            name="种族值"
            dataKey="value"
            stroke="#4fc3f7"
            fill="#4fc3f7"
            fillOpacity={0.2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
