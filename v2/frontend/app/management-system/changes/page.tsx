import { AuthGate } from "@/components/AuthGate";
import { ManagementChangesPanel } from "@/components/ManagementChangesPanel";
import { ManagementShell } from "@/components/ManagementShell";

export default function ManagementSystemChangesPage() {
  return (
    <AuthGate>
      <ManagementShell activePath="/management-system/changes" title="Изменения">
        <ManagementChangesPanel />
      </ManagementShell>
    </AuthGate>
  );
}
