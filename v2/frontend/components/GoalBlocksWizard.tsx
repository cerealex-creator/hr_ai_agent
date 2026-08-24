"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  approveMgmtGoalBlock,
  generateMgmtGoalBlock,
  skipMgmtGoalBlock,
  submitMgmtGoalBlockAnswer,
  updateMgmtGoal,
  type MgmtGoal,
  type MgmtGoalBlock,
} from "@/lib/management";

type BlockCode = "finance" | "customers" | "processes" | "people";

type Props = {
  blocks: MgmtGoalBlock[];
  skippedBlocks?: string[];
  mode?: "wizard" | "expert";
  busy?: boolean;
  onReload: () => Promise<void>;
  onCompleteStep?: () => Promise<void>;
  showWizardComplete?: boolean;
};

const BLOCK_ORDER: BlockCode[] = ["finance", "customers", "processes", "people"];

export function GoalBlocksWizard({
  blocks,
  skippedBlocks = [],
  mode = "wizard",
  busy: externalBusy,
  onReload,
  onCompleteStep,
  showWizardComplete = false,
}: Props) {
  const [activeBlock, setActiveBlock] = useState<BlockCode>("finance");
  const [answersDraft, setAnswersDraft] = useState<Record<string, string>>({});
  const [selectedGoals, setSelectedGoals] = useState<Record<string, boolean>>({});
  const [editGoalId, setEditGoalId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editBaseline, setEditBaseline] = useState("");
  const [editTarget, setEditTarget] = useState("");
  const [editUnit, setEditUnit] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const isBusy = busy || externalBusy;

  const blockMap = useMemo(() => {
    const m = new Map<string, MgmtGoalBlock>();
    for (const b of blocks) m.set(b.code, b);
    return m;
  }, [blocks]);

  const active = blockMap.get(activeBlock);

  useEffect(() => {
    if (!active) return;
    const draft: Record<string, string> = {};
    const selected: Record<string, boolean> = {};
    for (const a of active.answers) draft[a.question_key.split(".").pop() || a.question_key] = a.answer_text;
    for (const g of active.goals) {
      if (g.status === "draft") selected[g.id] = selectedGoals[g.id] ?? true;
    }
    setAnswersDraft(draft);
    setSelectedGoals((prev) => ({ ...selected, ...prev }));
  }, [activeBlock, active?.answers, active?.goals]);

  const approvedCount = useMemo(
    () =>
      blocks.filter(
        (b) =>
          b.status === "approved" ||
          b.status === "skipped" ||
          skippedBlocks.includes(b.code)
      ).length,
    [blocks, skippedBlocks]
  );

  const run = useCallback(
    async (fn: () => Promise<void>) => {
      setBusy(true);
      setErr(null);
      try {
        await fn();
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Ошибка");
      } finally {
        setBusy(false);
      }
    },
    []
  );

  async function saveAnswer(questionKey: string) {
    const text = (answersDraft[questionKey] || "").trim();
    if (!text || !active) return;
    await run(async () => {
      await submitMgmtGoalBlockAnswer(active.code, questionKey, text);
      setMsg("Ответ сохранён");
      await onReload();
    });
  }

  async function onGenerate() {
    if (!active) return;
    await run(async () => {
      const result = await generateMgmtGoalBlock(active.code);
      if (!result.ok) throw new Error(result.message || result.error || "Ошибка генерации");
      setMsg(`Предложено целей: ${result.goals_count ?? 0}`);
      await onReload();
    });
  }

  async function onApproveBlock() {
    if (!active) return;
    const ids = active.goals.filter((g) => g.status === "draft" && selectedGoals[g.id]).map((g) => g.id);
    if (!ids.length) {
      setErr("Отметьте черновые цели для утверждения");
      return;
    }
    await run(async () => {
      const r = await approveMgmtGoalBlock(active.code, ids);
      if (!r.ok) throw new Error(r.message || r.error);
      setMsg(`Утверждено: ${r.approved_count ?? 0}`);
      await onReload();
    });
  }

  async function onSkipBlock() {
    if (!active) return;
    await run(async () => {
      await skipMgmtGoalBlock(active.code);
      setMsg(`Блок «${active.title}» пропущен`);
      await onReload();
    });
  }

  async function saveGoalEdit(goal: MgmtGoal) {
    await run(async () => {
      await updateMgmtGoal(goal.id, {
        title: editTitle.trim() || goal.title,
        baseline_value: editBaseline ? Number(editBaseline) : null,
        target_value: editTarget ? Number(editTarget) : null,
        metric_unit: editUnit.trim() || null,
        metric_source: editBaseline || editTarget ? "owner" : null,
      });
      setEditGoalId(null);
      setMsg("Цель обновлена");
      await onReload();
    });
  }

  function startEdit(goal: MgmtGoal) {
    setEditGoalId(goal.id);
    setEditTitle(goal.title);
    setEditBaseline(goal.baseline_value != null ? String(goal.baseline_value) : "");
    setEditTarget(goal.target_value != null ? String(goal.target_value) : "");
    setEditUnit(goal.metric_unit || "");
  }

  function statusLabel(status: string) {
    if (status === "approved") return "утверждено";
    if (status === "draft") return "есть предложения";
    if (status === "skipped") return "пропущено";
    return "не начато";
  }

  if (!active) return <p className="muted">Нет данных блоков</p>;

  return (
    <div className="mgmt-goal-blocks">
      <div className="mgmt-goal-blocks-stats muted">
        Блоков закрыто: {approvedCount} / 4 · режим: {mode === "wizard" ? "мастер" : "эксперт"}
      </div>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <div className="mgmt-goal-blocks-shell">
        <nav className="mgmt-goal-blocks-nav">
          {BLOCK_ORDER.map((code) => {
            const b = blockMap.get(code);
            if (!b) return null;
            return (
              <button
                key={code}
                type="button"
                className={`mgmt-goal-blocks-nav-item${code === activeBlock ? " is-active" : ""}`}
                onClick={() => setActiveBlock(code)}
              >
                <span className="mgmt-goal-blocks-nav-title">{b.title}</span>
                <span className="muted">{statusLabel(b.status)}</span>
              </button>
            );
          })}
        </nav>

        <div className="mgmt-goal-blocks-main">
          <header className="mgmt-goal-blocks-head">
            <div>
              <h3>{active.title}</h3>
              <p className="muted">{active.subtitle}</p>
            </div>
            <span className={`mgmt-status mgmt-status-${active.status}`}>{statusLabel(active.status)}</span>
          </header>

          <section className="card-edit mgmt-block-survey">
            <h4>Короткий опрос</h4>
            <div className="mgmt-block-questions">
              {active.questions.map((q) => (
                <div key={q.key} className="mgmt-block-question">
                  <label>{q.text}</label>
                  {q.field_type === "select" ? (
                    <select
                      value={answersDraft[q.key] || ""}
                      onChange={(e) =>
                        setAnswersDraft((prev) => ({ ...prev, [q.key]: e.target.value }))
                      }
                      onBlur={() => void saveAnswer(q.key)}
                    >
                      <option value="">{q.placeholder || "— выберите —"}</option>
                      {(q.options || []).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={answersDraft[q.key] || ""}
                      placeholder={q.placeholder || ""}
                      onChange={(e) =>
                        setAnswersDraft((prev) => ({ ...prev, [q.key]: e.target.value }))
                      }
                      onBlur={() => void saveAnswer(q.key)}
                    />
                  )}
                  <button
                    type="button"
                    className="mgmt-btn-secondary"
                    disabled={isBusy}
                    onClick={() => void saveAnswer(q.key)}
                  >
                    Сохранить
                  </button>
                </div>
              ))}
            </div>
            <div className="mgmt-form-row">
              <button type="button" disabled={isBusy} onClick={() => void onGenerate()}>
                Предложить 2–3 цели
              </button>
              <button type="button" className="mgmt-btn-secondary" disabled={isBusy} onClick={() => void onSkipBlock()}>
                Пропустить блок
              </button>
            </div>
          </section>

          {active.goals.length ? (
            <section className="card-edit">
              <h4>Предложения — отметьте и при необходимости отредактируйте</h4>
              <ul className="mgmt-goal-proposals">
                {active.goals.map((g) => (
                  <li key={g.id} className={`mgmt-goal-proposal mgmt-status-${g.status}`}>
                    {g.status === "draft" ? (
                      <input
                        type="checkbox"
                        checked={!!selectedGoals[g.id]}
                        onChange={(e) =>
                          setSelectedGoals((prev) => ({ ...prev, [g.id]: e.target.checked }))
                        }
                      />
                    ) : (
                      <span className="mgmt-status-approved">✓</span>
                    )}
                    <div className="mgmt-goal-proposal-body">
                      {editGoalId === g.id ? (
                        <div className="mgmt-form-col">
                          <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
                          <div className="mgmt-form-row">
                            <input
                              placeholder="baseline"
                              value={editBaseline}
                              onChange={(e) => setEditBaseline(e.target.value)}
                            />
                            <input
                              placeholder="target"
                              value={editTarget}
                              onChange={(e) => setEditTarget(e.target.value)}
                            />
                            <input
                              placeholder="ед."
                              value={editUnit}
                              onChange={(e) => setEditUnit(e.target.value)}
                            />
                          </div>
                          <div className="mgmt-form-row">
                            <button type="button" disabled={isBusy} onClick={() => void saveGoalEdit(g)}>
                              Сохранить
                            </button>
                            <button type="button" className="mgmt-btn-secondary" onClick={() => setEditGoalId(null)}>
                              Отмена
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <strong>{g.title}</strong>
                          {g.baseline_value != null || g.target_value != null ? (
                            <span className="muted">
                              {" "}
                              · {g.baseline_value ?? "—"} → {g.target_value ?? "—"}
                              {g.metric_unit ? ` ${g.metric_unit}` : ""}
                            </span>
                          ) : (
                            <span className="muted"> · без цифр (качественная цель)</span>
                          )}
                          {g.status === "draft" ? (
                            <button
                              type="button"
                              className="mgmt-btn-secondary"
                              onClick={() => startEdit(g)}
                            >
                              Изменить
                            </button>
                          ) : null}
                        </>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
              <div className="mgmt-form-row">
                <button type="button" disabled={isBusy} onClick={() => void onApproveBlock()}>
                  Утвердить выбранные цели блока
                </button>
                <button type="button" className="mgmt-btn-secondary" disabled={isBusy} onClick={() => void onGenerate()}>
                  Предложить снова
                </button>
              </div>
            </section>
          ) : null}

          <div className="mgmt-form-row">
            {BLOCK_ORDER.indexOf(activeBlock) < BLOCK_ORDER.length - 1 ? (
              <button
                type="button"
                className="mgmt-btn-secondary"
                onClick={() => {
                  const idx = BLOCK_ORDER.indexOf(activeBlock);
                  setActiveBlock(BLOCK_ORDER[idx + 1]);
                }}
              >
                Следующий блок
              </button>
            ) : null}
            {showWizardComplete && onCompleteStep ? (
              <button
                type="button"
                disabled={isBusy || approvedCount < 4}
                onClick={() => void run(onCompleteStep)}
              >
                Завершить шаг 3
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
