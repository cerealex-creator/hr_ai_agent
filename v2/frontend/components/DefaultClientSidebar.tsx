"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ClientSidebar } from "@/components/ClientSidebar";
import { getApiBase, type ClientItem, type VacancyListItem } from "@/lib/api";

/** Sidebar on every page: loads clients; selection from ?client= when on home. */
export function DefaultClientSidebar() {
  const searchParams = useSearchParams();
  const tab = searchParams.get("tab") === "archive" ? "archive" : "active";
  const clientParam = searchParams.get("client");
  const selectedId =
    clientParam && /^\d+$/.test(clientParam) ? Number(clientParam) : null;

  const [clients, setClients] = useState<ClientItem[]>([]);
  const [countsByClient, setCountsByClient] = useState<Record<number, number>>({});
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [clientsRes, vacRes] = await Promise.all([
          fetch(`${getApiBase()}/api/v1/clients`, { cache: "no-store" }),
          fetch(`${getApiBase()}/api/v1/vacancies`, { cache: "no-store" }),
        ]);
        if (!clientsRes.ok || !vacRes.ok) return;
        const nextClients: ClientItem[] = await clientsRes.json();
        const vacancies: VacancyListItem[] = await vacRes.json();
        if (cancelled) return;
        const counts: Record<number, number> = {};
        let total = 0;
        for (const v of vacancies) {
          const isArchive = !v.active;
          if (tab === "active" && isArchive) continue;
          if (tab === "archive" && !isArchive) continue;
          total += 1;
          if (v.client_id != null) {
            counts[v.client_id] = (counts[v.client_id] || 0) + 1;
          }
        }
        setClients(nextClients);
        setCountsByClient(counts);
        setTotalCount(total);
      } catch {
        /* sidebar is non-blocking */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tab]);

  return (
    <ClientSidebar
      clients={clients}
      selectedId={selectedId}
      mode={tab}
      countsByClient={countsByClient}
      totalCount={totalCount}
    />
  );
}
