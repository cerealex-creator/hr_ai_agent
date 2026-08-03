export function Placeholder({
  title,
  body,
}: {
  path?: string;
  title: string;
  body: string;
}) {
  return (
    <div className="placeholder-card">
      <h1 className="page-title">{title}</h1>
      <p className="muted">{body}</p>
    </div>
  );
}
