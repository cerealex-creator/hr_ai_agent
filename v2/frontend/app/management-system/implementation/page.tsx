import { AuthGate } from "@/components/AuthGate";
import { ManagementImplementationPanel } from "@/components/ManagementImplementationPanel";
import { ManagementShell } from "@/components/ManagementShell";

export default function ManagementSystemImplementationPage() {
  return (
    <AuthGate>
      <ManagementShell activePath="/management-system/implementation" title="Внедрение">
        <p className="muted" style={{ marginBottom: 12 }}>
          Как есть → как надо → разрыв. Сопоставьте текущие должности с целевыми ролями; отчёт считается
          детерминированно, без ИИ.
        </p>
        <ManagementImplementationPanel />
      </ManagementShell>
    </AuthGate>
  );
}
