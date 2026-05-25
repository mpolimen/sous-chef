import { HashRouter, Routes, Route, NavLink } from 'react-router-dom'
import RecipeGrid from './components/RecipeGrid'
import RecipeDetail from './components/RecipeDetail'
import MetricsDashboard from './components/MetricsDashboard'

export default function App() {
  return (
    <HashRouter>
      <div className="app">
        <nav className="nav">
          <NavLink to="/" className="nav-logo">Sous Chef</NavLink>
          <div className="nav-links">
            <NavLink to="/" end className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}>
              Recipes
            </NavLink>
            <NavLink to="/metrics" className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}>
              Metrics
            </NavLink>
          </div>
        </nav>
        <main className="main">
          <Routes>
            <Route path="/" element={<RecipeGrid />} />
            <Route path="/recipe/:name" element={<RecipeDetail />} />
            <Route path="/metrics" element={<MetricsDashboard />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  )
}
