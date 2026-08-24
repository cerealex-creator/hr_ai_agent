import { AuthGate } from "@/components/AuthGate";
import { ManagementMap } from "@/components/ManagementMap";
import { ManagementShell } from "@/components/ManagementShell";

export default function ManagementSystemMapPage() {
  return (
    <AuthGate>
      <ManagementShell activePath="/management-system" title="Карта системы">
        <p className="muted" style={{ marginBottom: 12 }}>
          Интерактивный граф связей. Включите «Режим ворот» и кликните по узлу draft/suggested, чтобы
          утвердить (L0/L1/L2a/L2b). L2a требует роль на каждом шаге процесса.
        </p>
        <ManagementMap />
      </ManagementShell>
    </AuthGate>
  );
}
