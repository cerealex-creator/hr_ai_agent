import { AppShell } from "@/components/AppShell";

export default function ClientZoneHubPage() {
  return (
    <AppShell variant="search" activePath="/client-zone" sidebar={null}>
      <h1 className="page-title">Клиентская зона</h1>
      <p className="muted">
        Заказчик открывает секретную ссылку вида <code>/c/…</code> без логина. Создайте или
        сбросьте ссылку в настройках компании (раздел «Клиенты»).
      </p>
      <p>
        <a href="/settings">Перейти к настройкам компаний →</a>
      </p>
    </AppShell>
  );
}
