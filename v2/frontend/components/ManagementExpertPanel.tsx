"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { BusinessProfileForm } from "@/components/BusinessProfileForm";
import { GoalBlocksWizard } from "@/components/GoalBlocksWizard";
import { L3PreviewPanel } from "@/components/L3PreviewPanel";
import {
  approveAllMgmtGoalsDraft,
  approveAllMgmtTasksDraft,
  approveMgmtGate,
  approveMgmtGoal,
  approveMgmtL2aAll,
  approveMgmtL2bAll,
  approveMgmtTask,
  createMgmtGoal,
  createMgmtLink,
  createMgmtPosition,
  createMgmtTask,
  fetchMgmtGateSummary,
  fetchMgmtGoalBlocks,
  fetchMgmtGoalDimensions,
  fetchMgmtOverview,
  rejectMgmtGate,
  type MgmtGateSummary,
  type MgmtGoalBlock,
  type MgmtGoalDimension,
  type MgmtOverview,
} from "@/lib/management";

export function ManagementExpertPanel() {
  const [data, setData] = useState<MgmtOverview | null>(null);
  const [gates, setGates] = useState<MgmtGateSummary | null>(null);
  const [goalBlocks, setGoalBlocks] = useState<MgmtGoalBlock[]>([]);
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
      const [overview, dims, blocks, gateSummary] = await Promise.all([
        fetchMgmtOverview(),
        fetchMgmtGoalDimensions(),
        fetchMgmtGoalBlocks(),
        fetchMgmtGateSummary(),
      ]);
      setData(overview);
      setDimensions(dims);
      setGoalBlocks(blocks);
      setGates(gateSummary);
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

  async function onApproveGoal(id: string) {
    setMsg(null);
    try {
      await approveMgmtGoal(id);
      setMsg("Цель утверждена (L0)");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onApproveTask(id: string) {
    setMsg(null);
    try {
      await approveMgmtTask(id);
      setMsg("Задача утверждена (L1)");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onApproveAllGoals() {
    setMsg(null);
    try {
      const r = await approveAllMgmtGoalsDraft();
      setMsg(`Утверждено целей: ${r.approved_count}`);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onApproveAllTasks() {
    setMsg(null);
    try {
      const r = await approveAllMgmtTasksDraft();
      setMsg(`Утверждено задач: ${r.approved_count}`);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onRejectGoal(id: string) {
    setMsg(null);
    try {
      await rejectMgmtGate("goal", id);
      setMsg("Цель отклонена");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onRejectTask(id: string) {
    setMsg(null);
    try {
      await rejectMgmtGate("task", id);
      setMsg("Задача отклонена");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onApproveProcessMap(id: string) {
    setMsg(null);
    try {
      await approveMgmtGate("process_map", id);
      setMsg("Процесс утверждён (L2a)");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onApproveRole(id: string) {
    setMsg(null);
    try {
      await approveMgmtGate("role", id);
      setMsg("Роль утверждена (L2b)");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onApproveL2aAll() {
    setMsg(null);
    try {
      const r = await approveMgmtL2aAll();
      setMsg(`L2a утверждено процессов: ${r.approved_count}`);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onApproveL2bAll() {
    setMsg(null);
    try {
      const r = await approveMgmtL2bAll();
      setMsg(`L2b утверждено ролей: ${r.approved_count}`);
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
        <h2>Паспорт бизнеса</h2>
        <BusinessProfileForm showCompleteButton={false} />
      </section>

      <section className="card-edit">
        <h2>Цели по блокам BSC</h2>
        <GoalBlocksWizard blocks={goalBlocks} mode="expert" onReload={reload} />
      </section>

      <section className="card-edit">
        <h2>Цели (L0)</h2>
        {(data?.inherited_goals || []).length ? (
          <>
            <h3 className="muted">От холдинга (read-only)</h3>
            <ul className="mgmt-list">
              {data!.inherited_goals!.map((g) => (
                <li key={g.id}>
                  <strong>{g.title}</strong>
                  <span className="muted"> · холдинг · {g.status}</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
        <div className="mgmt-approve-row">
          <button type="button" className="mgmt-btn-secondary" onClick={() => void onApproveAllGoals()}>
            Утвердить все draft/suggested L0
          </button>
        </div>
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
              <span className={`mgmt-status mgmt-status-${g.status}`}> · {g.status}</span>
              <code className="mgmt-id">{g.id.slice(0, 8)}</code>
              {g.status === "draft" || g.status === "suggested" ? (
                <div className="mgmt-approve-row">
                  <button type="button" className="mgmt-btn-secondary" onClick={() => void onApproveGoal(g.id)}>
                    {g.status === "suggested" ? "Принять из пакета" : "Утвердить L0"}
                  </button>
                  <button type="button" className="mgmt-btn-secondary" onClick={() => void onRejectGoal(g.id)}>
                    Отклонить
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="card-edit">
        <h2>Задачи (L1)</h2>
        <div className="mgmt-approve-row">
          <button type="button" className="mgmt-btn-secondary" onClick={() => void onApproveAllTasks()}>
            Утвердить все draft/suggested L1
          </button>
        </div>
        <form onSubmit={onAddTask} className="mgmt-form-row">
          <input value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} placeholder="Название задачи" />
          <button type="submit">Добавить</button>
        </form>
        <ul className="mgmt-list">
          {(data?.tasks || []).map((t) => (
            <li key={t.id}>
              <strong>{t.title}</strong>
              <span className={`mgmt-status mgmt-status-${t.status}`}> · {t.status}</span>
              <code className="mgmt-id">{t.id.slice(0, 8)}</code>
              {t.status === "draft" || t.status === "suggested" ? (
                <div className="mgmt-approve-row">
                  <button type="button" className="mgmt-btn-secondary" onClick={() => void onApproveTask(t.id)}>
                    {t.status === "suggested" ? "Принять из пакета" : "Утвердить L1"}
                  </button>
                  <button type="button" className="mgmt-btn-secondary" onClick={() => void onRejectTask(t.id)}>
                    Отклонить
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <section className="card-edit">
        <h2>Процессы (L2a) и роли (L2b)</h2>
        <p className="muted">
          Ворота после отраслевого пакета. L2a блокируется, если у шага нет роли. На карте — режим ворот
          (клик по узлу).
        </p>
        <div className="mgmt-approve-row">
          <button type="button" className="mgmt-btn-secondary" onClick={() => void onApproveL2aAll()}>
            Утвердить все L2a
          </button>
          <button type="button" className="mgmt-btn-secondary" onClick={() => void onApproveL2bAll()}>
            Утвердить все L2b
          </button>
        </div>
        {gates ? (
          <p className="muted">
            Ждут: L2a {gates.l2a_pending} · L2b {gates.l2b_pending}
            {gates.suggested_goals ? ` · suggested целей ${gates.suggested_goals}` : ""}
          </p>
        ) : null}
        <h3>Процессы</h3>
        <ul className="mgmt-list">
          {(gates?.process_maps || []).map((pm) => (
            <li key={pm.id}>
              <strong>{pm.title}</strong>
              <span className={`mgmt-status mgmt-status-${pm.status}`}> · {pm.status}</span>
              {pm.status === "draft" || pm.status === "suggested" ? (
                <div className="mgmt-approve-row">
                  <button
                    type="button"
                    className="mgmt-btn-secondary"
                    onClick={() => void onApproveProcessMap(pm.id)}
                  >
                    Утвердить L2a
                  </button>
                </div>
              ) : null}
            </li>
          ))}
          {!gates?.process_maps?.length ? <li className="muted">Нет процессов — примените пакет</li> : null}
        </ul>
        <h3>Роли</h3>
        <ul className="mgmt-list">
          {(gates?.roles || []).map((r) => (
            <li key={r.id}>
              <strong>{r.title}</strong>
              <span className={`mgmt-status mgmt-status-${r.status}`}> · {r.status}</span>
              {r.status === "draft" || r.status === "suggested" ? (
                <div className="mgmt-approve-row">
                  <button type="button" className="mgmt-btn-secondary" onClick={() => void onApproveRole(r.id)}>
                    Утвердить L2b
                  </button>
                </div>
              ) : null}
            </li>
          ))}
          {!gates?.roles?.length ? <li className="muted">Нет ролей — примените пакет</li> : null}
        </ul>
        <L3PreviewPanel />
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
