"use client";

import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { apiFetch } from "@/lib/api";

export type TextBlock = {
  text: string;
  logic: string;
  field: string;
  period: string;
};

export type HhPreset = {
  version: number;
  status: "draft" | "approved" | string;
  api: {
    texts: TextBlock[];
    area_ids: number[];
    area_name: string;
    relocation: string;
    professional_role_ids: number[];
    experience: string[];
    employment: string[];
    schedule: string[];
    education_level: string[];
    age_from: number | null;
    age_to: number | null;
    gender: string | null;
    salary_from: number | null;
    salary_to: number | null;
    currency: string;
    period_days: number | null;
    order_by: string;
    label: string[];
    language: string[];
    driver_license_types: string[];
    by_text_prefix: boolean;
  };
  soft: {
    must_have: string[];
    reject: string[];
    title_priority: string[];
    portrait: { hard: string[]; important: string[]; nice: string[] };
    office_address: string;
    max_commute_min: number;
    office_required: string;
    recruiter_comment: string;
    soft_rules?: { ignore: string[]; focus: string[]; extra_stop: string[] };
  };
  run: {
    max_search: number;
    max_evaluate: number;
    smart_prefilter: boolean;
  };
  meta?: Record<string, unknown>;
};

type Opt = { id: string; label: string };
type AreaOpt = { id: number; name: string };

type FormOptions = {
  area_presets?: AreaOpt[];
  text_logic?: Opt[];
  text_fields?: Opt[];
  text_periods?: Opt[];
  experience?: Opt[];
  employment?: Opt[];
  schedule?: Opt[];
  relocation?: Opt[];
  order_by?: Opt[];
  education_level?: Opt[];
  label?: Opt[];
  gender?: Opt[];
  office_required?: Opt[];
};

type Warning = { level: string; code: string; text: string };

type Props = {
  vacancyId: number;
  preset: HhPreset;
  formOptions?: FormOptions;
  searchBusy?: boolean;
  onPresetChange: (preset: HhPreset) => void;
  onJobStarted: (jobId: string) => void;
  onMessage?: (msg: string | null, kind?: "ok" | "err") => void;
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  borderRadius: 8,
  border: "1px solid var(--border, #ddd)",
  background: "var(--bg, #fff)",
};

function linesToText(lines: string[]): string {
  return (lines || []).join("\n");
}

