"use client";

import { useState } from "react";
import { apiFetch, type CandidateDetail } from "@/lib/api";
import { X } from "lucide-react";

type Props = {
  candidate: CandidateDetail;
  onUpdate?: (c: CandidateDetail) => void;
  readOnly?: boolean;
};

export function CandidateTags({ candidate, onUpdate, readOnly }: Props) {
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  const tags = candidate.tags || [];

  const addTag = async (tag: string) => {
    const t = tag.trim();
    if (!t || tags.includes(t)) return;
    const next = [...tags, t];
    setSaving(true);
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidate.id}/tags`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tags: next }),
      });
      if (res.ok) onUpdate?.((await res.json()) as CandidateDetail);
    } finally {
      setSaving(false);
    }
    setInput("");
  };

  const removeTag = async (tag: string) => {
    const next = tags.filter((t) => t !== tag);
    setSaving(true);
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidate.id}/tags`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tags: next }),
      });
      if (res.ok) onUpdate?.((await res.json()) as CandidateDetail);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="cand-tags">
      <div className="cand-tags-list">
        {tags.map((t) => (
          <span key={t} className="cand-tag">
            {t}
            {!readOnly && (
              <button
                type="button"
                className="cand-tag-remove"
                disabled={saving}
                onClick={() => void removeTag(t)}
                aria-label={`Убрать тег ${t}`}
              >
                <X size={12} />
              </button>
            )}
          </span>
        ))}
      </div>
      {!readOnly && (
        <form
          className="cand-tag-form"
          onSubmit={(e) => {
            e.preventDefault();
            void addTag(input);
          }}
        >
          <input
            type="text"
            className="cand-tag-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Добавить тег…"
            disabled={saving}
          />
        </form>
      )}
    </div>
  );
}
