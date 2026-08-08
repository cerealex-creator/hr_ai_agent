/** Inline «i» hint — hover/focus shows help text (no Client Component needed). */
export function InfoTip({ text, label = "Подсказка" }: { text: string; label?: string }) {
  return (
    <span className="info-tip">
      <button type="button" className="info-tip-btn" aria-label={label} title={text}>
        i
      </button>
      <span className="info-tip-bubble" role="tooltip">
        {text}
      </span>
    </span>
  );
}
