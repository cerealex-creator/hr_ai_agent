"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export type ProviderLink = {
  id: string;
  label: string;
  url: string;
  enabled?: boolean;
};

type AiProvider = {
  id?: string;
  label?: string;
  console_url?: string;
  model?: string;
};

type Props = {
  /** Compact chips for topbar / settings side. */
  compact?: boolean;
};

export function ProviderResourceLinks({ compact = true }: Props) {
  const [links, setLinks] = useState<ProviderLink[]>([]);
  const [provider, setProvider] = useState<AiProvider | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/settings/app`, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        setLinks(Array.isArray(data.provider_links) ? data.provider_links : []);
        setProvider(data.ai_provider || null);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = links.filter((l) => l.enabled !== false && (l.url || "").trim());
  if (!visible.length && !provider) return null;

  return (
    <div className={compact ? "provider-links provider-links-compact" : "provider-links"}>
      {provider?.label ? (
        <a
          className="provider-link provider-link-active"
          href={(provider.console_url || "#").trim() || "#"}
          target="_blank"
          rel="noopener noreferrer"
          title={provider.model ? `Модель: ${provider.model}` : undefined}
        >
          {provider.label}
          {provider.model ? <span className="provider-link-meta">{provider.model}</span> : null}
        </a>
      ) : null}
      {visible
        .filter((l) => l.id !== "routerai" || !provider?.label)
        .map((l) => (
          <a
            key={l.id}
            className="provider-link"
            href={l.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {l.label}
          </a>
        ))}
    </div>
  );
}
