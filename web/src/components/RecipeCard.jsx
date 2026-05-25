import { useNavigate } from 'react-router-dom'

const CATEGORY_EMOJI = {
  Main:        '🍽️',
  Soup:        '🍲',
  Dessert:     '🍰',
  Breakfast:   '🍳',
  Snack:       '🥨',
  Vegetarian:  '🥦',
  Other:       '🥘',
}

function Stars({ rating }) {
  const n = parseFloat(rating)
  if (!n) return null
  return (
    <div className="card-rating">
      <span>★</span>
      <span>{n.toFixed(1)}</span>
    </div>
  )
}

export default function RecipeCard({ recipe }) {
  const navigate = useNavigate()
  const emoji = CATEGORY_EMOJI[recipe.category] || '🥘'
  const totalTime = (parseInt(recipe.prep_time) || 0) + (parseInt(recipe.cook_time) || 0)

  return (
    <div className="recipe-card" onClick={() => navigate(`/recipe/${encodeURIComponent(recipe.name)}`)}>
      <div className="card-header">
        <span className="card-header-emoji">{emoji}</span>
        <div className="card-name">{recipe.name}</div>
      </div>
      <div className="card-body">
        <Stars rating={recipe.rating} />
        <span className="badge">{recipe.category || 'Other'}</span>
        <div className="card-meta">
          {totalTime > 0 && (
            <span className="card-meta-item">⏱ {totalTime} min</span>
          )}
          {recipe.servings && (
            <span className="card-meta-item">🍴 {recipe.servings} servings</span>
          )}
          {recipe.date && (
            <span className="card-meta-item">📅 {recipe.date}</span>
          )}
        </div>
      </div>
    </div>
  )
}
