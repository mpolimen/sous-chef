const API_BASE = 'https://recipe-api-476979361711.us-central1.run.app'

export async function fetchRecipes() {
  const res = await fetch(`${API_BASE}/recipes`)
  if (!res.ok) throw new Error('Failed to fetch recipes')
  return res.json()
}

export async function fetchRecipe(name) {
  const res = await fetch(`${API_BASE}/recipes/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error('Recipe not found')
  return res.json()
}

export async function fetchMetrics() {
  const res = await fetch(`${API_BASE}/metrics`)
  if (!res.ok) throw new Error('Failed to fetch metrics')
  return res.json()
}
