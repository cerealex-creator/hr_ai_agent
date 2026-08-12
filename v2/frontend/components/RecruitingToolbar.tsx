"use client";

import Link from "next/link";
import { Filter, Search } from "lucide-react";

type Props = {
  filterHref?: string;
};

/** Верхняя панель: pill-поиск (якорь) + фильтр. */
export function RecruitingToolbar({ filterHref = "/stats" }: Props) {
  return (
    <div className="rec-toolbar-inner">
      <Link href="#cand-search" className="rec-search-pill">
        <Search strokeWidth={2.25} aria-hidden />
        <span>Поиск кандидатов</span>
      </Link>
      <Link href={filterHref} className="rec-filter-btn" aria-label="Фильтры и статистика">
        <Filter strokeWidth={2.25} aria-hidden />
      </Link>
    </div>
  );
}
