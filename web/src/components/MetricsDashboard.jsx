import { useState, useEffect } from 'react'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { fetchMetrics, fetchRecipes } from '../api'

const COLORS = ['#4A7C59', '#C8874A', '#7C9E8A', '#E8A87C', '#2D5940', '#9BB5A3', '#B8834A', '#D4B896']

function KpiCard({ label, value, sub }) {
  return (
    <div className="kpi-card">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value ?? '—'}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  )
}

export default function MetricsDashboard() {
  const [metrics, setMetrics] = useState(null)
  const [recipes, setRecipes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    Promise.all([fetchMetrics(), fetchRecipes()])
      .then(([m, r]) => { setMetrics(m); setRecipes(r) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="spinner" />
  if (error)   return <div className="centered"><p className="error-msg">⚠ {error}</p></div>
  if (!metrics) return null

  // Category pie data
  const categoryData = Object.entries(metrics.by_category || {})
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)

  // Ratings bar data: count recipes by integer rating bucket
  const ratingBuckets = { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 }
  recipes.forEach(r => {
    const n = Math.round(parseFloat(r.rating))
    if (n >= 1 && n <= 5) ratingBuckets[String(n)]++
  })
  const ratingsData = Object.entries(ratingBuckets).map(([name, count]) => ({ name: `★${name}`, count }))

  // Monthly activity
  const monthlyData = Object.entries(metrics.by_month || {}).map(([month, count]) => ({
    name: month.slice(5),  // "MM" from "YYYY-MM"
    count,
  }))

  // Top category
  const topCategory = categoryData[0]?.name

  return (
    <div>
      <h1 className="page-title">Metrics</h1>
      <p className="page-subtitle">Your recipe book at a glance</p>

      <div className="kpi-grid">
        <KpiCard label="Total Recipes" value={metrics.total_recipes} />
        <KpiCard
          label="Avg Rating"
          value={metrics.avg_rating ? `★ ${metrics.avg_rating}` : null}
          sub="out of 5"
        />
        <KpiCard
          label="Top Category"
          value={topCategory}
          sub={topCategory ? `${metrics.by_category[topCategory]} recipes` : null}
        />
        <KpiCard
          label="This Month"
          value={(() => {
            const thisMonth = new Date().toISOString().slice(0, 7)
            return metrics.by_month?.[thisMonth] ?? 0
          })()}
          sub="recipes logged"
        />
      </div>

      <div className="charts-grid">
        {/* Category breakdown */}
        <div className="chart-card">
          <div className="chart-title">Recipes by Category</div>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={categoryData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={90}
                innerRadius={50}
                paddingAngle={3}
              >
                {categoryData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [`${v} recipes`, '']} />
              <Legend iconType="circle" iconSize={10} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Ratings distribution */}
        <div className="chart-card">
          <div className="chart-title">Ratings Distribution</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={ratingsData} barSize={32}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 13 }} />
              <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 12 }} width={24} />
              <Tooltip cursor={{ fill: 'var(--accent-light)' }} formatter={(v) => [v, 'Recipes']} />
              <Bar dataKey="count" fill="var(--accent)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Monthly activity */}
        {monthlyData.length > 0 && (
          <div className="chart-card full-width">
            <div className="chart-title">Recipes Logged by Month</div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={monthlyData} barSize={28}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 12 }} width={24} />
                <Tooltip cursor={{ fill: 'var(--accent-light)' }} formatter={(v) => [v, 'Recipes']} />
                <Bar dataKey="count" fill="var(--gold)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
