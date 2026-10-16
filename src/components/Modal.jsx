import { useEffect } from 'react'
import { AlertTriangle, X } from 'lucide-react'

export default function Modal({ title, description, confirmLabel = 'Confirm', onConfirm, onClose, tone = 'default', busy = false }) {
  useEffect(() => {
    const closeOnEscape = (event) => event.key === 'Escape' && !busy && onClose()
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [busy, onClose])

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <button className="icon-button modal-close" type="button" aria-label="Close dialog" onClick={onClose} disabled={busy}><X size={18} /></button>
        <div className={`modal-icon ${tone}`}><AlertTriangle size={21} /></div>
        <h2 id="confirm-title">{title}</h2>
        <p>{description}</p>
        <div className="modal-actions">
          <button className="button button-secondary" type="button" onClick={onClose} disabled={busy}>Cancel</button>
          <button className={`button ${tone === 'danger' ? 'button-danger' : 'button-primary'}`} type="button" onClick={onConfirm} disabled={busy}>{confirmLabel}</button>
        </div>
      </section>
    </div>
  )
}
