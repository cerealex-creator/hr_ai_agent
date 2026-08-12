/** Next HR action for candidate card (audit M7). */

import type { CandidateDetail } from "@/lib/api";
import { isEventPassed } from "@/lib/dates";

export type NextActionSection = "anketa" | "stage" | "quest" | "client" | "ai" | "top";

export type NextAction = {
  label: string;
  detail?: string;
  section: NextActionSection;
};

export function resolveNextAction(c: CandidateDetail): NextAction | null {
  const stage = c.hr_stage || "";
  if (stage === "rejected") return null;

  const video = (c.video_link || "").trim();
  const transcript = (c.transcript || "").trim();
  const meetingDate = (c.office_interview_date || "").trim();
  const meetingTime = (c.office_interview_time || "").trim();
  const meetingSet = Boolean(meetingDate && meetingTime);
  const hrConfirmed = Boolean(c.payload?.meeting_hr_confirmed);
  const meetingPassed = isEventPassed(c.office_interview_date, c.office_interview_time);

  if (meetingSet && !hrConfirmed && (stage === "interview_scheduled" || stage === "client_meeting")) {
    return {
      label: "Подтвердить встречу HR",
      detail: `${meetingDate}${meetingTime ? `, ${meetingTime}` : ""}`,
      section: "top",
    };
  }

  if (stage === "interview_scheduled" && meetingPassed && meetingSet) {
    return {
      label: "Зафиксировать итог собеседования",
      detail: "сменить этап или заполнить оценку",
      section: "stage",
    };
  }

  if (stage === "interview_scheduled" || stage === "interview_done") {
    const interviewAi = (c.payload as { interview_ai_score?: number | null } | undefined)
      ?.interview_ai_score;
    if (video && !transcript && interviewAi == null) {
      return {
        label: "Обработать запись собеседования",
        detail: "расшифровка + оценка ИИ",
        section: "quest",
      };
    }
    if (!video) {
      return {
        label: "Добавить ссылку на запись",
        section: "anketa",
      };
    }
  }

  if (
    (stage === "resume_screening" || stage === "primary_contact") &&
    c.ai_score == null
  ) {
    return {
      label: "Оценить резюме ИИ",
      section: "quest",
    };
  }

  if (stage === "client_meeting" && meetingPassed && meetingSet) {
    return {
      label: "Зафиксировать решение заказчика",
      section: "client",
    };
  }

  if (stage === "client_review" || stage === "client_pause") {
    const st = c.client_status || "wait";
    if (st === "wait") {
      return {
        label: "Ждёт решения заказчика",
        detail: "можно напомнить или уточнить статус",
        section: "client",
      };
    }
    if (st === "think") {
      return {
        label: "Заказчик думает — follow-up",
        section: "client",
      };
    }
  }

  if (
    (stage === "resume_screening" || stage === "primary_contact") &&
    !(c.phone || "").trim()
  ) {
    return {
      label: "Добавить телефон / контакты",
      section: "anketa",
    };
  }

  return null;
}
