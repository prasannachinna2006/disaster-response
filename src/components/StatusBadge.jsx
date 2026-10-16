export default function StatusBadge({ children, tone }) {
  const inferredTone = tone || String(children).toLowerCase().replaceAll(' ', '-')
  return <span className={`badge badge-${inferredTone}`}>{children}</span>
}
