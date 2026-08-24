import { AuthGate } from "@/components/AuthGate";
import { ManagementShell } from "@/components/ManagementShell";
import { ManagementWizard } from "@/components/ManagementWizard";

export default function ManagementWizardPage() {
  return (
    <AuthGate>
      <ManagementShell activePath="/management-system/wizard" title="Мастер онбординга">
        <p className="muted" style={{ marginBottom: 12 }}>
          Шаги 1–2: команда и интервью собственника. Прогресс сохраняется автоматически.
        </p>
        <ManagementWizard />
      </ManagementShell>
    </AuthGate>
  );
}
