"use client";

import { useMemo, useState } from "react";
import { CandidateCompactRow } from "@/components/CandidateCompactRow";
import type { CandidateGroup } from "@/lib/groupCandidates";

const DEFAULT_VISIBLE = 6;

type Props = {
  groups: CandidateGroup[];
  showAttentionReason?: boolean;
  emptyMessage?: string;
};

export function CandidatesGroupedList({
  groups,
  showAttentionReason = false,
  emptyMessage = "Нет кандидатов в этой выборке",
}: Props) {
  /** true = свёрнута (показаны первые N). */
  const [folded, setFolded] = useState<Record<string, boolean>>({});

  const defaultFolded = useMemo(() => {
    const map: Record<string, boolean> = {};
    for (const g of groups) {
      map[g.key] = g.key !== "attention" && g.items.length > DEFAULT_VISIBLE;
    }
    return map;
  }, [groups]);

  if (!groups.length) {
    return <p className="rec-empty">{emptyMessage}</p>;
  }

  return (
    <div className="rec-groups">
      {groups.map((group) => {
        const isFolded = folded[group.key] ?? defaultFolded[group.key] ?? false;
        const visible = isFolded ? group.items.slice(0, DEFAULT_VISIBLE) : group.items;
        const hidden = group.items.length - visible.length;
        const isAttention = group.key === "attention";

        return (
          <section key={group.key} className={`rec-group rec-group-${group.tone}`}>
            <header className="rec-group-head">
              <h2 className="rec-group-title">{group.title}</h2>
              <span className="rec-group-count">{group.items.length}</span>
            </header>
            <ul className="rec-group-list">
              {visible.map((c) => (
                <li key={c.id}>
                  <CandidateCompactRow
                    candidate={c}
                    showAttentionReason={showAttentionReason || isAttention}
                  />
                </li>
              ))}
            </ul>
            {isFolded && hidden > 0 ? (
              <button
                type="button"
                className="rec-group-more"
                onClick={() => setFolded((prev) => ({ ...prev, [group.key]: false }))}
              >
                Показать ещё {hidden}
              </button>
            ) : null}
            {!isFolded && group.items.length > DEFAULT_VISIBLE ? (
              <button
                type="button"
                className="rec-group-more"
                onClick={() => setFolded((prev) => ({ ...prev, [group.key]: true }))}
              >
                Свернуть группу
              </button>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}
