import { NavLink } from "react-router-dom";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <nav className="nav">
        <span className="nav-title">洛克王国：世界 图鉴</span>
        <div className="nav-links">
          <NavLink to="/" end className={({ isActive }) => isActive ? "active" : ""}>
            精灵
          </NavLink>
          <NavLink to="/skills" className={({ isActive }) => isActive ? "active" : ""}>
            技能
          </NavLink>
          <NavLink to="/type-chart" className={({ isActive }) => isActive ? "active" : ""}>
            属性克制
          </NavLink>
          <NavLink to="/team-builder" className={({ isActive }) => isActive ? "active" : ""}>
            编队
          </NavLink>
          <NavLink to="/ai-builder" className={({ isActive }) => isActive ? "active" : ""}>
            AI配队
          </NavLink>
        </div>
      </nav>
      <main className="container">{children}</main>
    </>
  );
}
