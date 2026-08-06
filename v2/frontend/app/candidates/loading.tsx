export default function Loading() {
  return (
    <div className="page-loading" aria-busy="true" aria-live="polite">
      <div className="page-loading-bar" />
      <p className="muted">Загрузка кандидатов…</p>
      <div className="skeleton-block" />
      <div className="skeleton-block skeleton-block-short" />
    </div>
  );
}
