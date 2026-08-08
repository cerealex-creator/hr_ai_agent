"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "@/components/AuthGate";
import {
  fetchUsefulLinks,
  saveUsefulLinks,
  type UsefulLink,
} from "@/lib/api";

const PRESET_LINKS: UsefulLink[] = [
  {
    id: "preset-telemost",
    label: "Яндекс Телемост",
    url: "https://telemost.yandex.ru",
  },
  { id: "preset-zoom", label: "Zoom", url: "https://app.zoom.us" },
  {
    id: "preset-gdrive",
    label: "Google Диск",
    url: "https://drive.google.com",
  },
  {
    id: "preset-yadisk",
    label: "Яндекс Диск",
    url: "https://disk.yandex.ru",
  },
];

const LS_KEY = "hr_useful_links_v1";

function loadLocalCustom(): UsefulLink[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((x): x is UsefulLink => Boolean(x && typeof x === "object"))
      .map((x) => ({
        id: String((x as UsefulLink).id || crypto.randomUUID()),
        label: String((x as UsefulLink).label || "").trim(),
        url: String((x as UsefulLink).url || "").trim(),
      }))
      .filter((x) => x.label && /^https?:\/\//i.test(x.url));
  } catch {
    return [];
  }
}

function saveLocalCustom(items: UsefulLink[]) {
  localStorage.setItem(LS_KEY, JSON.stringify(items));
}

export function UsefulLinksBar() {
  const { user } = useAuth();
  const [custom, setCustom] = useState<UsefulLink[]>([]);
  const [useLocal, setUseLocal] = useState(false);
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchUsefulLinks();
        if (cancelled) return;
        if (data.auth_disabled || user?.auth_disabled) {
          setUseLocal(true);
          setCustom(loadLocalCustom());
        } else {
          setUseLocal(false);
          setCustom(data.items || []);
        }
      } catch {
        if (cancelled) return;
        setUseLocal(true);
        setCustom(loadLocalCustom());
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.id, user?.auth_disabled]);

  const persist = async (next: UsefulLink[]) => {
    setBusy(true);
    setError("");
    try {
      if (useLocal) {
        saveLocalCustom(next);
        setCustom(next);
      } else {
        const saved = await saveUsefulLinks(next);
        setCustom(saved);
      }
      setAdding(false);
      setLabel("");
      setUrl("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
    } finally {
      setBusy(false);
    }
  };

  const onAdd = (e: FormEvent) => {
    e.preventDefault();
    const nextLabel = label.trim();
    let nextUrl = url.trim();
    if (!nextLabel) {
      setError("Укажите название");
      return;
    }
    if (!nextUrl) {
      setError("Укажите ссылку");
      return;
    }
    if (!/^https?:\/\//i.test(nextUrl)) {
      nextUrl = `https://${nextUrl}`;
    }
    void persist([
      ...custom,
      { id: crypto.randomUUID(), label: nextLabel, url: nextUrl },
    ]);
  };

  const onRemove = (id: string) => {
    void persist(custom.filter((x) => x.id !== id));
  };

  return (
    <div className="useful-links useful-links-side" aria-label="Полезные ссылки">
      <div className="sidebar-title">Сервисы</div>
      <div className="useful-links-row">
        {PRESET_LINKS.map((item) => (
          <a
            key={item.id}
            className="useful-link-chip"
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {item.label}
          </a>
        ))}
        {custom.map((item) => (
          <span key={item.id} className="useful-link-custom">
            <a
              className="useful-link-chip"
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              title={item.url}
            >
              {item.label}
            </a>
            <button
              type="button"
              className="useful-link-remove"
              aria-label={`Удалить ${item.label}`}
              disabled={busy}
              onClick={() => onRemove(item.id)}
            >
              ×
            </button>
          </span>
        ))}
        {!adding ? (
          <button
            type="button"
            className="useful-link-add"
            onClick={() => {
              setAdding(true);
              setError("");
            }}
          >
            Добавить сервис
          </button>
        ) : null}
      </div>
      {adding ? (
        <form className="useful-links-form" onSubmit={onAdd}>
          <input
            type="text"
            placeholder="Название"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            maxLength={64}
            disabled={busy}
            autoFocus
          />
          <input
            type="url"
            placeholder="https://…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={busy}
          />
          <button type="submit" className="useful-link-add useful-link-add-solid" disabled={busy}>
            Добавить
          </button>
          <button
            type="button"
            className="useful-link-add"
            disabled={busy}
            onClick={() => {
              setAdding(false);
              setError("");
              setLabel("");
              setUrl("");
            }}
          >
            Отмена
          </button>
        </form>
      ) : null}
      {error ? <p className="useful-links-error">{error}</p> : null}
    </div>
  );
}
