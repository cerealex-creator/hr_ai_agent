"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import {
  addConsultingEtalon,
  getConsultingEtalon,
  patchConsultingEtalon,
  statusLabel,
  type ConsultingEtalonNode,
} from "@/lib/consulting";

export default function ConsultingEtalonPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [items, setItems] = useState<ConsultingEtalonNode[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");

  function reload() {
    return getConsultingEtalon(id).then((d) => setItems(d.items));
  }

  useEffect(() => {
    if (!id) return;
    reload().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  return (
    <ConsultingShell projectId={id} active="etalon" title="Целевой эталон">
      {err ? <p className="consult-err">{err}</p> : null}
      <p className="muted">
        Сравнение всегда с зафиксированной версией. «Не применимо» не участвует в разрывах. Мегамейд сюда не
        подмешивается сам.
      </p>
      <form
        className="consult-row"
        onSubmit={(e) => {
          e.preventDefault();
          if (!title.trim()) return;
          addConsultingEtalon(id, { title })
            .then(() => {
              setTitle("");
              return reload();
            })
            .catch((er) => setErr(er instanceof Error ? er.message : "Ошибка"));
        }}
      >
        <input placeholder="Свой узел эталона" value={title} onChange={(e) => setTitle(e.target.value)} />
        <button type="submit" className="mgmt-btn">
          Добавить
        </button>
      </form>
      <ul className="consult-registry">
        {items.map((n) => (
          <li key={n.id}>
            <div>
              <strong>{n.title}</strong>
              <p className="muted">
                {statusLabel(n.status)} · v{n.version}
                {n.source_megamaid_id ? " · из Мегамейд" : ""}
              </p>
              <p>{n.body}</p>
            </div>
            <div className="consult-actions">
              {n.status !== "locked" ? (
                <button
                  type="button"
                  className="consult-btn-secondary"
                  onClick={() =>
                    patchConsultingEtalon(id, n.id, { status: "locked" })
                      .then(() => reload())
                      .catch((e) => setErr(String(e)))
                  }
                >
                  Зафиксировать
                </button>
              ) : (
                <button
                  type="button"
                  className="consult-btn-secondary"
                  onClick={() =>
                    patchConsultingEtalon(id, n.id, { status: "draft" })
                      .then(() => reload())
                      .catch((e) => setErr(String(e)))
                  }
                >
                  Снять фиксацию
                </button>
              )}
              {n.status !== "na" ? (
                <button
                  type="button"
                  className="consult-btn-secondary"
                  onClick={() =>
                    patchConsultingEtalon(id, n.id, { status: "na" })
                      .then(() => reload())
                      .catch((e) => setErr(String(e)))
                  }
                >
                  Не применимо
                </button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </ConsultingShell>
  );
}
