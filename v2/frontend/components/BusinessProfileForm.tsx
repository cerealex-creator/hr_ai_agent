"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  completeMgmtWizardStep2Profile,
  fetchMgmtBusinessProfile,
  fetchMgmtBusinessProfileSchema,
  saveMgmtBusinessProfile,
  type MgmtBusinessProfile,
  type MgmtBusinessProfileSchema,
} from "@/lib/management";

type Props = {
  onComplete?: () => void;
  showCompleteButton?: boolean;
};

export function BusinessProfileForm({ onComplete, showCompleteButton = true }: Props) {
  const [schema, setSchema] = useState<MgmtBusinessProfileSchema | null>(null);
  const [profile, setProfile] = useState<MgmtBusinessProfile | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [industryCode, setIndustryCode] = useState("");
  const [industryCustom, setIndustryCustom] = useState("");
  const [businessModel, setBusinessModel] = useState("");
  const [marketType, setMarketType] = useState("");
  const [scaleBand, setScaleBand] = useState("");
  const [maturityStage, setMaturityStage] = useState("");
  const [horizonMonths, setHorizonMonths] = useState<number | "">("");
  const [priorities, setPriorities] = useState<string[]>([]);
  const [constraints, setConstraints] = useState("");
  const [optOut, setOptOut] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const [s, p] = await Promise.all([
          fetchMgmtBusinessProfileSchema(),
          fetchMgmtBusinessProfile(),
        ]);
        setSchema(s);
        setProfile(p);
        setIndustryCode(p.industry_code || "");
        setIndustryCustom(p.industry_custom || "");
        setBusinessModel(p.business_model || "");
        setMarketType(p.market_type || "");
        setScaleBand(p.scale_band || "");
        setMaturityStage(p.maturity_stage || "");
        setHorizonMonths(p.horizon_months || "");
        setPriorities(p.priorities || []);
        setConstraints(p.constraints_text || "");
        setOptOut(p.sensitive_metrics_opt_out);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
  }, []);

  function togglePriority(code: string) {
    setPriorities((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code].slice(0, 6)
    );
  }

  async function onSave(e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const saved = await saveMgmtBusinessProfile({
        industry_code: industryCode || null,
        industry_custom: industryCode === "other" ? industryCustom : industryCustom || null,
        business_model: businessModel || null,
        market_type: marketType || null,
        scale_band: scaleBand || null,
        maturity_stage: maturityStage || null,
        horizon_months: horizonMonths === "" ? null : Number(horizonMonths),
        priorities,
        constraints_text: constraints || null,
        sensitive_metrics_opt_out: optOut,
      });
      setProfile(saved);
      setMsg("Паспорт сохранён");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  }

  async function onCompleteStep() {
    setBusy(true);
    setErr(null);
    try {
      await onSave();
      await completeMgmtWizardStep2Profile();
      setMsg("Паспорт утверждён — переход к целям по блокам");
      onComplete?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  if (!schema) return <p className="muted">Загрузка паспорта…</p>;

  return (
    <form className="mgmt-form-col mgmt-profile-form" onSubmit={(e) => void onSave(e)}>
      <p className="muted">
        Кратко опишите бизнес — без обязательных чувствительных цифр. Это поможет ИИ предложить уместные цели.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <label>
        Отрасль *
        <select value={industryCode} onChange={(e) => setIndustryCode(e.target.value)}>
          <option value="">— выберите —</option>
          {schema.industries.map((o) => (
            <option key={o.code} value={o.code}>{o.label}</option>
          ))}
        </select>
      </label>
      {industryCode === "other" ? (
        <label>
          Уточните отрасль
          <input value={industryCustom} onChange={(e) => setIndustryCustom(e.target.value)} placeholder="например, логистика" />
        </label>
      ) : null}

      <label>
        Модель бизнеса *
        <select value={businessModel} onChange={(e) => setBusinessModel(e.target.value)}>
          <option value="">— выберите —</option>
          {schema.business_models.map((o) => (
            <option key={o.code} value={o.code}>{o.label}</option>
          ))}
        </select>
      </label>

      <label>
        Рынок
        <select value={marketType} onChange={(e) => setMarketType(e.target.value)}>
          <option value="">— не указано —</option>
          {schema.market_types.map((o) => (
            <option key={o.code} value={o.code}>{o.label}</option>
          ))}
        </select>
      </label>

      <label>
        Масштаб *
        <select value={scaleBand} onChange={(e) => setScaleBand(e.target.value)}>
          <option value="">— выберите —</option>
          {schema.scale_bands.map((o) => (
            <option key={o.code} value={o.code}>{o.label}</option>
          ))}
        </select>
      </label>

      <label>
        Стадия
        <select value={maturityStage} onChange={(e) => setMaturityStage(e.target.value)}>
          <option value="">— не указано —</option>
          {schema.maturity_stages.map((o) => (
            <option key={o.code} value={o.code}>{o.label}</option>
          ))}
        </select>
      </label>

      <label>
        Горизонт планирования *
        <select
          value={horizonMonths === "" ? "" : String(horizonMonths)}
          onChange={(e) => setHorizonMonths(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">— выберите —</option>
          {schema.horizons.map((h) => (
            <option key={h.months} value={h.months}>{h.label}</option>
          ))}
        </select>
      </label>

      <fieldset className="mgmt-priority-fieldset">
        <legend>Приоритеты (до 6)</legend>
        <div className="mgmt-dimensions">
          {schema.priorities.map((p) => (
            <label key={p.code} className="mgmt-dim-chip">
              <input
                type="checkbox"
                checked={priorities.includes(p.code)}
                onChange={() => togglePriority(p.code)}
              />
              {p.label}
            </label>
          ))}
        </div>
      </fieldset>

      <label>
        Ограничения и особенности
        <textarea
          rows={3}
          value={constraints}
          onChange={(e) => setConstraints(e.target.value)}
          placeholder="например, нельзя нанимать до закрытия раунда"
        />
      </label>

      <label className="mgmt-check-row">
        <input type="checkbox" checked={optOut} onChange={(e) => setOptOut(e.target.checked)} />
        Предпочитаю не указывать чувствительные цифры (выручка, маржа)
      </label>

      <div className="mgmt-form-row">
        <button type="submit" disabled={busy}>Сохранить</button>
        {showCompleteButton ? (
          <button type="button" disabled={busy} onClick={() => void onCompleteStep()}>
            Далее — цели по блокам
          </button>
        ) : null}
      </div>
      {profile?.status === "complete" ? <p className="muted">Статус: заполнен</p> : null}
    </form>
  );
}
