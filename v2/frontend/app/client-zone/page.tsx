import { AppShell } from "@/components/AppShell";
import { Placeholder } from "@/components/Placeholder";

export default function ClientZonePage() {
  return (
    <AppShell activePath="/client-zone" sidebar={null}>
      <Placeholder
        title="Клиентская зона"
        body="Оценка заказчиком с отдельным доступом. Раздел в подготовке."
      />
    </AppShell>
  );
}
