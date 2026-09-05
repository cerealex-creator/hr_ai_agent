"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import {
  copyMegamaidToEtalon,
  getConsultingMegamaid,
  type ConsultingMegamaidNode,
} from "@/lib/consulting";

export default function ConsultingMegamaidPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [items, setItems] = useState<ConsultingMegamaidNode[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getConsultingMegamaid(id)
      .then((d) => setItems(d.items))
      .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  return (
    <ConsultingShell projectId={id} active="megamaid" title="Мегамейд">
      {err ? <p className="consult-err">{err}</p> : null}
      {msg ? <p className="consult-ok">{msg}</p> : null}
      <p className="muted">
        Отдельная библиотека, не эталон проекта. Для БЕ «не стройка» пакет сам не подмешивается. Кнопка «В эталон» —
        только ваше решение.
      </p>
      <ul className="consult-registry">
        {items.map((n) => (
          <li key={n.id}>
            <div>
              <strong>{n.title}</strong>
              <p className="muted">БЕ: {(n.be_tags || []).join(", ") || "—"}</p>
              <p>{n.body}</p>
            </div>
            <button
              type="button"
              className="consult-btn-secondary"
              onClick={() =>
                copyMegamaidToEtalon(id, n.id)
                  .then(() => setMsg(`«${n.title}» скопирован в эталон`))
                  .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"))
              }
            >
              Взять в эталон
            </button>
          </li>
        ))}
      </ul>
    </ConsultingShell>
  );
}
