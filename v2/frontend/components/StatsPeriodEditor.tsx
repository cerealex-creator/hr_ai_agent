"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export type StatsLinkBase = {
  mode: string;
  companyId: number | null;
  allCompanies?: boolean;
  deptId: number | null;
  vacancyId: number | null;
  scope: string;
};

type Props = {
  linkBase: StatsLinkBase;
  dateFrom: string; // YYYY-MM-DD
  dateTo: string;
  period: string;
  presets: { id: string; label: string }[];
};

function hrefFor(
  base: StatsLinkBase,
  opts: { period?: string; from?: string; to?: string },
): string {
  const params = new URLSearchParams();
  if (base.mode === "executive" || base.mode === "ai") params.set("mode", base.mode);
  if (base.allCompanies) params.set("company", "all");
  else if (base.companyId != null) params.set("company", String(base.companyId));
  if (base.deptId != null) params.set("dept", String(base.deptId));
  if (base.vacancyId != null) params.set("vacancy", String(base.vacancyId));
  if (base.scope === "all") params.set("scope", "all");

  const period = opts.period ?? "day";
  const from = opts.from ?? "";
  const to = opts.to ?? "";

  if (from || to || period === "custom") {
    params.set("period", "custom");
    if (from) params.set("from", from);
    if (to) params.set("to", to);
  } else {
    const defaultPeriod = "day";
    if (period && period !== defaultPeriod) params.set("period", period);
  }

  const q = params.toString();
  return q ? `/stats?${q}` : "/stats";
}

export function StatsPeriodEditor({ linkBase, dateFrom, dateTo, period, presets }: Props) {
  const router = useRouter();
  const [from, setFrom] = useState(dateFrom);
  const [to, setTo] = useState(dateTo);

  useEffect(() => {
    setFrom(dateFrom);
    setTo(dateTo);
  }, [dateFrom, dateTo]);

  const isCustom = period === "custom" || Boolean(dateFrom || dateTo);

  const applyCustom = () => {
    if (!from && !to) return;
    router.push(hrefFor(linkBase, { period: "custom", from, to }));
  };

  return (
    <div className="stats-period-editor">
      <div className="stats-period-dates">
        <label className="stats-period-field">
          <span>с</span>
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label className="stats-period-field">
          <span>по</span>
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
        <button type="button" className="chip chip-active" onClick={applyCustom}>
          Применить
        </button>
      </div>
      <div className="chip-row stats-period-presets">
        {presets.map((p) => (
          <Link
            key={p.id}
            href={hrefFor(linkBase, { period: p.id, from: "", to: "" })}
            className={!isCustom && period === p.id ? "chip chip-active" : "chip"}
          >
            {p.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
