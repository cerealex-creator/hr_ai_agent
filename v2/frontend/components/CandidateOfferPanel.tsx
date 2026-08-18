"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/components/AuthGate";
import { DEMO_WRITE_HINT } from "@/lib/demo";

export type OfferDraft = {
  greeting: string;
  name_patronymic: string;
  full_name: string;
  company: string;
  position: string;
  office_address: string;
  work_schedule: string;
  start_date: string;
  probation_months: string;
  salary_probation_base: string;
  salary_probation_bonus: string;
  salary_probation_line: string;
  salary_after_base: string;
  salary_after_bonus: string;
  salary_after_line: string;
  duties: string;
  manager_name: string;
  logo_data_url?: string | null;
  company_client_id?: number | null;
};

type Props = {
  candidateId: string;
};

type OfferTemplateInfo = {
  source: string;
  filename?: string | null;
  has_custom: boolean;
  can_upload: boolean;
};

function composeLine(base: string, bonus: string): string {
  const b = base.trim();
  const p = bonus.trim();
  if (b && p) return p.startsWith("+") ? `${b} ${p}` : `${b} + ${p}`;
  return b || p;
}

async function readError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string" && data.detail.trim()) return data.detail;
  } catch {
    /* ignore */
  }
  return `Ошибка ${res.status}`;
}

