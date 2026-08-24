import { AuthGate } from "@/components/AuthGate";
import { ManagementDocumentsPanel } from "@/components/ManagementDocumentsPanel";
import { ManagementShell } from "@/components/ManagementShell";

export default function ManagementSystemDocumentsPage() {
  return (
    <AuthGate>
      <ManagementShell activePath="/management-system/documents" title="Документы ролей">
        <p className="muted" style={{ marginBottom: 12 }}>
          Утверждение L3 только здесь (не в мастере). Сборка из процессов и ролей; KPI проверяется
          инвариантом.
        </p>
        <ManagementDocumentsPanel />
      </ManagementShell>
    </AuthGate>
  );
}
