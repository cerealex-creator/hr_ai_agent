"use client";

import { useState } from "react";
import {
  applyMgmtIndustryPack,
  completeMgmtWizardStep4,
  type MgmtIndustryPack,
} from "@/lib/management";

type Props = {
  packs: MgmtIndustryPack[];
  activePackId?: string | null;
  onApplied: () => Promise<void>;
};

export function IndustryPackStep({ packs, activePackId, onApplied }: Props) {
  const [selected, setSelected] = useState(activePackId || packs[0]?.id || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function onApply() {
    if (!selected) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await applyMgmtIndustryPack(selected);
      setMsg(
        `Пакет применён: ${r.goals_suggested} подсказок целей, ${r.roles_draft} ролей, ${r.process_steps_draft} шагов процессов`
      );
      await onApplied();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onComplete() {
    setBusy(true);
    setErr(null);
    try {
      await completeMgmtWizardStep4();
      setMsg("Шаг 4 завершён — сводка и разрыв");
      await onApplied();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mgmt-form-col">
      <p className="muted">
        Импорт типовых процессов, ролей и подсказок целей из пакета. Seeds со статусом «suggested» — не
        утверждаются автоматически.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      <div className="mgmt-pack-grid">
        {packs.map((p) => (
          <label key={p.id} className={`mgmt-pack-card${selected === p.id ? " is-active" : ""}`}>
            <input
              type="radio"
              name="pack"
              value={p.id}
              checked={selected === p.id}
              onChange={() => setSelected(p.id)}
            />
            <strong>{p.title}</strong>
            {p.description ? <span className="muted">{p.description}</span> : null}
          </label>
        ))}
      </div>
      <div className="mgmt-form-row">
        <button type="button" disabled={busy || !selected} onClick={() => void onApply()}>
          Применить пакет
        </button>
        <button type="button" disabled={busy || !activePackId} onClick={() => void onComplete()}>
          Далее — сводка
        </button>
      </div>
      {activePackId ? <p className="muted">Текущий пакет: {activePackId}</p> : null}
    </div>
  );
}
