import { useState, useEffect } from 'react'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { fetchMetrics } from '../api'

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
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    fetchMetrics()
      .then(setMetrics)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="spinner" />
  if (error)   return <div className="centered"><p className="error-msg">⚠ {error}</p></div>
  if (!metrics) return null

  // Cuisine pie data (from meal log)
  const cuisinePieData = Object.entries(metrics.meals_by_cuisine || {})
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)

  // Ratings bar data from metrics endpoint
  const ratingsData = Object.entries(metrics.ratings_distribution || {})
    .map(([name, count]) => ({ name: `★${name}`, count }))

  // Monthly recipes
  const monthlyData = Object.entries(metrics.by_month || {}).map(([month, count]) => ({
    name: month.slice(5),
    count,
  }))

  // Monthly meals
  const monthlyMealsData = Object.entries(metrics.meals_by_month || {}).map(([month, count]) => ({
    name: month.slice(5),
    count,
  }))

  // Monthly HT savings
  const htSavingsData = Object.entries(metrics.monthly_ht_savings || {}).map(([month, savings]) => ({
    name: month.slice(5),
    savings,
  }))

  const topCuisine = cuisinePieData[0]?.name

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
          label="Top Cuisine"
          value={topCuisine ?? '—'}
          sub={topCuisine ? `${metrics.meals_by_cuisine[topCuisine]} meals` : null}
        />
        <KpiCard
          label="This Month"
          value={(() => {
            const thisMonth = new Date().toISOString().slice(0, 7)
            return metrics.by_month?.[thisMonth] ?? 0
          })()}
          sub="recipes logged"
        />
        <KpiCard label="Meals Cooked" value={metrics.total_meals ?? 0} sub="times cooked" />
        <KpiCard
          label="HT Savings"
          value={`$${(metrics.total_ht_savings ?? 0).toFixed(2)}`}
          sub="from flyer deals"
        />
      </div>

      <div className="charts-grid">
        {/* Cuisine breakdown */}
        {cuisinePieData.length > 0 && (
          <div className="chart-card">
            <div className="chart-title">Meals by Cuisine</div>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={cuisinePieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  innerRadius={50}
                  paddingAngle={3}
                >
                  {cuisinePieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => [`${v} meals`, '']} />
                <Legend iconType="circle" iconSize={10} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

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

        {/* Monthly HT savings */}
        {htSavingsData.length > 0 && (
          <div className="chart-card">
            <div className="chart-title">Monthly HT Savings</div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={htSavingsData} barSize={28}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12 }} width={40} tickFormatter={(v) => `$${v}`} />
                <Tooltip cursor={{ fill: 'var(--accent-light)' }} formatter={(v) => [`$${v.toFixed(2)}`, 'Saved']} />
                <Bar dataKey="savings" fill="var(--gold)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Monthly recipes */}
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

        {/* Monthly meals cooked */}
        {monthlyMealsData.length > 0 && (
          <div className="chart-card full-width">
            <div className="chart-title">Meals Cooked by Month</div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={monthlyMealsData} barSize={28}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 12 }} width={24} />
                <Tooltip cursor={{ fill: 'var(--accent-light)' }} formatter={(v) => [v, 'Meals']} />
                <Bar dataKey="count" fill="var(--accent)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