export function CandidateOfferPanel({ candidateId }: Props) {
  const { isDemo } = useAuth();
  const [draft, setDraft] = useState<OfferDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [templateInfo, setTemplateInfo] = useState<OfferTemplateInfo | null>(null);

  const loadTemplate = async () => {
    try {
      const res = await apiFetch("/api/v1/settings/offer-template");
      if (!res.ok) return;
      setTemplateInfo((await res.json()) as OfferTemplateInfo);
    } catch {
      /* ignore */
    }
  };

  const load = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidateId}/offer`);
      if (!res.ok) throw new Error(await readError(res));
      setDraft((await res.json()) as OfferDraft);
      setDirty(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось загрузить оффер");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void load();
    void loadTemplate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidateId]);

  const patch = (partial: Partial<OfferDraft>) => {
    setDraft((prev) => {
      if (!prev) return prev;
      const next = { ...prev, ...partial };
      if ("salary_probation_base" in partial || "salary_probation_bonus" in partial) {
        next.salary_probation_line = composeLine(
          next.salary_probation_base,
          next.salary_probation_bonus,
        );
      }
      if ("salary_after_base" in partial || "salary_after_bonus" in partial) {
        next.salary_after_line = composeLine(next.salary_after_base, next.salary_after_bonus);
      }
      return next;
    });
    setDirty(true);
    setMsg(null);
  };

  const save = async () => {
    if (isDemo) {
      setErr(DEMO_WRITE_HINT);
      return;
    }
    if (!draft) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const { logo_data_url: _l, company_client_id: _c, ...body } = draft;
      const res = await apiFetch(`/api/v1/candidates/${candidateId}/offer`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await readError(res));
      setDraft((await res.json()) as OfferDraft);
      setDirty(false);
      setMsg("Черновик сохранён");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  };

  const prefill = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidateId}/offer/prefill`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await readError(res));
      setDraft((await res.json()) as OfferDraft);
      setDirty(false);
      setMsg("Заполнено из данных карточки и компании");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка заполнения");
    } finally {
      setBusy(false);
    }
  };

  const aiFill = async () => {
    setBusy(true);
    setErr(null);
    setMsg("ИИ думает… обычно 20–60 сек, не закрывайте вкладку");
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidateId}/offer/ai-fill`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await readError(res));
      setDraft((await res.json()) as OfferDraft);
      setDirty(false);
      setMsg("ИИ дописал режим / обязанности (проверьте текст)");
    } catch (e) {
      const text = e instanceof Error ? e.message : "Ошибка ИИ";
      if (/500|502|Failed to fetch|network|hang up|aborted/i.test(text)) {
        setErr(
          `${text}. Если запрос долгий — перезапустите npm run dev (нужен proxyTimeout) и повторите.`,
        );
      } else {
        setErr(text);
      }
      setMsg(null);
    } finally {
      setBusy(false);
    }
  };

  const download = async () => {
    if (dirty && !isDemo) {
      await save();
    }
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidateId}/offer.docx`);
      if (!res.ok) throw new Error(await readError(res));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `offer_${(draft?.full_name || "candidate").replace(/\s+/g, "_")}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setMsg("Word скачан");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось скачать");
    } finally {
      setBusy(false);
    }
  };

  const onLogoFile = async (file: File | null) => {
    if (!draft?.company_client_id || !file) return;
    if (!file.type.startsWith("image/")) {
      setErr("Нужен файл изображения (PNG/JPG)");
      return;
    }
    if (file.size > 1_200_000) {
      setErr("Логотип больше 1.2 МБ — сожмите файл");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(new Error("Не удалось прочитать файл"));
        reader.readAsDataURL(file);
      });
      const res = await apiFetch(`/api/v1/clients/${draft.company_client_id}/offer-branding`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ logo_data_url: dataUrl }),
      });
      if (!res.ok) throw new Error(await readError(res));
      setDraft((prev) => (prev ? { ...prev, logo_data_url: dataUrl } : prev));
      setMsg("Логотип компании сохранён");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки лого");
    } finally {
      setBusy(false);
    }
  };

  const clearLogo = async () => {
    if (!draft?.company_client_id) return;
    setBusy(true);
    try {
      const res = await apiFetch(`/api/v1/clients/${draft.company_client_id}/offer-branding`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ logo_data_url: "" }),
      });
      if (!res.ok) throw new Error(await readError(res));
      setDraft((prev) => (prev ? { ...prev, logo_data_url: null } : prev));
      setMsg("Логотип убран");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const onTemplateFile = async (file: File | null) => {
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await apiFetch("/api/v1/settings/offer-template", { method: "POST", body });
      if (!res.ok) throw new Error(await readError(res));
      setTemplateInfo((await res.json()) as OfferTemplateInfo);
      setMsg("Шаблон Word сохранён — используется при следующем скачивании");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось загрузить шаблон");
    } finally {
      setBusy(false);
    }
  };

  const clearTemplate = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch("/api/v1/settings/offer-template", { method: "DELETE" });
      if (!res.ok) throw new Error(await readError(res));
      setTemplateInfo((await res.json()) as OfferTemplateInfo);
      setMsg("Ваш шаблон убран — снова встроенный");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const templateLabel = (() => {
    if (!templateInfo) return "…";
    if (templateInfo.source === "env") return "Задан в OFFER_TEMPLATE_PATH";
    if (templateInfo.has_custom) return `Ваш шаблон: ${templateInfo.filename || "offer_template.docx"}`;
    return "Встроенный шаблон";
  })();

  if (!draft) {
    return (
      <div className="rec-card">
        {err ? <p className="warn">{err}</p> : <p className="muted">Загрузка оффера…</p>}
      </div>
    );
  }

  return (
    <div className="offer-panel">
      <div className="offer-mock-toolbar">
        <div className="offer-mock-toolbar-left">
          <span className={`rec-badge ${dirty ? "rec-badge-orange" : "rec-badge-teal"}`}>
            {dirty ? "Есть несохранённые правки" : "Черновик"}
          </span>
          <span className="muted hh-micro">Авто / ИИ / ручная правка → Word</span>
        </div>
        <div className="offer-mock-toolbar-actions">
          {isDemo ? (
            <button type="button" className="chip chip-active" disabled={busy} onClick={() => void download()}>
              Скачать Word
            </button>
          ) : (
            <>
          <button type="button" className="chip" disabled={busy} onClick={() => void prefill()}>
            Заполнить из данных
          </button>
          <button type="button" className="chip" disabled={busy} onClick={() => void aiFill()}>
            Дописать ИИ
          </button>
          <button type="button" className="chip" disabled={busy || !dirty} onClick={() => void save()}>
            Сохранить
          </button>
          <button type="button" className="chip chip-active" disabled={busy} onClick={() => void download()}>
            Скачать Word
          </button>
            </>
          )}
        </div>
      </div>

      {isDemo ? <p className="muted hh-micro">{DEMO_WRITE_HINT} Скачать Word можно.</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <div className="offer-mock-grid">
        <section className="rec-card offer-mock-card">
          <h2 className="rec-card-title">Данные письма</h2>
          <div className="offer-mock-fields">
            <Field label="Обращение" auto value={draft.greeting} onChange={(v) => patch({ greeting: v })} />
            <Field
              label="Имя и отчество"
              auto
              value={draft.name_patronymic}
              onChange={(v) => patch({ name_patronymic: v })}
            />
            <Field
              label="ФИО полностью"
              auto
              value={draft.full_name}
              onChange={(v) => patch({ full_name: v })}
            />
            <Field label="Компания" auto value={draft.company} onChange={(v) => patch({ company: v })} />
            <Field label="Должность" auto value={draft.position} onChange={(v) => patch({ position: v })} />
            <Field
              label="Адрес офиса"
              value={draft.office_address}
              onChange={(v) => patch({ office_address: v })}
            />
            <Field
              label="Режим рабочего дня"
              multiline
              value={draft.work_schedule}
              onChange={(v) => patch({ work_schedule: v })}
            />
            <div className="offer-mock-row2">
              <Field label="Дата выхода" value={draft.start_date} onChange={(v) => patch({ start_date: v })} />
              <Field
                label="Испытательный срок"
                hint="только число, напр. 3 → «3 месяца»"
                value={draft.probation_months}
                onChange={(v) => patch({ probation_months: v })}
              />
            </div>

            <div className="offer-mock-pay-block">
              <p className="offer-mock-pay-title">Оплата на испытательном сроке</p>
              <Field
                label="Оклад / формулировка"
                value={draft.salary_probation_base}
                onChange={(v) => patch({ salary_probation_base: v })}
              />
              <Field
                label="Премирование на ИС"
                hint="опционально"
                multiline
                value={draft.salary_probation_bonus}
                onChange={(v) => patch({ salary_probation_bonus: v })}
              />
              <Field
                label="Итоговая строка для письма (ИС)"
                multiline
                value={draft.salary_probation_line}
                onChange={(v) => patch({ salary_probation_line: v })}
              />
            </div>

            <div className="offer-mock-pay-block">
              <p className="offer-mock-pay-title">Оплата после испытательного срока</p>
              <Field
                label="Оклад / формулировка"
                value={draft.salary_after_base}
                onChange={(v) => patch({ salary_after_base: v })}
              />
              <Field
                label="Премирование после ИС"
                hint="опционально"
                multiline
                value={draft.salary_after_bonus}
                onChange={(v) => patch({ salary_after_bonus: v })}
              />
              <Field
                label="Итоговая строка для письма (после ИС)"
                multiline
                value={draft.salary_after_line}
                onChange={(v) => patch({ salary_after_line: v })}
              />
            </div>

            <Field
              label="ФИО руководителя"
              value={draft.manager_name}
              onChange={(v) => patch({ manager_name: v })}
            />
          </div>
        </section>

        <div className="offer-mock-side">
          <section className="rec-card offer-mock-card">
            <h2 className="rec-card-title">Логотип компании</h2>
            <p className="muted hh-micro">В Word — в верхний колонтитул. Хранится у компании.</p>
            <div className="offer-mock-logo-box">
              {draft.logo_data_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={draft.logo_data_url} alt="Логотип" style={{ maxHeight: 72, maxWidth: "90%" }} />
              ) : (
                <span className="offer-mock-logo-mark">Нет лого</span>
              )}
            </div>
            {isDemo ? null : (
            <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
              <label className="chip" style={{ cursor: busy || !draft.company_client_id ? "default" : "pointer" }}>
                Загрузить лого
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  hidden
                  disabled={busy || !draft.company_client_id}
                  onChange={(e) => void onLogoFile(e.target.files?.[0] || null)}
                />
              </label>
              <button
                type="button"
                className="chip"
                disabled={busy || !draft.logo_data_url}
                onClick={() => void clearLogo()}
              >
                Убрать
              </button>
            </div>
            )}
          </section>

          <section className="rec-card offer-mock-card">
            <h2 className="rec-card-title">Шаблон Word</h2>
            <p className="muted hh-micro">
              Сейчас: <strong>{templateLabel}</strong>. В тексте шаблона — плейсхолдеры{" "}
              <code>{`{{position}}`}</code>, <code>{`{{duties}}`}</code> и др. (см. OFFER_TEMPLATE.md).
            </p>
            {isDemo ? null : (
            <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
              <label
                className="chip"
                style={{
                  cursor: busy || !templateInfo?.can_upload ? "default" : "pointer",
                }}
              >
                Загрузить .docx
                <input
                  type="file"
                  accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  hidden
                  disabled={busy || !templateInfo?.can_upload}
                  onChange={(e) => void onTemplateFile(e.target.files?.[0] || null)}
                />
              </label>
              <button
                type="button"
                className="chip"
                disabled={busy || !templateInfo?.has_custom || !templateInfo?.can_upload}
                onClick={() => void clearTemplate()}
              >
                Встроенный шаблон
              </button>
            </div>
            )}
          </section>

          <section className="rec-card offer-mock-card">
            <h2 className="rec-card-title">Обязанности</h2>
            <p className="muted hh-micro">Список пунктов. ИИ может набросать из профиля вакансии.</p>
            <textarea
              className="offer-mock-textarea"
              rows={12}
              value={draft.duties}
              readOnly={isDemo}
              disabled={busy && !isDemo}
              onChange={(e) => patch({ duties: e.target.value })}
            />
          </section>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  hint,
  auto,
  multiline,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
  auto?: boolean;
  multiline?: boolean;
}) {
  const { isDemo } = useAuth();
  return (
    <label className="hh-field offer-mock-field">
      <span className="hh-label">
        {label}
        {auto ? <span className="offer-mock-auto">авто</span> : null}
        {hint ? <span className="muted hh-micro"> · {hint}</span> : null}
      </span>
      {multiline ? (
        <textarea
          className="offer-mock-textarea"
          rows={3}
          value={value}
          readOnly={isDemo}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input type="text" value={value} readOnly={isDemo} onChange={(e) => onChange(e.target.value)} />
      )}
    </label>
  );
}
