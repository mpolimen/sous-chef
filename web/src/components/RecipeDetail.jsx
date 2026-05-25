import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchRecipe } from '../api'

function CheckIcon() {
  return (
    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="2,6 5,9 10,3" />
    </svg>
  )
}

export default function RecipeDetail() {
  const { name }                        = useParams()
  const navigate                        = useNavigate()
  const [recipe, setRecipe]             = useState(null)
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState(null)
  const [checked, setChecked]           = useState({})

  useEffect(() => {
    fetchRecipe(name)
      .then(data => { setRecipe(data); setChecked({}) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [name])

  const toggleIngredient = (i) =>
    setChecked(prev => ({ ...prev, [i]: !prev[i] }))

  if (loading) return <div className="spinner" />
  if (error)   return <div className="centered"><p className="error-msg">⚠ {error}</p></div>
  if (!recipe)  return null

  const totalTime = (parseInt(recipe.prep_time) || 0) + (parseInt(recipe.cook_time) || 0)

  return (
    <div>
      <button className="back-btn" onClick={() => navigate(-1)}>
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="10,3 5,8 10,13" />
        </svg>
        Back
      </button>

      <div className="detail-header">
        <span className="badge">{recipe.category}</span>
        <h1 className="detail-title">{recipe.name}</h1>
        <div className="detail-meta">
          {recipe.rating && (
            <div className="detail-meta-chip">
              <span>★</span> <span>{parseFloat(recipe.rating).toFixed(1)} / 5</span>
            </div>
          )}
          {recipe.servings && (
            <div className="detail-meta-chip">
              <span>🍴</span> <span>{recipe.servings} servings</span>
            </div>
          )}
          {recipe.prep_time && (
            <div className="detail-meta-chip">
              <span>⚡</span> <span>{recipe.prep_time} min prep</span>
            </div>
          )}
          {recipe.cook_time && (
            <div className="detail-meta-chip">
              <span>🔥</span> <span>{recipe.cook_time} min cook</span>
            </div>
          )}
          {totalTime > 0 && (
            <div className="detail-meta-chip">
              <span>⏱</span> <span>{totalTime} min total</span>
            </div>
          )}
        </div>
      </div>

      <div className="detail-body">
        {/* Ingredients */}
        <div className="ingredients-panel">
          <div className="detail-section-title">Ingredients</div>
          {recipe.ingredients?.length > 0 ? (
            recipe.ingredients.map((ing, i) => (
              <div
                key={i}
                className={'ingredient-item' + (checked[i] ? ' checked' : '')}
                onClick={() => toggleIngredient(i)}
              >
                <div className="ingredient-cb">
                  <CheckIcon />
                </div>
                <span className="ingredient-name">{ing.item}</span>
                {ing.quantity && <span className="ingredient-qty">{ing.quantity}</span>}
              </div>
            ))
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No ingredients listed.</p>
          )}
        </div>

        {/* Instructions + Notes */}
        <div>
          <div className="detail-section-title">Instructions</div>
          {recipe.instructions?.length > 0 ? (
            <ol className="instructions-list">
              {recipe.instructions.map((step, i) => (
                <li key={i} className="instruction-step">
                  <div className="step-number">{i + 1}</div>
                  <p className="step-text">{step}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No instructions listed.</p>
          )}

          {recipe.notes && (
            <div className="notes-box">
              <strong>Storage &amp; Reheating</strong>
              {recipe.notes}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
