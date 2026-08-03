"use client";

type Props = {
  msg?: string | null;
  err?: string | null;
};

/** Floating feedback near the section where the user just acted. */
export function ActionBanner({ msg, err }: Props) {
  if (!msg && !err) return null;
  return (
    <div
      className="action-banner"
      role="status"
      style={{
        position: "sticky",
        top: "0.5rem",
        zIndex: 20,
        margin: "0 0 0.75rem",
        padding: "0.55rem 0.75rem",
        borderRadius: "8px",
        border: err ? "1px solid #c45c5c" : "1px solid #3d8b6e",
        background: err ? "rgba(196,92,92,0.12)" : "rgba(61,139,110,0.12)",
      }}
    >
      {err ? <p className="warn" style={{ margin: 0 }}>{err}</p> : null}
      {msg ? <p className="ok" style={{ margin: 0 }}>{msg}</p> : null}
    </div>
  );
}
