import FoodAutocomplete from './FoodAutocomplete'
import NutrientAutocomplete from './NutrientAutocomplete'

const UNIT_OPTIONS = ['g/100g', 'mg/100g', 'μg/100g', 'kcal/100g', 'kJ/100g', 'IU/100g', '%']

export default function FoodItemForm({ index, data, onChange, onDelete, allNutrients, allFoods, foodsLoaded, userId }) {
    const nutrients = data.nutrients || []
    const addedNutrientIds = new Set(nutrients.map((n) => n.nutrient_id).filter(Boolean))

    const handleFoodChange = ({ food_name, food_fdc_id, is_custom_food }) => {
        onChange({ ...data, food_name, food_fdc_id, is_custom_food })
    }

    const handleAddNutrient = (nutrientEntry) => {
        // Prevent duplicates
        if (nutrientEntry.nutrient_id && addedNutrientIds.has(nutrientEntry.nutrient_id)) return
        onChange({
            ...data,
            nutrients: [...nutrients, nutrientEntry],
        })
    }

    const handleNutrientValueChange = (idx, field, value) => {
        const updated = nutrients.map((n, i) => {
            if (i !== idx) return n
            if (field === 'value') {
                return { ...n, value: value === '' ? null : parseFloat(value) }
            }
            return { ...n, [field]: value }
        })
        onChange({ ...data, nutrients: updated })
    }

    const handleRemoveNutrient = (idx) => {
        onChange({
            ...data,
            nutrients: nutrients.filter((_, i) => i !== idx),
        })
    }

    return (
        <div className="food-item-card">
            <div className="card-header">
                <h3>Food Item {index + 1}</h3>
                <button className="delete-btn" onClick={onDelete} title="Remove food item">
                    ✕
                </button>
            </div>

            <FoodAutocomplete
                value={data.food_name}
                foodFdcId={data.food_fdc_id}
                onChange={handleFoodChange}
                allFoods={allFoods || []}
                foodsLoaded={foodsLoaded}
                userId={userId}
            />

            {/* Dynamic nutrient rows */}
            {nutrients.length > 0 && (
                <div className="nutrient-list">
                    {nutrients.map((n, idx) => (
                        <div className="nutrient-row" key={`${n.nutrient_id || n.nutrient_name}-${idx}`}>
                            <span className="nutrient-row-name">{n.nutrient_name}</span>
                            <input
                                type="number"
                                step="any"
                                placeholder="Value"
                                value={n.value ?? ''}
                                onChange={(e) =>
                                    handleNutrientValueChange(idx, 'value', e.target.value)
                                }
                                className="nutrient-row-value"
                            />
                            <select
                                value={n.unit}
                                onChange={(e) =>
                                    handleNutrientValueChange(idx, 'unit', e.target.value)
                                }
                                className="nutrient-row-unit"
                            >
                                {UNIT_OPTIONS.map((u) => (
                                    <option key={u} value={u}>{u}</option>
                                ))}
                            </select>
                            <button
                                className="nutrient-row-remove"
                                onClick={() => handleRemoveNutrient(idx)}
                                title="Remove nutrient"
                            >
                                ✕
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* Nutrient autocomplete */}
            <NutrientAutocomplete
                allNutrients={allNutrients || []}
                addedNutrientIds={addedNutrientIds}
                onAdd={handleAddNutrient}
                userId={userId}
            />
        </div>
    )
}
