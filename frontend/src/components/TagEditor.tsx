import { KeyboardEvent, useState } from 'react'

interface Props {
  label: string
  value: string[]
  onChange: (value: string[]) => void
  placeholder?: string
  hint?: string
}

export default function TagEditor({ label, value, onChange, placeholder, hint }: Props) {
  const [draft, setDraft] = useState('')

  const add = () => {
    const item = draft.trim()
    if (!item) return
    if (!value.some((existing) => existing.toLocaleLowerCase() === item.toLocaleLowerCase())) {
      onChange([...value, item])
    }
    setDraft('')
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      add()
    }
  }

  return (
    <div className="field-group">
      <label>{label}</label>
      {hint && <p className="field-hint">{hint}</p>}
      <div className="tag-editor">
        <div className="tag-list">
          {value.map((tag) => (
            <span className="tag" key={tag}>
              {tag}
              <button type="button" aria-label={`حذف ${tag}`} onClick={() => onChange(value.filter((x) => x !== tag))}>
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="tag-input-row">
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            onBlur={add}
            placeholder={placeholder ?? 'اكتبي ثم اضغطي Enter'}
          />
          <button type="button" className="btn btn-soft btn-small" onClick={add}>
            إضافة
          </button>
        </div>
      </div>
    </div>
  )
}
