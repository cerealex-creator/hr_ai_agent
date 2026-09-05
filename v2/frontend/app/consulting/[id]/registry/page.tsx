"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import {
  getConsultingRegistry,
  patchConsultingRegistry,
  statusLabel,
  type ConsultingRegistryRow,
} from "@/lib/consulting";

const NEXT: Record<string, { to: string; label: string }[]> = {
  draft: [{ to: "confirmed", label: "Подтвердить" }],
  recommended: [
    { to: "confirmed", label: "Подтвердить" },
    { to: "draft", label: "В черновик" },
  ],
  confirmed: [{ to: "sent", label: "Отдать заказчику" }],
  sent: [
    { to: "approved", label: "Заказчик утвердил" },
    { to: "disputed", label: "Оспорено заказчиком" },
  ],
  disputed: [{ to: "sent", label: "Снова отдать" }],
};

export default function ConsultingRegistryPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [items, setItems] = useState<ConsultingRegistryRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  function reload() {
    return getConsultingRegistry(id).then((d) => setItems(d.items));
  }

  useEffect(() => {
    if (!id) return;
    reload().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  return (
    <ConsultingShell projectId={id} active="registry" title="Единый реестр">
      {err ? <p className="consult-err">{err}</p> : null}
      <p className="muted">
        «Оспорено заказчиком» не возвращает строку в рекомендацию ИИ. Подтверждение остаётся.
      </p>
      {!items.length ? <p className="muted">Пока пусто — добавьте материалы в папки.</p> : null}
      <ul className="consult-registry">
        {items.map((row) => (
          <li key={row.id}>
            <div>
              <strong>{row.title}</strong>
              <p className="muted">
                {statusLabel(row.status)}
                {row.confidence ? ` · уверенность ${statusLabel(row.confidence)}` : ""}
              </p>
            </div>
            <div className="consult-actions">
              {(NEXT[row.status] || []).map((act) => (
                <button
                  key={act.to}
                  type="button"
                  className="consult-btn-secondary"
                  onClick={() =>
                    patchConsultingRegistry(id, row.id, { status: act.to })
                      .then(() => reload())
                      .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"))
                  }
                >
                  {act.label}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </ConsultingShell>
  );
}
