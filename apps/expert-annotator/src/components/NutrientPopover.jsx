import { useState, useEffect, useRef } from 'react'

const UNIT_OPTIONS = ['g/100g', 'mg/100g', 'μg/100g', 'kcal/100g', 'kJ/100g', 'IU/100g', '%']

export default function NutrientPopover({ nutrient, anchorRect, onAdd, onClose }) {
    const [value, setValue] = useState('')
    const [unit, setUnit] = useState(formatDefaultUnit(nutrient?.unit_name))
    const popoverRef = useRef(null)
    const inputRef = useRef(null)

    // Position the popover near the clicked highlight
    useEffect(() => {
        if (popoverRef.current && anchorRect) {
            const popover = popoverRef.current
            const popoverRect = popover.getBoundingClientRect()

            // Position below the anchor, centered horizontally
            let top = anchorRect.bottom + 8
            let left = anchorRect.left + (anchorRect.width / 2) - (popoverRect.width / 2)

            // Keep within viewport
            if (left < 8) left = 8
            if (left + popoverRect.width > window.innerWidth - 8) {
                left = window.innerWidth - popoverRect.width - 8
            }
            if (top + popoverRect.height > window.innerHeight - 8) {
                top = anchorRect.top - popoverRect.height - 8
            }

            popover.style.top = `${top}px`
            popover.style.left = `${left}px`
        }
    }, [anchorRect])

    // Focus input on open
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.focus()
        }
    }, [])

    // Close on outside click
    useEffect(() => {
        const handler = (e) => {
            if (popoverRef.current && !popoverRef.current.contains(e.target)) {
                onClose()
            }
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [onClose])

    // Close on Escape
    useEffect(() => {
        const handler = (e) => {
            if (e.key === 'Escape') onClose()
        }
        document.addEventListener('keydown', handler)
        return () => document.removeEventListener('keydown', handler)
    }, [onClose])

    const handleAdd = () => {
        onAdd({
            nutrient_id: nutrient.id,
            nutrient_name: nutrient.name,
            value: value === '' ? null : parseFloat(value),
            unit: unit,
        })
        onClose()
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault()
            handleAdd()
        }
    }

    if (!nutrient || !anchorRect) return null

    return (
        <div className="nutrient-popover" ref={popoverRef}>
            <div className="popover-header">
                <span className="popover-nutrient-name">{nutrient.name}</span>
                <button type="button" className="popover-close icon-only-btn" onClick={onClose}>
                    <span className="icon-x" aria-hidden="true" />
                    <span className="visually-hidden">Close</span>
                </button>
            </div>
            <div className="popover-body">
                <input
                    ref={inputRef}
                    type="number"
                    step="any"
                    placeholder="Value"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="popover-value-input"
                />
                <select
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    className="popover-unit-select"
                >
                    {UNIT_OPTIONS.map((u) => (
                        <option key={u} value={u}>{u}</option>
                    ))}
                </select>
            </div>
            <button className="popover-add-btn" onClick={handleAdd}>
                + Add
            </button>
        </div>
    )
}

function formatDefaultUnit(unitName) {
    if (!unitName) return 'g/100g'
    const u = unitName.toUpperCase()
    if (u === 'G') return 'g/100g'
    if (u === 'MG') return 'mg/100g'
    if (u === 'UG' || u === 'ΜG') return 'μg/100g'
    if (u === 'KCAL') return 'kcal/100g'
    if (u === 'KJ') return 'kJ/100g'
    if (u === 'IU') return 'IU/100g'
    return `${unitName}/100g`
}
