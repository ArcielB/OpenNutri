const NUTRIENTS = [
    { key: 'moisture', label: 'Moisture', defaultUnit: 'g/100g' },
    { key: 'protein', label: 'Protein', defaultUnit: 'g/100g' },
    { key: 'fat', label: 'Fat', defaultUnit: 'g/100g' },
    { key: 'carbohydrate', label: 'Carbohydrate', defaultUnit: 'g/100g' },
    { key: 'ash', label: 'Ash', defaultUnit: 'g/100g' },
    { key: 'energy', label: 'Energy', defaultUnit: 'kcal/100g' },
    { key: 'fiber', label: 'Fiber', defaultUnit: 'g/100g' },
]

const UNIT_OPTIONS = ['g/100g', 'mg/100g', 'μg/100g', 'kcal/100g', '%']

export default function FoodItemForm({ index, data, onChange, onDelete }) {
    const handleNameChange = (e) => {
        onChange({ ...data, food_name: e.target.value })
    }

    const handleNutrientChange = (key, field, value) => {
        const updated = { ...data }
        if (field === 'value') {
            updated[key] = value === '' ? null : parseFloat(value)
        } else {
            updated[`${key}_unit`] = value
        }
        onChange(updated)
    }

    return (
        <div className="food-item-card">
            <div className="card-header">
                <h3>Food Item {index + 1}</h3>
                <button className="delete-btn" onClick={onDelete} title="Remove food item">
                    ✕
                </button>
            </div>

            <input
                className="food-name-input"
                type="text"
                placeholder="Food name (e.g., Trabzon ekmeği)"
                value={data.food_name || ''}
                onChange={handleNameChange}
            />

            <div className="nutrient-grid">
                {NUTRIENTS.map((nutrient) => (
                    <div className="nutrient-field" key={nutrient.key}>
                        <label>{nutrient.label}</label>
                        <div className="input-group">
                            <input
                                type="number"
                                step="any"
                                placeholder="—"
                                value={data[nutrient.key] ?? ''}
                                onChange={(e) =>
                                    handleNutrientChange(nutrient.key, 'value', e.target.value)
                                }
                            />
                            <select
                                value={data[`${nutrient.key}_unit`] || nutrient.defaultUnit}
                                onChange={(e) =>
                                    handleNutrientChange(nutrient.key, 'unit', e.target.value)
                                }
                            >
                                {UNIT_OPTIONS.map((u) => (
                                    <option key={u} value={u}>
                                        {u}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