function textToLines(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

function toggleInList(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}

function emptyText(): TextBlock {
  return { text: "", logic: "any", field: "everywhere", period: "all_time" };
}

export function HhPresetBlock({
  vacancyId,
  preset,
  formOptions,
  searchBusy,
  onPresetChange,
  onJobStarted,
  onMessage,
}: Props) {
  const [local, setLocal] = useState<HhPreset>(preset);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [warnings, setWarnings] = useState<Warning[]>([]);
  const [showSoft, setShowSoft] = useState(false);
  const [showExtra, setShowExtra] = useState(false);
  const [roleDraft, setRoleDraft] = useState(
    () => (preset.api.professional_role_ids || []).join(", "),
  );

  useEffect(() => {
    setLocal(preset);
    setRoleDraft((preset.api.professional_role_ids || []).join(", "));
  }, [preset]);

  const opts = formOptions || {};
  const areas = opts.area_presets || [];

  const patchApi = useCallback(
    (partial: Partial<HhPreset["api"]>) => {
      setLocal((prev) => {
        const next = {
          ...prev,
          status: prev.status === "approved" ? "draft" : prev.status,
          api: { ...prev.api, ...partial },
        };
        onPresetChange(next);
        return next;
      });
    },
    [onPresetChange],
  );

  const patchSoft = useCallback(
    (partial: Partial<HhPreset["soft"]>) => {
      setLocal((prev) => {
        const next = {
          ...prev,
          status: prev.status === "approved" ? "draft" : prev.status,
          soft: { ...prev.soft, ...partial },
        };
        onPresetChange(next);
        return next;
      });
    },
    [onPresetChange],
  );

  const patchRun = useCallback(
    (partial: Partial<HhPreset["run"]>) => {
      setLocal((prev) => {
        const next = { ...prev, run: { ...prev.run, ...partial } };
        onPresetChange(next);
        return next;
      });
    },
    [onPresetChange],
  );

  const save = async (approve: boolean) => {
    setSaving(true);
    onMessage?.(null);
    try {
      const roles = roleDraft
        .split(/[,\s]+/)
        .map((s) => parseInt(s, 10))
        .filter((n) => !Number.isNaN(n));
      const bodyPreset: HhPreset = {
        ...local,
        api: { ...local.api, professional_role_ids: roles },
      };
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/hh-preset`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset: bodyPreset, approve, rebuild_portrait: false }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setLocal(data.preset);
      setWarnings(data.warnings || []);
      onPresetChange(data.preset);
      onMessage?.(approve ? "Пресет утверждён и сохранён" : "Пресет сохранён", "ok");
      return data.preset as HhPreset;
    } catch (e) {
      onMessage?.(e instanceof Error ? e.message : "Не удалось сохранить", "err");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const runNow = async () => {
    setRunning(true);
    onMessage?.(null);
    try {
      const saved = await save(true);
      if (!saved) return;
      const res = await apiFetch(`/api/v1/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_type: "hh_cold_search",
          vacancy_id: vacancyId,
          payload: { preset: saved },
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const created = await res.json();
      onJobStarted(created.id);
    } catch (e) {
      onMessage?.(e instanceof Error ? e.message : "Не удалось запустить поиск", "err");
    } finally {
      setRunning(false);
    }
  };

  const hardWarns = useMemo(
    () => warnings.filter((w) => w.level === "warning"),
    [warnings],
  );

  const texts = local.api.texts?.length ? local.api.texts : [emptyText()];

  return (
    <div className="hh-preset">
      <div className="hh-status" style={{ marginBottom: 12 }}>
        <span className="muted">
          Пресет = точные фильтры HH · soft-правила только для ИИ · статус:{" "}
          <strong>{local.status}</strong>
        </span>
      </div>

      <div className="hh-section">
        <p className="hh-subhead">Ключевые слова</p>
        {texts.map((block, idx) => (
          <div key={idx} className="hh-plan-card" style={{ marginBottom: 10 }}>
            <label className="hh-field">
              <span className="hh-label">Текст #{idx + 1}</span>
              <input
                style={inputStyle}
                value={block.text}
                placeholder="казначей treasury"
                onChange={(e) => {
                  const next = texts.map((t, i) =>
                    i === idx ? { ...t, text: e.target.value } : t,
                  );
                  patchApi({ texts: next });
                }}
              />
            </label>
            <div className="hh-inline-pair">
              <label className="hh-field">
                <span className="hh-label">Логика</span>
                <select
                  style={inputStyle}
                  value={block.logic}
                  onChange={(e) => {
                    const next = texts.map((t, i) =>
                      i === idx ? { ...t, logic: e.target.value } : t,
                    );
                    patchApi({ texts: next });
                  }}
                >
                  {(opts.text_logic || [
                    { id: "any", label: "Любое из слов" },
                    { id: "all", label: "Все слова" },
                    { id: "phrase", label: "Точная фраза" },
                    { id: "except", label: "Кроме слов" },
                  ]).map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="hh-field">
                <span className="hh-label">Где искать</span>
                <select
                  style={inputStyle}
                  value={block.field}
                  onChange={(e) => {
                    const next = texts.map((t, i) =>
                      i === idx ? { ...t, field: e.target.value } : t,
                    );
                    patchApi({ texts: next });
                  }}
                >
                  {(opts.text_fields || [
                    { id: "everywhere", label: "Везде в резюме" },
                    { id: "title", label: "В названии должности" },
                    { id: "skills", label: "В ключевых навыках" },
                    { id: "experience", label: "В опыте работы" },
                  ]).map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="hh-field">
                <span className="hh-label">Период в опыте</span>
                <select
                  style={inputStyle}
                  value={block.period}
                  onChange={(e) => {
                    const next = texts.map((t, i) =>
                      i === idx ? { ...t, period: e.target.value } : t,
                    );
                    patchApi({ texts: next });
                  }}
                >
                  {(opts.text_periods || [
                    { id: "all_time", label: "За всё время" },
                    { id: "last_year", label: "За последний год" },
                    { id: "last_three_years", label: "За 3 года" },
                  ]).map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {texts.length > 1 ? (
              <button
                type="button"
                className="chip"
                onClick={() => patchApi({ texts: texts.filter((_, i) => i !== idx) })}
              >
                Удалить блок
              </button>
            ) : null}
          </div>
        ))}
        <button
          type="button"
          className="chip"
          onClick={() => patchApi({ texts: [...texts, emptyText()] })}
        >
          + ещё текстовый блок
        </button>
      </div>

      <div className="hh-section">
        <p className="hh-subhead">Регион и роль</p>
        <div className="hh-funnel-grid">
          <label className="hh-field">
            <span className="hh-label">Город</span>
            <select
              style={inputStyle}
              value={local.api.area_ids[0] ?? ""}
              onChange={(e) => {
                const id = e.target.value ? parseInt(e.target.value, 10) : NaN;
                if (Number.isNaN(id)) {
                  patchApi({ area_ids: [], area_name: "" });
                  return;
                }
                const name = areas.find((a) => a.id === id)?.name || "";
                patchApi({ area_ids: [id], area_name: name });
              }}
            >
              <option value="">— не задан —</option>
              {areas.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <label className="hh-field">
            <span className="hh-label">Переезд</span>
            <select
              style={inputStyle}
              value={local.api.relocation}
              onChange={(e) => patchApi({ relocation: e.target.value })}
            >
              {(opts.relocation || []).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="hh-field">
            <span className="hh-label">Проф. роли (id через запятую)</span>
            <input
              style={inputStyle}
              value={roleDraft}
              placeholder="50 = Казначей"
              onChange={(e) => setRoleDraft(e.target.value)}
              onBlur={() => {
                const roles = roleDraft
                  .split(/[,\s]+/)
                  .map((s) => parseInt(s, 10))
                  .filter((n) => !Number.isNaN(n));
                patchApi({ professional_role_ids: roles });
              }}
            />
            <span className="muted hh-micro">Подсказка: Казначей = 50, Бухгалтер = 18</span>
          </label>
        </div>
      </div>

      <div className="hh-section">
        <p className="hh-subhead">Опыт / занятость / график</p>
        <div className="hh-chip-row">
          {(opts.experience || []).map((o) => (
            <button
              key={o.id}
              type="button"
              className={local.api.experience.includes(o.id) ? "chip chip-active" : "chip"}
              onClick={() => patchApi({ experience: toggleInList(local.api.experience, o.id) })}
            >
              {o.label}
            </button>
          ))}
        </div>
        <div className="hh-chip-row" style={{ marginTop: 8 }}>
          {(opts.employment || []).map((o) => (
            <button
              key={o.id}
              type="button"
              className={local.api.employment.includes(o.id) ? "chip chip-active" : "chip"}
              onClick={() => patchApi({ employment: toggleInList(local.api.employment, o.id) })}
            >
              {o.label}
            </button>
          ))}
        </div>
        <p className="muted hh-micro">График HH пустой = любой (рекомендуется). Жмите только если нужен жёсткий фильтр.</p>
        <div className="hh-chip-row">
          {(opts.schedule || []).map((o) => (
            <button
              key={o.id}
              type="button"
              className={local.api.schedule.includes(o.id) ? "chip chip-active" : "chip"}
              onClick={() => patchApi({ schedule: toggleInList(local.api.schedule, o.id) })}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      <div className="hh-section">
        <p className="hh-subhead">Зарплата и свежесть</p>
        <div className="hh-funnel-grid">
          <label className="hh-field">
            <span className="hh-label">ЗП от</span>
            <input
              style={inputStyle}
              type="number"
              value={local.api.salary_from ?? ""}
              onChange={(e) =>
                patchApi({
                  salary_from: e.target.value === "" ? null : parseInt(e.target.value, 10),
                })
              }
            />
          </label>
          <label className="hh-field">
            <span className="hh-label">ЗП до</span>
            <input
              style={inputStyle}
              type="number"
              value={local.api.salary_to ?? ""}
              onChange={(e) =>
                patchApi({
                  salary_to: e.target.value === "" ? null : parseInt(e.target.value, 10),
                })
              }
            />
          </label>
          <label className="hh-field">
            <span className="hh-label">Период обновления, дни</span>
            <input
              style={inputStyle}
              type="number"
              value={local.api.period_days ?? ""}
              onChange={(e) =>
                patchApi({
                  period_days: e.target.value === "" ? null : parseInt(e.target.value, 10),
                })
              }
            />
          </label>
          <label className="hh-field">
            <span className="hh-label">Сортировка</span>
            <select
              style={inputStyle}
              value={local.api.order_by}
              onChange={(e) => patchApi({ order_by: e.target.value })}
            >
              {(opts.order_by || []).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="hh-section">
        <button type="button" className="chip" onClick={() => setShowExtra((v) => !v)}>
          {showExtra ? "Скрыть возраст/пол/образование" : "Ещё фильтры HH (возраст, пол, …)"}
        </button>
        {showExtra ? (
          <div className="hh-advanced" style={{ marginTop: 10 }}>
            <div className="hh-inline-pair">
              <label className="hh-field">
                <span className="hh-label">Возраст от</span>
                <input
                  style={inputStyle}
                  type="number"
                  value={local.api.age_from ?? ""}
                  onChange={(e) =>
                    patchApi({
                      age_from: e.target.value === "" ? null : parseInt(e.target.value, 10),
                    })
                  }
                />
              </label>
              <label className="hh-field">
                <span className="hh-label">Возраст до</span>
                <input
                  style={inputStyle}
                  type="number"
                  value={local.api.age_to ?? ""}
                  onChange={(e) =>
                    patchApi({
                      age_to: e.target.value === "" ? null : parseInt(e.target.value, 10),
                    })
                  }
                />
              </label>
              <label className="hh-field">
                <span className="hh-label">Пол</span>
                <select
                  style={inputStyle}
                  value={local.api.gender ?? ""}
                  onChange={(e) => patchApi({ gender: e.target.value || null })}
                >
                  <option value="">— любой —</option>
                  {(opts.gender || []).map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        ) : null}
      </div>

      <div className="hh-section">
        <button type="button" className="chip" onClick={() => setShowSoft((v) => !v)}>
          {showSoft ? "Скрыть soft-правила" : "Soft-правила для ИИ (не уходят в HH API)"}
        </button>
        {showSoft ? (
          <div className="hh-advanced" style={{ marginTop: 10 }}>
            <label className="hh-field">
              <span className="hh-label">Комментарий рекрутера</span>
              <textarea
                style={inputStyle}
                rows={3}
                value={local.soft.recruiter_comment}
                onChange={(e) => patchSoft({ recruiter_comment: e.target.value })}
              />
            </label>
            <label className="hh-field">
              <span className="hh-label">Must-have</span>
              <textarea
                style={inputStyle}
                rows={2}
                value={linesToText(local.soft.must_have)}
                onChange={(e) => patchSoft({ must_have: textToLines(e.target.value) })}
              />
            </label>
            <label className="hh-field">
              <span className="hh-label">Отсев</span>
              <textarea
                style={inputStyle}
                rows={2}
                value={linesToText(local.soft.reject)}
                onChange={(e) => patchSoft({ reject: textToLines(e.target.value) })}
              />
            </label>
            <label className="hh-field">
              <span className="hh-label">Приоритет названий</span>
              <textarea
                style={inputStyle}
                rows={2}
                value={linesToText(local.soft.title_priority)}
                onChange={(e) => patchSoft({ title_priority: textToLines(e.target.value) })}
              />
            </label>
          </div>
        ) : null}
      </div>

      <div className="hh-section">
        <p className="hh-subhead">Лимиты запуска</p>
        <div className="hh-inline-pair">
          <label className="hh-field">
            <span className="hh-label">max_search</span>
            <input
              style={inputStyle}
              type="number"
              min={1}
              max={50}
              value={local.run.max_search}
              onChange={(e) => patchRun({ max_search: parseInt(e.target.value, 10) || 1 })}
            />
          </label>
          <label className="hh-field">
            <span className="hh-label">max_evaluate</span>
            <input
              style={inputStyle}
              type="number"
              min={0}
              max={50}
              value={local.run.max_evaluate}
              onChange={(e) => patchRun({ max_evaluate: parseInt(e.target.value, 10) || 0 })}
            />
          </label>
        </div>
      </div>

      {hardWarns.length ? (
        <div className="hh-warns">
          {hardWarns.map((w) => (
            <p key={w.code} className="warn">
              ⚠ {w.text}
            </p>
          ))}
        </div>
      ) : null}

      <div className="hh-footer-actions" style={{ marginTop: 12 }}>
        <button type="button" className="chip" disabled={saving || running} onClick={() => void save(false)}>
          {saving ? "…" : "Сохранить"}
        </button>
        <button
          type="button"
          className="chip chip-active"
          disabled={saving || running || searchBusy}
          onClick={() => void runNow()}
        >
          {running || searchBusy ? "Поиск…" : "Сохранить и запустить"}
        </button>
      </div>
    </div>
  );
}
