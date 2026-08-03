import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { CandidateEditor } from "@/components/CandidateEditor";
import { apiGet, type CandidateDetail } from "@/lib/api";

type Props = { params: Promise<{ id: string }> };

export default async function CandidatePage({ params }: Props) {
  const { id } = await params;
  let candidate: CandidateDetail | null = null;
  let error: string | null = null;

  try {
    candidate = await apiGet<CandidateDetail>(`/api/v1/candidates/${id}`);
  } catch (e) {
    error = e instanceof Error ? e.message : "Ошибка API";
  }

  return (
    <AppShell variant="search" activePath="/candidates">
      {candidate ? (
        <Link className="back" href={`/vacancies/${candidate.vacancy_id}?section=candidates`}>
          ← К вакансии{candidate.vacancy_title ? `: ${candidate.vacancy_title}` : ""}
        </Link>
      ) : (
        <Link className="back" href="/">
          ← К вакансиям
        </Link>
      )}
      {error ? <p className="warn">{error}</p> : null}
      {candidate ? <CandidateEditor initial={candidate} /> : null}
    </AppShell>
  );
}
