import { useState, useEffect, useMemo } from 'react'
import { fetchRecipes } from '../api'
import RecipeCard from './RecipeCard'

const SORT_OPTIONS = [
  { value: 'newest',    label: 'Newest' },
  { value: 'rating',    label: 'Rating ↓' },
  { value: 'time',      label: 'Fastest' },
]

const TIME_FILTERS = [
  { value: 'all',  label: 'Any time' },
  { value: '30',   label: '≤ 30 min' },
  { value: '60',   label: '≤ 60 min' },
  { value: '90',   label: '≤ 90 min' },
]

export default function RecipeGrid() {
  const [recipes, setRecipes]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [search, setSearch]     = useState('')
  const [timeFilter, setTime]   = useState('all')
  const [sort, setSort]         = useState('newest')

  useEffect(() => {
    fetchRecipes()
      .then(setRecipes)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    let list = recipes.filter(r => {
      const matchesSearch = r.name.toLowerCase().includes(search.toLowerCase())
      const totalTime = (parseInt(r.prep_time) || 0) + (parseInt(r.cook_time) || 0)
      const matchesTime = timeFilter === 'all' || (totalTime > 0 && totalTime <= parseInt(timeFilter))
      return matchesSearch && matchesTime
    })

    if (sort === 'rating') {
      list = [...list].sort((a, b) => (parseFloat(b.rating) || 0) - (parseFloat(a.rating) || 0))
    } else if (sort === 'time') {
      list = [...list].sort((a, b) => {
        const ta = (parseInt(a.prep_time) || 0) + (parseInt(a.cook_time) || 0)
        const tb = (parseInt(b.prep_time) || 0) + (parseInt(b.cook_time) || 0)
        return (ta || 999) - (tb || 999)
      })
    }
    // 'newest' keeps the natural order from the API (appended order)

    return list
  }, [recipes, search, timeFilter, sort])

  if (loading) return <div className="spinner" />
  if (error) return <div className="centered"><p className="error-msg">⚠ {error}</p></div>

  return (
    <div>
      <h1 className="page-title">Recipe Book</h1>
      <p className="page-subtitle">{recipes.length} recipe{recipes.length !== 1 ? 's' : ''} saved</p>

      <div className="grid-controls">
        <input
          className="search-input"
          type="text"
          placeholder="Search recipes…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="filter-row">
          <div className="filter-pills">
            {TIME_FILTERS.map(f => (
              <button
                key={f.value}
                className={'pill' + (timeFilter === f.value ? ' active' : '')}
                onClick={() => setTime(f.value)}
              >
                {f.label}
              </button>
            ))}
          </div>
          <select
            className="sort-select"
            value={sort}
            onChange={e => setSort(e.target.value)}
          >
            {SORT_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="recipe-grid">
        {filtered.length === 0 ? (
          <div className="empty-state">
            <p>🍽️</p>
            <p>No recipes found</p>
          </div>
        ) : (
          filtered.map(r => <RecipeCard key={r.name} recipe={r} />)
        )}
      </div>
    </div>
  )
}
