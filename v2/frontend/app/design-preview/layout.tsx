import type { ReactNode } from "react";

/** Изоляция preview от глобальных отступов body. */
export default function DesignPreviewLayout({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        margin: 0,
        padding: 0,
        minHeight: "100vh",
        width: "100%",
      }}
    >
      {children}
    </div>
  );
}
