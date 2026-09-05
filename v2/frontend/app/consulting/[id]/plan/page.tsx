"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import {
  approveConsultingPlan,
  getConsultingPlan,
  patchConsultingPlanItem,
  statusLabel,
  type ConsultingPlan,
} from "@/lib/consulting";

export default function ConsultingPlanPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [plan, setPlan] = useState<ConsultingPlan | null>(null);
  const [err, setErr] = useState<string | null>(null);

  function reload() {
    return getConsultingPlan(id).then(setPlan);
  }

  useEffect(() => {
    if (!id) return;
    reload().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  return (
    <ConsultingShell projectId={id} active="plan" title="План диагностики">
      {err ? <p className="consult-err">{err}</p> : null}
      {!plan ? (
        <p className="muted">Загрузка…</p>
      ) : (
        <>
          <p className="muted">
            Статус плана: {plan.plan_status === "approved" ? "утверждён" : "черновик"}. После утверждения чек-лист
            остаётся, пункты можно отмечать.
          </p>
          {plan.plan_status !== "approved" ? (
            <button
              type="button"
              className="mgmt-btn"
              onClick={() => approveConsultingPlan(id).then(setPlan).catch((e) => setErr(String(e)))}
            >
              Утвердить план
            </button>
          ) : null}
          <ul className="consult-checklist">
            {plan.items.map((item) => (
              <li key={item.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={item.status === "done"}
                    onChange={(e) =>
                      patchConsultingPlanItem(id, item.id, { status: e.target.checked ? "done" : "todo" })
                        .then(() => reload())
                        .catch((er) => setErr(String(er)))
                    }
                  />
                  <span>{item.title}</span>
                </label>
                <em>{statusLabel(item.status)}</em>
              </li>
            ))}
          </ul>
        </>
      )}
    </ConsultingShell>
  );
}
