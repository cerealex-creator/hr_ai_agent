export default function Loading() {
  return (
    <div className="page-loading" aria-busy="true" aria-live="polite">
      <div className="page-loading-bar" />
      <p className="muted">Загрузка задач…</p>
      <div className="skeleton-block" />
      <div className="skeleton-block" />
    </div>
  );
}
