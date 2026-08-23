"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  createMgmtGoal,
  createMgmtLink,
  createMgmtPosition,
  createMgmtTask,
  fetchMgmtGoalDimensions,
  fetchMgmtOverview,
  type MgmtGoalDimension,
  type MgmtOverview,
} from "@/lib/management";

export function ManagementExpertPanel() {
  const [data, setData] = useState<MgmtOverview | null>(null);
  const [dimensions, setDimensions] = useState<MgmtGoalDimension[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [goalTitle, setGoalTitle] = useState("");
  const [goalUnit, setGoalUnit] = useState("");
  const [baselineValue, setBaselineValue] = useState("");
  const [targetValue, setTargetValue] = useState("");
  const [selectedDims, setSelectedDims] = useState<string[]>([]);
  const [primaryDim, setPrimaryDim] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [posTitle, setPosTitle] = useState("");
  const [linkKind, setLinkKind] = useState("decomposes");
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");

  const reload = useCallback(async () => {
    setErr(null);
    try {
      const [overview, dims] = await Promise.all([fetchMgmtOverview(), fetchMgmtGoalDimensions()]);
      setData(overview);
      setDimensions(dims);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  function toggleDim(code: string) {
    setSelectedDims((prev) => {
      const next = prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code];
      if (!next.includes(primaryDim)) setPrimaryDim(next[0] || "");
      return next;
    });
  }

  async function onAddGoal(e: FormEvent) {
    e.preventDefault();
    if (!goalTitle.trim()) return;
    setMsg(null);
    try {
      await createMgmtGoal({
        title: goalTitle.trim(),
        metric_unit: goalUnit.trim() || null,
        baseline_value: baselineValue ? Number(baselineValue) : null,
        target_value: targetValue ? Number(targetValue) : null,
        metric_source: baselineValue || targetValue ? "owner" : null,
        dimension_codes: selectedDims,
        primary_dimension_code: primaryDim || null,
      });
      setGoalTitle("");
      setGoalUnit("");
      setBaselineValue("");
      setTargetValue("");
      setSelectedDims([]);
      setPrimaryDim("");
      setMsg("Цель добавлена");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onAddTask(e: FormEvent) {
    e.preventDefault();
    if (!taskTitle.trim()) return;
    setMsg(null);
    try {
      await createMgmtTask(taskTitle.trim());
      setTaskTitle("");
      setMsg("Задача добавлена");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onAddPosition(e: FormEvent) {
    e.preventDefault();
    if (!posTitle.trim()) return;
    setMsg(null);
    try {
      await createMgmtPosition(posTitle.trim());
      setPosTitle("");
      setMsg("Должность (as-is) добавлена");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onAddLink(e: FormEvent) {
    e.preventDefault();
    if (!sourceId || !targetId) return;
    setMsg(null);
    try {
      await createMgmtLink({
        source_type: "goal",
        source_id: targetId,
        target_type: "task",
        target_id: sourceId,
        link_kind: linkKind,
      });
      setMsg("Связь добавлена");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  if (!data && !err) return <p className="muted">Загрузка…</p>;

  return (
    <div className="mgmt-expert">
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {(data?.warnings || []).map((w) => (
        <p key={w} className="warn">
          {w}
        </p>
      ))}

      <section className="card-edit">
        <h2>Цели (L0)</h2>
        <form onSubmit={onAddGoal} className="mgmt-form-col">
          <input value={goalTitle} onChange={(e) => setGoalTitle(e.target.value)} placeholder="Название цели" />
          <div className="mgmt-form-row">
            <input
              value={baselineValue}
              onChange={(e) => setBaselineValue(e.target.value)}
              placeholder="Сейчас (baseline)"
              inputMode="decimal"
            />
            <input
              value={targetValue}
              onChange={(e) => setTargetValue(e.target.value)}
              placeholder="Цель (target)"
              inputMode="decimal"
            />
            <input value={goalUnit} onChange={(e) => setGoalUnit(e.target.value)} placeholder="Ед. изм." />
          </div>
          <fieldset className="mgmt-dimensions">
            <legend>Измерения (BSC)</legend>
            {dimensions.map((d) => (
              <label key={d.code} className="mgmt-dim-chip">
                <input type="checkbox" checked={selectedDims.includes(d.code)} onChange={() => toggleDim(d.code)} />
                {d.icon ? `${d.icon} ` : ""}
                {d.title}
              </label>
            ))}
            {selectedDims.length > 1 ? (
              <label>
                Основное измерение
                <select value={primaryDim} onChange={(e) => setPrimaryDim(e.target.value)}>
                  {selectedDims.map((code) => {
                    const d = dimensions.find((x) => x.code === code);
                    return (
                      <option key={code} value={code}>
                        {d?.title || code}
                      </option>
                    );
                  })}
                </select>
              </label>
            ) : null}
          </fieldset>
          <button type="submit">Добавить</button>
        </form>
        <ul className="mgmt-list">
          {(data?.goals || []).map((g) => (
            <li key={g.id}>
              <strong>{g.title}</strong>
              {g.dimensions?.length ? (
                <span className="muted">
                  {" "}
                  · {(g.dimensions || []).map((d) => d.title).join(", ")}
                </span>
              ) : null}
              {g.baseline_value != null || g.target_value != null ? (
                <span className="muted">
                  {" "}
                  · {g.baseline_value ?? "—"} → {g.target_value ?? "—"}
                  {g.metric_unit ? ` ${g.metric_unit}` : ""}
                  {g.numeric_gap != null ? ` (разрыв ${g.numeric_gap})` : ""}
                </span>
              ) : null}
              <span className="muted"> · {g.status}</span>
              <code className="mgmt-id">{g.id.slice(0, 8)}</code>
            </li>
          ))}
        </ul>
      </section>

      <section className="card-edit">
        <h2>Задачи (L1)</h2>
        <form onSubmit={onAddTask} className="mgmt-form-row">
          <input value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} placeholder="Название задачи" />
          <button type="submit">Добавить</button>
        </form>
        <ul className="mgmt-list">
          {(data?.tasks || []).map((t) => (
            <li key={t.id}>
              <strong>{t.title}</strong>
              <code className="mgmt-id">{t.id.slice(0, 8)}</code>
            </li>
          ))}
        </ul>
      </section>

      <section className="card-edit">
        <h2>Текущие должности (as-is)</h2>
        <form onSubmit={onAddPosition} className="mgmt-form-row">
          <input value={posTitle} onChange={(e) => setPosTitle(e.target.value)} placeholder="Название должности" />
          <button type="submit">Добавить</button>
        </form>
        <ul className="mgmt-list">
          {(data?.current_positions || []).map((p) => (
            <li key={p.id}>{p.title} · headcount {p.headcount}</li>
          ))}
        </ul>
      </section>

      <section className="card-edit">
        <h2>Связь цель → задача</h2>
        <form onSubmit={onAddLink} className="mgmt-form-col">
          <label>
            Задача (потомок)
            <select value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
              <option value="">—</option>
              {(data?.tasks || []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title.slice(0, 40)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Цель (родитель)
            <select value={targetId} onChange={(e) => setTargetId(e.target.value)}>
              <option value="">—</option>
              {(data?.goals || []).map((g) => (
                <option key={g.id} value={g.id}>
                  {g.title.slice(0, 40)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Тип связи
            <select value={linkKind} onChange={(e) => setLinkKind(e.target.value)}>
              <option value="decomposes">decomposes</option>
              <option value="implements">implements</option>
              <option value="measures">measures</option>
              <option value="references">references</option>
            </select>
          </label>
          <button type="submit">Создать связь</button>
        </form>
      </section>
    </div>
  );
}
