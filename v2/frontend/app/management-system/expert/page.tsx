import { AuthGate } from "@/components/AuthGate";
import { ManagementExpertPanel } from "@/components/ManagementExpertPanel";
import { ManagementShell } from "@/components/ManagementShell";

export default function ManagementSystemExpertPage() {
  return (
    <AuthGate>
      <ManagementShell activePath="/management-system/expert" title="Экспертный режим">
        <p className="muted" style={{ marginBottom: 12 }}>
          Ручной конструктор целей, задач, as-is должностей и связей. Graph Checker блокирует циклы.
        </p>
        <ManagementExpertPanel />
      </ManagementShell>
    </AuthGate>
  );
}
