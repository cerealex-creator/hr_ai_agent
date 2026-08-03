"use client";

import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { getApiBase } from "@/lib/api";

type Priority = "hard" | "important" | "nice";

type Portrait = { hard: string[]; important: string[]; nice: string[] };

type PrefillMeta = {
  prefilled_at?: string | null;
  sources?: string[];
  recruiter_edited?: boolean;
  skip_prefill?: boolean;
};

type Criteria = {
  keywords: string;
  area_id: number | null;
  area_name: string;
  schedule: string;
  experience_from: number | null;
  salary_to: number | null;
  period_days: number | null;
  office_address: string;
  max_commute_min: number;
  office_required: "first_3_months" | "always" | "no";
  title_priority: string[];
  must_have: string[];
  reject: string[];
  priorities: Record<string, Priority>;
  portrait: Portrait;
  recruiter_comment: string;
  prefill_meta: PrefillMeta;
  max_search: number;
  max_evaluate: number;
  smart_prefilter: boolean;
};

type Warning = { level: string; code: string; text: string };

type HhHit = {
  hh_resume_id: string;
  title: string;
  url: string;
  area?: string | null;
  ai_score?: number | null;
  ai_preview?: string;
  title_fit?: string | null;
  office_fit?: string | null;
  commute_ok?: string | null;
  error?: string | null;
  skipped_eval?: boolean;
  skipped_prefilter?: boolean;
  skipped_seen?: boolean;
  seen_label?: string;
  prefilter_reason?: string;
  source_query?: string;
};

type Job = {
  id: string;
  status: string;
  progress_pct: number | null;
  progress_label: string | null;
  error: string | null;
  payload: {
    keywords?: string;
    found?: number;
    evaluated?: number;
    prefilter?: {
      hard_skip?: number;
      soft_backfill?: number;
      to_eval?: number;
      seen_skip?: number;
    };
    results?: HhHit[];
  };
};

type HistoryItem = {
  id: string;
  status: string;
  created_at: string | null;
  keywords_short: string;
  found: number | null;
  evaluated: number | null;
  progress_label: string | null;
  error: string | null;
};

type ShortItem = {
  id: string;
  hh_resume_id: string;
  title: string;
  url?: string | null;
  area?: string | null;
  ai_score?: number | null;
};

type ToCandidateResult = {
  candidate: { id: string; name: string };
  created: boolean;
  already_exists: boolean;
};

type Defaults = {
  criteria: Criteria;
  warnings: Warning[];
  needs_prefill?: boolean;
  schedule_options: { id: string; label: string }[];
  area_presets: { id: number; name: string }[];
};

type Props = { vacancyId: number };

const inputStyle: CSSProperties = {
  padding: "0.45rem 0.65rem",
  borderRadius: 8,
  border: "1px solid var(--border, var(--line))",
  background: "var(--surface, #fff)",
  color: "inherit",
  font: "inherit",
  width: "100%",
};

function linesToText(lines: string[]) {
  return (lines || []).join("\n");
}

/** Keep spaces/newlines while typing — do not trim on every keystroke. */
function textToLines(text: string) {
  return text.split("\n");
}

function normalizeLines(lines: string[]) {
  return (lines || []).map((s) => s.trim()).filter(Boolean);
}

function normalizeCriteriaForSave(c: Criteria): Criteria {
  return {
    ...c,
    keywords: c.keywords,
    title_priority: normalizeLines(c.title_priority),
    must_have: normalizeLines(c.must_have),
    reject: normalizeLines(c.reject),
    recruiter_comment: (c.recruiter_comment || "").trim(),
    prefill_meta: c.prefill_meta || {},
    portrait: {
      hard: normalizeLines(c.portrait?.hard || []),
      important: normalizeLines(c.portrait?.important || []),
      nice: normalizeLines(c.portrait?.nice || []),
    },
  };
}

const FIT_RU: Record<string, string> = {
  yes: "да",
  partial: "частично",
  no: "нет",
  unknown: "неясно",
};

