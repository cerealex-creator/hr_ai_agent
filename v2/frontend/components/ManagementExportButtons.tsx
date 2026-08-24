"use client";

import { useState } from "react";
import { getApiBase } from "@/lib/api";

export function ManagementExportButtons() {
  const [msg, setMsg] = useState<string | null>(null);

  function openHtml() {
    setMsg(null);
    window.open(`${getApiBase()}/api/v1/management/export/goals.html`, "_blank", "noopener,noreferrer");
  }

  function downloadDocx() {
    setMsg(null);
    // cookie-auth: same-origin navigate
    window.location.href = `${getApiBase()}/api/v1/management/export/goals.docx`;
    setMsg("Скачивание DOCX…");
  }

  return (
    <div className="mgmt-export-bar">
      <span className="muted">Экспорт (ранний превью):</span>
      <button type="button" className="mgmt-btn-secondary" onClick={openHtml}>
        Цели — HTML / PDF
      </button>
      <button type="button" className="mgmt-btn-secondary" onClick={downloadDocx}>
        Цели — Word
      </button>
      <span className="muted" style={{ fontSize: 12 }}>
        Оргсхема и инструкции — позже (когда появятся роли)
      </span>
      {msg ? <span className="ok">{msg}</span> : null}
    </div>
  );
}
