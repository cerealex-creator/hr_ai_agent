import { AuthGate } from "@/components/AuthGate";
import { ManagementMap } from "@/components/ManagementMap";
import { ManagementShell } from "@/components/ManagementShell";

export default function ManagementSystemMapPage() {
  return (
    <AuthGate>
      <ManagementShell activePath="/management-system" title="Карта системы">
        <p className="muted" style={{ marginBottom: 12 }}>
          Интерактивный граф связей. Режим эксперта — для правки структуры; мастер онбординга — в U2.
        </p>
        <ManagementMap />
      </ManagementShell>
    </AuthGate>
  );
}