function fitLabel(value?: string | null): string {
  if (!value) return "—";
  return FIT_RU[value] || value;
}

/** Local warnings from current form (same rules as backend). */
function buildWarnings(c: Criteria): Warning[] {
  const out: Warning[] = [];
  const meta = c.prefill_meta || {};
  if (meta.prefilled_at && !meta.recruiter_edited) {
    const sources = (meta.sources || []).join(", ") || "профиль";
    out.push({
      level: "warning",
      code: "prefill_unreviewed",
      text: `Критерии заполнены ИИ (${sources}), правок рекрутера ещё не было. Проверьте портрет и комментарий перед поиском — иначе снова будет шум.`,
    });
  }
  const kw = (c.keywords || "").trim();
  if (!kw) {
    out.push({
      level: "warning",
      code: "no_keywords",
      text: "Нет ключевых запросов — воронка HH будет пустой или слишком широкой.",
    });
  } else if (kw.split(/\s+/).length < 2 && !kw.includes("\n")) {
    out.push({
      level: "info",
      code: "weak_keywords",
      text: "Один короткий запрос — лучше 2–3 близких названия должности (с новой строки).",
    });
  }
  if (!c.schedule && c.office_required !== "no") {
    out.push({
      level: "warning",
      code: "no_schedule",
      text: "Не задан график HH — remote-only могут попасть в выдачу; ИИ отсечёт только по портрету.",
    });
  }
  if (c.area_id == null && !(c.area_name || "").trim()) {
    out.push({
      level: "warning",
      code: "no_area",
      text: "Город не задан — в выдачу попадут другие регионы; «близко к офису» оценить сложно.",
    });
  }
  if (c.office_required !== "no" && !(c.office_address || "").trim()) {
    out.push({
      level: "info",
      code: "no_office_address",
      text: "Нет адреса офиса — время в пути будет грубым (по городу/району из резюме).",
    });
  }
  if (!(c.title_priority || []).some((x) => x.trim())) {
    out.push({
      level: "info",
      code: "no_title_priority",
      text: "Нет приоритета названий — сильный «похожий» профиль может обогнать точное совпадение должности.",
    });
  }
  const portrait = c.portrait || { hard: [], important: [], nice: [] };
  if (
    !(c.must_have || []).some((x) => x.trim()) &&
    !(portrait.hard || []).some((x) => x.trim()) &&
    !(portrait.important || []).some((x) => x.trim())
  ) {
    out.push({
      level: "info",
      code: "thin_portrait",
      text: "Портрет почти пустой — оценка будет общей, больше «не тех» кандидатов.",
    });
  }
  if (!c.period_days) {
    out.push({
      level: "info",
      code: "no_period",
      text: "Нет фильтра свежести — в выдачу попадут и давно не обновлявшиеся резюме.",
    });
  }
  if (!(c.recruiter_comment || "").trim()) {
    out.push({
      level: "info",
      code: "no_recruiter_comment",
      text: "Нет комментария рекрутера — ИИ будет опираться только на портрет и профиль.",
    });
  }
  return out;
}

