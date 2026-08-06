"use client";

type Props = {
  msg?: string | null;
  err?: string | null;
  tone?: "success" | "warning" | "error";
};

const TONE_STYLES = {
  success: { border: "1px solid #3d8b6e", background: "rgba(61,139,110,0.12)" },
  warning: { border: "1px solid #b8860b", background: "rgba(184,134,11,0.14)" },
  error: { border: "1px solid #c45c5c", background: "rgba(196,92,92,0.12)" },
} as const;

/** Floating feedback near the section where the user just acted. */
export function ActionBanner({ msg, err, tone }: Props) {
  if (!msg && !err) return null;
  const resolvedTone = tone ?? (err ? "error" : "success");
  const style = TONE_STYLES[resolvedTone];
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
        border: style.border,
        background: style.background,
      }}
    >
      {err ? (
        <p className="warn" style={{ margin: 0, whiteSpace: "pre-wrap" }}>
          {err}
        </p>
      ) : null}
      {msg ? (
        <p
          className={resolvedTone === "warning" ? "warn" : "ok"}
          style={{ margin: 0, whiteSpace: "pre-wrap" }}
        >
          {msg}
        </p>
      ) : null}
    </div>
  );
}
