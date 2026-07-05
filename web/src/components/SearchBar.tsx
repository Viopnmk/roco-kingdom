import { useState } from "react";
import { useNavigate } from "react-router-dom";

interface Props {
  value: string;
  onChange: (val: string) => void;
}

export default function SearchBar({ value, onChange }: Props) {
  return (
    <div className="search-bar">
      <input
        type="text"
        placeholder="搜索精灵名称、编号、特性..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
