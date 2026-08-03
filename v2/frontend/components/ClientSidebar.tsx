import Link from "next/link";
import type { ClientItem } from "@/lib/api";

type Props = {
  clients: ClientItem[];
  selectedId: number | null;
  mode: "active" | "archive";
  countsByClient: Record<number, number>;
  totalCount: number;
};

function hrefFor(tab: string, clientId: number | null): string {
  const params = new URLSearchParams();
  params.set("tab", tab);
  if (clientId != null) params.set("client", String(clientId));
  return `/vacancies?${params.toString()}`;
}

export function ClientSidebar({
  clients,
  selectedId,
  mode,
  countsByClient,
  totalCount,
}: Props) {
  return (
    <div className="sidebar-inner">
      <div className="sidebar-title">Клиент</div>
      <nav className="sidebar-nav" aria-label="Фильтр по клиенту">
        <Link
          href={hrefFor(mode, null)}
          className={selectedId == null ? "side-link side-link-active" : "side-link"}
        >
          <span>Все</span>
          <span className="side-count">{totalCount}</span>
        </Link>
        {clients.map((c) => (
          <Link
            key={c.id}
            href={hrefFor(mode, c.id)}
            className={selectedId === c.id ? "side-link side-link-active" : "side-link"}
          >
            <span>{c.name}</span>
            <span className="side-count">{countsByClient[c.id] ?? 0}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
