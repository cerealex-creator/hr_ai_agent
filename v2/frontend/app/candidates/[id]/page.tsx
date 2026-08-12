import Link from "next/link";
import { Suspense } from "react";
import { CandidateEditor } from "@/components/CandidateEditor";
import { RecruitingShell } from "@/components/RecruitingShell";
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
    <RecruitingShell activePath="/candidates">
      {candidate ? (
        <Link className="rec-back" href={`/vacancies/${candidate.vacancy_id}?section=candidates`}>
          ← К вакансии{candidate.vacancy_title ? `: ${candidate.vacancy_title}` : ""}
        </Link>
      ) : (
        <Link className="rec-back" href="/candidates">
          ← К кандидатам
        </Link>
      )}
      {error ? <p className="warn">{error}</p> : null}
      {candidate ? (
        <Suspense fallback={<p className="muted">Загрузка…</p>}>
          <CandidateEditor initial={candidate} />
        </Suspense>
      ) : null}
    </RecruitingShell>
  );
}
