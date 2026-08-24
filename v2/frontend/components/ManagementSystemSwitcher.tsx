"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  activateMgmtSystem,
  createMgmtSystem,
  fetchMgmtSystems,
  type MgmtSystem,
} from "@/lib/management";

type Props = {
  onChanged?: () => void;
};

const KIND_LABEL: Record<string, string> = {
  company: "Компания",
  holding: "Холдинг",
  demo: "Демо",
};

export function ManagementSystemSwitcher({ onChanged }: Props) {
  const [systems, setSystems] = useState<MgmtSystem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"company" | "holding" | "demo">("company");
  const [parentId, setParentId] = useState("");

  const reload = useCallback(async () => {
    try {
      const data = await fetchMgmtSystems();
      setSystems(data.systems);
      setActiveId(data.active_system_id);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const holdings = systems.filter((s) => s.kind === "holding");

  async function onSelect(systemId: string) {
    if (systemId === activeId) return;
    setBusy(true);
    setErr(null);
    try {
      await activateMgmtSystem(systemId);
      await reload();
      onChanged?.();
      if (typeof window !== "undefined") window.location.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await createMgmtSystem({
        title: title.trim(),
        kind,
        parent_system_id: kind === "company" && parentId ? parentId : null,
        activate: true,
      });
      setTitle("");
      setShowCreate(false);
      await reload();
      onChanged?.();
      if (typeof window !== "undefined") window.location.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mgmt-system-switcher">
      <label className="mgmt-system-switcher-label">
        Система / компания
        <select
          value={activeId || ""}
          disabled={busy || !systems.length}
          onChange={(e) => void onSelect(e.target.value)}
        >
          {systems.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title} ({KIND_LABEL[s.kind] || s.kind})
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="mgmt-btn-secondary"
        disabled={busy}
        onClick={() => setShowCreate((v) => !v)}
      >
        {showCreate ? "Скрыть" : "+ Новая"}
      </button>
      {err ? <p className="warn" style={{ margin: "0.35rem 0 0", fontSize: 12 }}>{err}</p> : null}
      {showCreate ? (
        <form className="mgmt-system-create" onSubmit={(e) => void onCreate(e)}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Название (ООО Ромашка / Демо презентация)"
            required
          />
          <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
            <option value="company">Компания</option>
            <option value="holding">Холдинг (общие цели)</option>
            <option value="demo">Демо / презентация</option>
          </select>
          {kind === "company" && holdings.length ? (
            <select value={parentId} onChange={(e) => setParentId(e.target.value)}>
              <option value="">Без холдинга</option>
              {holdings.map((h) => (
                <option key={h.id} value={h.id}>{h.title}</option>
              ))}
            </select>
          ) : null}
          <button type="submit" disabled={busy}>Создать и открыть</button>
        </form>
      ) : null}
    </div>
  );
}
