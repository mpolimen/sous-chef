import { useState, useEffect, useMemo } from 'react'
import { fetchRecipes } from '../api'
import RecipeCard from './RecipeCard'

export default function RecipeGrid() {
  const [recipes, setRecipes]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [search, setSearch]     = useState('')
  const [category, setCategory] = useState('All')

  useEffect(() => {
    fetchRecipes()
      .then(setRecipes)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const categories = useMemo(() => {
    const cats = [...new Set(recipes.map(r => r.category).filter(Boolean))]
    return ['All', ...cats.sort()]
  }, [recipes])

  const filtered = useMemo(() => {
    return recipes.filter(r => {
      const matchesCat    = category === 'All' || r.category === category
      const matchesSearch = r.name.toLowerCase().includes(search.toLowerCase())
      return matchesCat && matchesSearch
    })
  }, [recipes, search, category])

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
        <div className="filter-pills">
          {categories.map(cat => (
            <button
              key={cat}
              className={'pill' + (category === cat ? ' active' : '')}
              onClick={() => setCategory(cat)}
            >
              {cat}
            </button>
          ))}
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
