import { AppShell } from "@/components/AppShell";
import { Placeholder } from "@/components/Placeholder";

export default function DocumentsLabPage() {
  return (
    <AppShell activePath="/documents-lab" sidebar={null}>
      <Placeholder
        title="Разработка документов"
        body="Раздел в подготовке: шаблоны, правки и генерация пакета документов вне конкретной вакансии."
      />
    </AppShell>
  );
}
