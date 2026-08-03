import Link from "next/link";
import type { ClientItem } from "@/lib/api";

export type SidebarClient = ClientItem & {
  parent_id?: number | null;
  kind?: string;
  chat_mode?: string;
};

type Props = {
  clients: SidebarClient[];
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
  const companies = clients.filter((c) => c.kind === "company" || (!c.parent_id && c.kind !== "department"));
  const departments = clients.filter((c) => c.kind === "department" || c.parent_id != null);
  const hasTree = companies.some((c) => c.chat_mode === "departments") || departments.length > 0;

  const orphans = hasTree
    ? clients.filter((c) => {
        if (c.kind === "test" || c.kind === "company" || c.kind === "department") return false;
        if (c.parent_id != null) return false;
        return true;
      })
    : clients.filter((c) => c.kind !== "test");

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

        {hasTree
          ? companies
              .filter((c) => c.kind === "company")
              .map((co) => {
                const kids = departments.filter((d) => d.parent_id === co.id);
                if (co.chat_mode === "departments") {
                  const groupCount = kids.reduce((s, d) => s + (countsByClient[d.id] || 0), 0);
                  return (
                    <div key={co.id} className="side-group">
                      <div className="side-group-title">
                        <span>{co.name}</span>
                        <span className="side-count">{groupCount}</span>
                      </div>
                      {kids.map((d) => (
                        <Link
                          key={d.id}
                          href={hrefFor(mode, d.id)}
                          className={
                            selectedId === d.id ? "side-link side-link-active side-link-nested" : "side-link side-link-nested"
                          }
                        >
                          <span>{d.name}</span>
                          <span className="side-count">{countsByClient[d.id] ?? 0}</span>
                        </Link>
                      ))}
                    </div>
                  );
                }
                return (
                  <Link
                    key={co.id}
                    href={hrefFor(mode, co.id)}
                    className={selectedId === co.id ? "side-link side-link-active" : "side-link"}
                  >
                    <span>{co.name}</span>
                    <span className="side-count">{countsByClient[co.id] ?? 0}</span>
                  </Link>
                );
              })
          : null}

        {orphans.map((c) => (
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