export function HhSearchPanel({ vacancyId }: Props) {
  const [criteria, setCriteria] = useState<Criteria | null>(null);
  const [scheduleOptions, setScheduleOptions] = useState<{ id: string; label: string }[]>([]);
  const [areaPresets, setAreaPresets] = useState<{ id: number; name: string }[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [shortlist, setShortlist] = useState<ShortItem[]>([]);
  const [shortIds, setShortIds] = useState<Set<string>>(new Set());
  const [toFunnelBusy, setToFunnelBusy] = useState<string | null>(null);
  const [lastFunnelLink, setLastFunnelLink] = useState<{ id: string; name: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState<string | null>(null);
  const [prefillBanner, setPrefillBanner] = useState<string | null>(null);
  const [prefilling, setPrefilling] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [section, setSection] = useState<"who" | "funnel" | "results">("who");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showInfoTips, setShowInfoTips] = useState(false);

  const markRecruiterEdited = useCallback((prev: Criteria): Criteria => {
    const meta = prev.prefill_meta || {};
    if (!meta.prefilled_at || meta.recruiter_edited) return prev;
    return {
      ...prev,
      prefill_meta: { ...meta, recruiter_edited: true },
    };
  }, []);

  const loadShortlist = useCallback(async () => {
    const res = await fetch(`${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-shortlist`, {
      cache: "no-store",
    });
    if (!res.ok) return;
    const items: ShortItem[] = await res.json();
    setShortlist(items);
    setShortIds(new Set(items.map((i) => i.hh_resume_id)));
  }, [vacancyId]);

  const poll = useCallback(async (jobId: string) => {
    const res = await fetch(`${getApiBase()}/api/v1/jobs/${jobId}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const next: Job = await res.json();
    setJob(next);
    return next;
  }, []);

  const loadHistory = useCallback(async () => {
    const res = await fetch(
      `${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-search-history?limit=20`,
      { cache: "no-store" },
    );
    if (!res.ok) return [] as HistoryItem[];
    const data = await res.json();
    const items: HistoryItem[] = data.items || [];
    setHistory(items);
    return items;
  }, [vacancyId]);

  const openHistoryJob = useCallback(
    async (jobId: string) => {
      setError(null);
      setSection("results");
      await poll(jobId);
    },
    [poll],
  );

  const runPrefill = useCallback(async () => {
    setPrefilling(true);
    setError(null);
    try {
      const res = await fetch(
        `${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-search-criteria/prefill`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setCriteria({
        ...data.criteria,
        recruiter_comment: data.criteria.recruiter_comment || "",
        prefill_meta: data.criteria.prefill_meta || {},
      });
      const sources = (data.sources || []).join(", ") || "профиль";
      setPrefillBanner(
        `ИИ заполнил критерии из: ${sources}. Проверьте портрет и комментарий.`,
      );
      setSection("who");
      setSaveOk(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Prefill не удался");
    } finally {
      setPrefilling(false);
    }
  }, [vacancyId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-search-defaults`,
          { cache: "no-store" },
        );
        if (!res.ok) throw new Error(`API ${res.status}`);
        const data: Defaults = await res.json();
        if (cancelled) return;
        setCriteria({
          ...data.criteria,
          recruiter_comment: data.criteria.recruiter_comment || "",
          prefill_meta: data.criteria.prefill_meta || {},
        });
        setScheduleOptions(data.schedule_options || []);
        setAreaPresets(data.area_presets || []);
        await loadShortlist();
        const items = await loadHistory();
        if (cancelled) return;
        const active = items.find((h) => h.status === "queued" || h.status === "running");
        const latestDone = items.find((h) => h.status === "completed");
        const restore = active || latestDone;
        if (restore) {
          await poll(restore.id);
          if (!cancelled && latestDone && !active) {
            setSection("results");
          }
        }
        if (data.needs_prefill && !cancelled) {
          await runPrefill();
        } else if (data.criteria?.prefill_meta?.prefilled_at && !data.criteria.prefill_meta.recruiter_edited) {
          const sources = (data.criteria.prefill_meta.sources || []).join(", ") || "профиль";
          setPrefillBanner(
            `Критерии ранее заполнены ИИ (${sources}), правок рекрутера не было.`,
          );
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [vacancyId, loadShortlist, loadHistory, poll, runPrefill]);

  const patch = useCallback(
    (partial: Partial<Criteria>) => {
      setCriteria((prev) => {
        if (!prev) return prev;
        return markRecruiterEdited({ ...prev, ...partial });
      });
      setPrefillBanner(null);
    },
    [markRecruiterEdited],
  );

  const patchPortrait = (tier: keyof Portrait, text: string) => {
    setCriteria((prev) => {
      if (!prev) return prev;
      return markRecruiterEdited({
        ...prev,
        portrait: { ...prev.portrait, [tier]: textToLines(text) },
      });
    });
    setPrefillBanner(null);
  };

  const saveCriteria = async (rebuildPortrait = false) => {
    if (!criteria) return null;
    setSaving(true);
    setError(null);
    setSaveOk(null);
    const toSave = normalizeCriteriaForSave(criteria);
    try {
      const res = await fetch(
        `${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-search-criteria`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ criteria: toSave, rebuild_portrait: rebuildPortrait }),
        },
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setCriteria(data.criteria);
      setSaveOk(
        rebuildPortrait
          ? "Портрет пересобран и критерии сохранены в вакансию."
          : "Критерии сохранены в вакансию. При следующем открытии подставятся сами.",
      );
      return data.criteria as Criteria;
    } catch (e) {
      const msg =
        e instanceof TypeError
          ? "API недоступен (http://localhost:8000). Запустите uvicorn и попробуйте снова."
          : e instanceof Error
            ? e.message
            : "Не удалось сохранить";
      setError(msg);
      return null;
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    if (!job || ["completed", "failed", "cancelled"].includes(job.status)) return;
    const t = setInterval(() => {
      poll(job.id).catch(() => undefined);
    }, 2000);
    return () => clearInterval(t);
  }, [job, poll]);

  const onStart = async () => {
    if (!criteria) return;
    const meta = criteria.prefill_meta || {};
    if (meta.prefilled_at && !meta.recruiter_edited) {
      const ok = window.confirm(
        "Критерии заполнены ИИ, правок рекрутера не зафиксировано.\n\nРекомендуется проверить портрет и комментарий. Всё равно запустить поиск?",
      );
      if (!ok) return;
    }
    setBusy(true);
    setError(null);
    setSection("results");
    try {
      const saved = await saveCriteria(false);
      const payloadCriteria = normalizeCriteriaForSave(saved || criteria);
      const res = await fetch(`${getApiBase()}/api/v1/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_type: "hh_cold_search",
          vacancy_id: vacancyId,
          payload: { criteria: payloadCriteria },
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const created = await res.json();
      await poll(created.id);
      await loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось запустить");
    } finally {
      setBusy(false);
    }
  };

  const addToShortlist = async (hit: HhHit) => {
    try {
      const res = await fetch(`${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-shortlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hh_resume_id: hit.hh_resume_id,
          title: hit.title,
          url: hit.url,
          area: hit.area,
          ai_score: hit.ai_score,
          snapshot: hit,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      await loadShortlist();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Shortlist error");
    }
  };

  const rejectCandidate = async (hit: HhHit) => {
    try {
      const res = await fetch(`${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-seen/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hh_resume_id: hit.hh_resume_id,
          title: hit.title,
          url: hit.url,
          ai_score: hit.ai_score,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setSaveOk(`«${hit.title || hit.hh_resume_id}» больше не будет оцениваться в этой вакансии.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось отклонить");
    }
  };

  const removeShortlist = async (itemId: string) => {
    await fetch(`${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-shortlist/${itemId}`, {
      method: "DELETE",
    });
    await loadShortlist();
  };

  const toFunnel = async (item: ShortItem) => {
    setToFunnelBusy(item.id);
    setError(null);
    setSaveOk(null);
    try {
      const res = await fetch(
        `${getApiBase()}/api/v1/vacancies/${vacancyId}/hh-shortlist/${item.id}/to-candidate`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await res.text());
      const data: ToCandidateResult = await res.json();
      setLastFunnelLink({ id: data.candidate.id, name: data.candidate.name });
      setSaveOk(
        data.created
          ? `В воронке: ${data.candidate.name}`
          : `Уже был в воронке: ${data.candidate.name}`,
      );
      await loadShortlist();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось создать кандидата");
    } finally {
      setToFunnelBusy(null);
    }
  };

  const results = job?.payload?.results || [];

  const warnings = useMemo(
    () => (criteria ? buildWarnings(criteria) : []),
    [criteria],
  );

  const portraitPreview = useMemo(() => {
    if (!criteria) return null;
    return criteria.portrait;
  }, [criteria]);

  const warningsHard = useMemo(
    () => warnings.filter((w) => w.level === "warning"),
    [warnings],
  );
  const warningsInfo = useMemo(
    () => warnings.filter((w) => w.level !== "warning"),
    [warnings],
  );

  if (!criteria) {
    return <p className="muted">{error || "Загрузка критериев…"}</p>;
  }

  const meta = criteria.prefill_meta || {};
  const statusBits: string[] = [];
  if (prefilling) statusBits.push("заполнение ИИ…");
  else if (meta.prefilled_at) {
    statusBits.push(meta.recruiter_edited ? "prefill · правки есть" : "prefill · без правок");
  }
  if (warningsHard.length) statusBits.push(`⚠ ${warningsHard.length}`);
  if (shortlist.length) statusBits.push(`★ ${shortlist.length}`);

  return (
    <div className="hh-panel">
      <div className="hh-status">
        <span className="muted">Холодный поиск HH · без контактов · ~50 просмотров/сутки</span>
        {statusBits.length ? <span className="hh-status-pills">{statusBits.join(" · ")}</span> : null}
      </div>

      {error ? <p className="warn">{error}</p> : null}
      {saveOk ? <p className="muted">{saveOk}</p> : null}
      {prefillBanner ? <p className="warn">{prefillBanner}</p> : null}

      <div className="tabs" role="tablist">
        <button
          type="button"
          className={section === "who" ? "tab tab-active" : "tab"}
          onClick={() => setSection("who")}
        >
          1. Кого ищем
        </button>
        <button
          type="button"
          className={section === "funnel" ? "tab tab-active" : "tab"}
          onClick={() => setSection("funnel")}
        >
          2. Воронка HH
        </button>
        <button
          type="button"
          className={section === "results" ? "tab tab-active" : "tab"}
          onClick={() => setSection("results")}
        >
          3. Результаты
          {results.length ? <span className="tab-count">{results.length}</span> : null}
        </button>
      </div>

      {section === "who" ? (
        <div className="hh-section">
          <label className="hh-field">
            <span className="hh-label">Комментарий рекрутера</span>
            <span className="muted hh-label-hint">читается ИИ первым</span>
            <textarea
              value={criteria.recruiter_comment || ""}
              onChange={(e) => patch({ recruiter_comment: e.target.value })}
              rows={3}
              style={inputStyle}
              placeholder="Сфера fashion желательна; не брать руководителей направления; ЗП выше 130к — мимо…"
            />
          </label>

          <div className="hh-portrait-grid">
            {(["hard", "important", "nice"] as const).map((tier) => (
              <label key={tier} className="hh-field">
                <span className="hh-label">
                  {tier === "hard" ? "Жёстко" : tier === "important" ? "Важно" : "Желательно"}
                </span>
                <textarea
                  value={linesToText(portraitPreview?.[tier] || [])}
                  onChange={(e) => patchPortrait(tier, e.target.value)}
                  rows={5}
                  style={inputStyle}
                />
              </label>
            ))}
          </div>
          <p className="muted hh-micro">
            Жёстко — отсев · Важно — сильный downrank · Желательно — можно «закрыть глаза»
          </p>

          <button
            type="button"
            className="chip"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? "Скрыть дополнительно" : "Дополнительно: названия, must-have, отсев"}
          </button>

          {showAdvanced ? (
            <div className="hh-advanced">
              <label className="hh-field">
                <span className="hh-label">Приоритет названий</span>
                <textarea
                  value={linesToText(criteria.title_priority)}
                  onChange={(e) => patch({ title_priority: textToLines(e.target.value) })}
                  rows={2}
                  style={inputStyle}
                />
              </label>
              <label className="hh-field">
                <span className="hh-label">Must-have</span>
                <textarea
                  value={linesToText(criteria.must_have)}
                  onChange={(e) => patch({ must_have: textToLines(e.target.value) })}
                  rows={2}
                  style={inputStyle}
                />
              </label>
              <label className="hh-field">
                <span className="hh-label">Отсев / red flags</span>
                <textarea
                  value={linesToText(criteria.reject)}
                  onChange={(e) => patch({ reject: textToLines(e.target.value) })}
                  rows={2}
                  style={inputStyle}
                />
              </label>
            </div>
          ) : null}

          <div className="hh-actions-secondary">
            <button
              type="button"
              className="chip"
              disabled={saving || prefilling}
              onClick={() => runPrefill()}
            >
              {prefilling ? "Prefill…" : "Заполнить из профиля"}
            </button>
            <button
              type="button"
              className="chip"
              disabled={saving || prefilling}
              onClick={() => saveCriteria(true)}
            >
              Пересобрать портрет из воронки
            </button>
            <button
              type="button"
              className="chip"
              disabled={saving || prefilling}
              onClick={() => saveCriteria(false)}
            >
              {saving ? "…" : "Сохранить"}
            </button>
          </div>
        </div>
      ) : null}

      {section === "funnel" ? (
        <div className="hh-section">
          <label className="hh-field">
            <span className="hh-label">Ключевые запросы</span>
            <span className="muted hh-label-hint">
              каждая строка — отдельный поиск; верхние строки важнее (больше слотов)
            </span>
            <textarea
              value={criteria.keywords}
              onChange={(e) => patch({ keywords: e.target.value })}
              rows={3}
              style={inputStyle}
            />
          </label>

          <label className="hh-field" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <input
              type="checkbox"
              checked={criteria.smart_prefilter !== false}
              onChange={(e) => patch({ smart_prefilter: e.target.checked })}
            />
            <span>
              <span className="hh-label">Умный отсев до оценки</span>
              <span className="muted hh-label-hint" style={{ display: "block" }}>
                Режет руководителей/reject по title до ИИ; при недоборе добирает «мягких»
              </span>
            </span>
          </label>

          <div className="hh-funnel-grid">
            <label className="hh-field">
              <span className="hh-label">Город</span>
              <select
                value={criteria.area_id ?? ""}
                onChange={(e) => {
                  const id = e.target.value ? Number(e.target.value) : null;
                  const preset = areaPresets.find((a) => a.id === id);
                  patch({ area_id: id, area_name: preset?.name || criteria.area_name });
                }}
                style={inputStyle}
              >
                <option value="">Не задан</option>
                {areaPresets.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="hh-field">
              <span className="hh-label">График</span>
              <select
                value={criteria.schedule}
                onChange={(e) => patch({ schedule: e.target.value })}
                style={inputStyle}
              >
                {scheduleOptions.map((o) => (
                  <option key={o.id || "none"} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="hh-field">
              <span className="hh-label">Обновлено за</span>
              <select
                value={criteria.period_days ?? ""}
                onChange={(e) =>
                  patch({ period_days: e.target.value ? Number(e.target.value) : null })
                }
                style={inputStyle}
              >
                <option value="">Без ограничения</option>
                <option value={7}>7 дней</option>
                <option value={14}>14 дней</option>
                <option value={30}>30 дней</option>
                <option value={90}>90 дней</option>
              </select>
            </label>
            <label className="hh-field">
              <span className="hh-label">Зарплата до</span>
              <input
                type="number"
                value={criteria.salary_to ?? ""}
                onChange={(e) =>
                  patch({ salary_to: e.target.value ? Number(e.target.value) : null })
                }
                style={inputStyle}
              />
            </label>
            <label className="hh-field">
              <span className="hh-label">Офис</span>
              <select
                value={criteria.office_required}
                onChange={(e) =>
                  patch({
                    office_required: e.target.value as Criteria["office_required"],
                  })
                }
                style={inputStyle}
              >
                <option value="first_3_months">Первые 3 месяца</option>
                <option value="always">Постоянно</option>
                <option value="no">Не обязателен</option>
              </select>
            </label>
            <label className="hh-field">
              <span className="hh-label">Адрес / район</span>
              <input
                value={criteria.office_address}
                onChange={(e) => patch({ office_address: e.target.value })}
                style={inputStyle}
                placeholder="м. Алексеевская…"
              />
            </label>
            <label className="hh-field">
              <span className="hh-label">Дорога, мин</span>
              <input
                type="number"
                value={criteria.max_commute_min}
                onChange={(e) => patch({ max_commute_min: Number(e.target.value) || 60 })}
                style={inputStyle}
              />
            </label>
            <label className="hh-field">
              <span className="hh-label">Найти / оценить</span>
              <div className="hh-inline-pair">
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={criteria.max_search}
                  onChange={(e) => patch({ max_search: Number(e.target.value) || 20 })}
                  style={inputStyle}
                />
                <input
                  type="number"
                  min={0}
                  max={50}
                  value={criteria.max_evaluate}
                  onChange={(e) => patch({ max_evaluate: Number(e.target.value) || 0 })}
                  style={inputStyle}
                />
              </div>
            </label>
          </div>
        </div>
      ) : null}

      {section === "results" ? (
        <div className="hh-section">
          {history.length ? (
            <label className="hh-field" style={{ marginBottom: "0.75rem" }}>
              <span className="hh-label">Прошлые поиски</span>
              <select
                value={job?.id || ""}
                onChange={(e) => {
                  const id = e.target.value;
                  if (id) openHistoryJob(id).catch((err) => setError(String(err)));
                }}
                style={inputStyle}
              >
                {!job ? <option value="">Выберите поиск…</option> : null}
                {history.map((h) => {
                  const when = h.created_at
                    ? new Date(h.created_at).toLocaleString("ru-RU", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "—";
                  const stats =
                    h.found != null
                      ? ` · найдено ${h.found}${h.evaluated != null ? `, оценено ${h.evaluated}` : ""}`
                      : "";
                  const kw = h.keywords_short ? ` · ${h.keywords_short}` : "";
                  return (
                    <option key={h.id} value={h.id}>
                      {when} · {h.status}
                      {stats}
                      {kw}
                    </option>
                  );
                })}
              </select>
            </label>
          ) : null}
          {job ? (
            <p className="muted">
              {job.progress_label || job.status} · {job.progress_pct ?? 0}%
              {job.payload.found != null ? ` · найдено ${job.payload.found}` : ""}
              {job.payload.evaluated != null ? ` · оценено ${job.payload.evaluated}` : ""}
              {job.payload.prefilter?.seen_skip
                ? ` · уже смотрели ${job.payload.prefilter.seen_skip}`
                : ""}
              {job.payload.prefilter?.hard_skip
                ? ` · отсев до оценки ${job.payload.prefilter.hard_skip}`
                : ""}
              {job.payload.prefilter?.soft_backfill
                ? ` · добор ${job.payload.prefilter.soft_backfill}`
                : ""}
            </p>
          ) : (
            <p className="muted">Запустите поиск — результаты появятся здесь. Прошлые прогоны сохраняются и доступны в списке выше.</p>
          )}
          {job?.error ? <p className="warn">{job.error}</p> : null}

          {results.length ? (
            <table>
              <thead>
                <tr>
                  <th></th>
                  <th>Оценка</th>
                  <th>Совпадение</th>
                  <th>Должность</th>
                  <th>Город</th>
                  <th>Итог</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.hh_resume_id || r.url}>
                    <td>
                      {shortIds.has(r.hh_resume_id) ? (
                        <span className="muted">★</span>
                      ) : r.skipped_seen ? (
                        <span className="muted">—</span>
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          <button type="button" className="chip" onClick={() => addToShortlist(r)}>
                            ★
                          </button>
                          {!r.skipped_prefilter ? (
                            <button
                              type="button"
                              className="chip"
                              onClick={() => rejectCandidate(r)}
                              title="Не рассматривать снова"
                            >
                              ✕
                            </button>
                          ) : null}
                        </div>
                      )}
                    </td>
                    <td>
                      {r.ai_score != null ? (
                        <strong>{r.ai_score}/4</strong>
                      ) : r.skipped_eval ? (
                        <span className="muted">—</span>
                      ) : (
                        <span className="muted">…</span>
                      )}
                    </td>
                    <td className="row-meta">
                      Офис: {fitLabel(r.office_fit)} · Должность: {fitLabel(r.title_fit)} · Дорога:{" "}
                      {fitLabel(r.commute_ok)}
                    </td>
                    <td>
                      <div>{r.title || "—"}</div>
                      {r.error ? <div className="row-meta warn">{r.error}</div> : null}
                      {r.skipped_seen ? (
                        <div className="row-meta warn">
                          уже смотрели
                          {r.seen_label ? `: ${r.seen_label}` : ""}
                        </div>
                      ) : r.skipped_prefilter ? (
                        <div className="row-meta warn">
                          отсеян до оценки
                          {r.prefilter_reason ? `: ${r.prefilter_reason}` : ""}
                        </div>
                      ) : r.skipped_eval ? (
                        <div className="row-meta">без оценки ИИ</div>
                      ) : null}
                      {r.source_query ? (
                        <div className="row-meta">запрос: {r.source_query}</div>
                      ) : null}
                    </td>
                    <td>{r.area || "—"}</td>
                    <td className="row-meta">{r.ai_preview || "—"}</td>
                    <td>
                      {r.url ? (
                        <a href={r.url} target="_blank" rel="noreferrer">
                          HH
                        </a>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}

          <h3 className="hh-subhead">Shortlist ({shortlist.length})</h3>
          {lastFunnelLink ? (
            <p className="muted">
              Кандидат в воронке:{" "}
              <a href={`/candidates/${lastFunnelLink.id}`}>{lastFunnelLink.name}</a>
              {" · "}
              <a href={`/vacancies/${vacancyId}?section=candidates`}>к списку кандидатов</a>
            </p>
          ) : null}
          {shortlist.length ? (
            <table>
              <thead>
                <tr>
                  <th>Оценка</th>
                  <th>Должность</th>
                  <th>Город</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {shortlist.map((s) => (
                  <tr key={s.id}>
                    <td>{s.ai_score != null ? `${s.ai_score}/4` : "—"}</td>
                    <td>
                      {s.url ? (
                        <a href={s.url} target="_blank" rel="noreferrer">
                          {s.title || s.hh_resume_id}
                        </a>
                      ) : (
                        s.title || s.hh_resume_id
                      )}
                    </td>
                    <td>{s.area || "—"}</td>
                    <td className="hh-row-actions">
                      <button
                        type="button"
                        className="chip chip-active"
                        disabled={toFunnelBusy === s.id}
                        onClick={() => toFunnel(s)}
                      >
                        {toFunnelBusy === s.id ? "…" : "В воронку"}
                      </button>
                      <button type="button" className="chip" onClick={() => removeShortlist(s.id)}>
                        Убрать
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">Пока пусто — отметьте ★ в результатах.</p>
          )}
        </div>
      ) : null}

      <div className="hh-footer">
        {warningsHard.length ? (
          <div className="hh-warns">
            {warningsHard.map((w) => (
              <p key={w.code} className="warn">
                ⚠ {w.text}
              </p>
            ))}
          </div>
        ) : null}
        {warningsInfo.length ? (
          <div>
            <button type="button" className="chip" onClick={() => setShowInfoTips((v) => !v)}>
              {showInfoTips ? "Скрыть подсказки" : `Подсказки (${warningsInfo.length})`}
            </button>
            {showInfoTips
              ? warningsInfo.map((w) => (
                  <p key={w.code} className="muted">
                    ℹ {w.text}
                  </p>
                ))
              : null}
          </div>
        ) : null}
        <div className="hh-footer-actions">
          {section !== "funnel" ? (
            <button type="button" className="chip" onClick={() => setSection("funnel")}>
              К воронке
            </button>
          ) : null}
          {section !== "who" ? (
            <button type="button" className="chip" onClick={() => setSection("who")}>
              К портрету
            </button>
          ) : null}
          <button
            type="button"
            className="chip chip-active"
            disabled={busy || prefilling}
            onClick={onStart}
          >
            {busy ? "Поиск…" : "Искать на HH"}
          </button>
        </div>
      </div>
    </div>
  );
}
