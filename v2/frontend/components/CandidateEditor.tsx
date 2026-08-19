"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Heart } from "lucide-react";
import { type CandidateDetail, apiFetch } from "@/lib/api";
import {
  HR_FUNNEL_STAGES,
  HR_STAGE_LABELS,
  clientStatusLabel,
  clientStatusLabelForCard,
  controlWordStatusLabel,
  hrStageLabel,
  isRejectionStage,
} from "@/lib/labels";
import { StageMarker } from "@/components/StageMarker";
import { StageProgress } from "@/components/StageProgress";
import { AiCommentBlock } from "@/components/AiCommentBlock";
import { QuestionnairePanel, type QItem } from "@/components/QuestionnairePanel";
import { LinkField } from "@/components/LinkField";
import { ActionBanner } from "@/components/ActionBanner";
import { CandidateAvatar } from "@/components/CandidateAvatar";
import { ClientZoneLink, clientZonePathFromSendResults } from "@/components/ClientZoneLink";
import { CandidateOfferPanel } from "@/components/CandidateOfferPanel";
import { daysBetween, daysLabel, formatDateRu, isEventPassed, parseLocalDate } from "@/lib/dates";
import { resolveNextAction } from "@/lib/nextAction";
import { DEMO_WRITE_HINT } from "@/lib/demo";
import { useAuth } from "@/components/AuthGate";

type Props = { initial: CandidateDetail };

type CandTab = "overview" | "profile" | "materials" | "pipeline" | "offer" | "interview" | "client" | "ai";

const CAND_TABS: { id: CandTab; label: string }[] = [
  { id: "profile", label: "Анкета" },
  { id: "materials", label: "Материалы" },
  { id: "pipeline", label: "Воронка" },
  { id: "interview", label: "Интервью" },
  { id: "client", label: "Заказчик" },
  { id: "ai", label: "ИИ" },
  { id: "offer", label: "Сделать оффер" },
];

function isCandTab(value: string | null): value is CandTab {
  return CAND_TABS.some((t) => t.id === value);
}

function sectionToTab(section: string): CandTab {
  if (section === "anketa") return "profile";
  if (section === "stage") return "pipeline";
  if (section === "quest") return "interview";
  if (section === "client") return "client";
  if (section === "ai") return "ai";
  return "profile";
}

function photoUrlFromCandidate(c: CandidateDetail): string | null {
  const top = (c.photo_url || "").trim();
  if (top) return top;
  const fromPayload = c.payload?.photo_url;
  return typeof fromPayload === "string" && fromPayload.trim() ? fromPayload.trim() : null;
}

type JobStatus = {
  id: string;
  status: string;
  progress_label: string | null;
  error: string | null;
  job_type: string;
};

type WaitingInfo = {
  since: string;
  days: number;
  reason: string;
};

const STAGE_ORDER = Object.keys(HR_STAGE_LABELS).filter((k) => k !== "rejected");
const CHAT_POLL_MS = 8000;

function field(v: string | null | undefined): string {
  return v ?? "";
}

function payloadStr(c: CandidateDetail, key: string): string {
  return String((c.payload as Record<string, unknown> | undefined)?.[key] ?? "").trim();
}

function payloadFlag(c: CandidateDetail, key: string): boolean {
  return Boolean((c.payload as Record<string, unknown> | undefined)?.[key]);
}

function candidateHasResumeForEval(c: CandidateDetail): boolean {
  const p = c.payload || {};
  const text = typeof p.resume_text === "string" && p.resume_text.trim();
  const link = (c.resume_link || "").trim();
  return Boolean(text || link);
}

function candidateCreatedManually(c: CandidateDetail): boolean {
  const source = String((c.payload || {}).source || "").trim();
  return source === "manual" || source === "";
}

function aiScoreSourceLabel(source: string | null | undefined): string {
  const s = (source || "").trim().toLowerCase();
  if (s === "resume") return "по резюме";
  if (s === "interview") return "по интервью";
  if (!s) return "";
  return s;
}

function formatMeetingDateRu(value: string | null | undefined): string {
  const d = parseLocalDate(value);
  if (!d) return "—";
  return d.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function buildMeetingInviteText(opts: {
  name: string;
  date: string;
  time: string;
  link: string;
}): string {
  const who = (opts.name || "").trim() || "кандидат";
  const dateLabel = formatMeetingDateRu(opts.date);
  const timeLabel = (opts.time || "").trim() || "—";
  const link = (opts.link || "").trim();
  return [
    `Здравствуйте, ${who}!`,
    "",
    "Приглашаю вас на встречу.",
    `Дата: ${dateLabel}`,
    `Время: ${timeLabel}`,
    `Ссылка: ${link}`,
    "",
    "Буду рад(а) видеть вас.",
  ].join("\n");
}

function buildMailtoHref(email: string, subject: string, body: string): string {
  const params = new URLSearchParams();
  params.set("subject", subject);
  params.set("body", body);
  return `mailto:${email.trim()}?${params.toString()}`;
}

/** Fields that change from Telegram / client zone. */
function chatFingerprint(c: CandidateDetail): string {
  const p = c.payload || {};
  return JSON.stringify([
    c.hr_stage,
    c.client_status,
    c.status_updated_at,
    c.office_interview_date,
    c.office_interview_time,
    c.client_comment,
    Boolean(p.meeting_hr_confirmed),
    Boolean(p.remote_interview),
    Boolean(p.office_interview),
  ]);
}

function splitClientComments(raw: string | null | undefined): {
  status: string[];
  free: string[];
} {
  const status: string[] = [];
  const free: string[] = [];
  for (const line of (raw || "").split("\n")) {
    const t = line.trim();
    if (!t) continue;
    if (t.includes("к статусу «") || t.includes('к статусу "')) status.push(t);
    else free.push(t);
  }
  return { status, free };
}

function meetingFormatLabel(c: CandidateDetail): string | null {
  const p = c.payload || {};
  const remote = Boolean(p.remote_interview);
  const office = Boolean(p.office_interview);
  if (remote && office) return "онлайн / офис";
  if (remote) return "онлайн";
  if (office) return "в офисе";
  return null;
}

/** Waiting for a decision after interview/meeting date or while on client review. */
function resolveWaiting(c: CandidateDetail): WaitingInfo | null {
  const stage = c.hr_stage;
  const meetingDate = c.office_interview_date;
  const meetingPassed = isEventPassed(meetingDate, c.office_interview_time);

  if (stage === "interview_scheduled" && meetingPassed && meetingDate) {
    const days = daysBetween(meetingDate);
    if (days == null) return null;
    return { since: meetingDate, days, reason: "после собеседования" };
  }
  if (stage === "client_meeting" && meetingPassed && meetingDate) {
    const days = daysBetween(meetingDate);
    if (days == null) return null;
    return { since: meetingDate, days, reason: "после встречи с заказчиком" };
  }
  if (stage === "client_review" || stage === "client_pause") {
    const since = c.status_updated_at || c.created_at;
    if (!since) return null;
    const days = daysBetween(since);
    if (days == null) return null;
    return {
      since,
      days,
      reason: stage === "client_pause" ? "на паузе у заказчика" : "на оценке у заказчика",
    };
  }
  return null;
}

export function CandidateEditor({ initial }: Props) {
  const router = useRouter();
  const { isDemo, isOwner } = useAuth();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const activeTab: CandTab = isCandTab(tabParam) ? tabParam : "profile";
  const setActiveTab = (tab: CandTab) => {
    const params = new URLSearchParams(searchParams.toString());
    if (tab === "overview") params.delete("tab");
    else params.set("tab", tab);
    const q = params.toString();
    router.replace(q ? `?${q}` : "?", { scroll: false });
  };
  const [c, setC] = useState(initial);
  const [name, setName] = useState(initial.name || "");
  const [phone, setPhone] = useState(field(initial.phone));
  const [email, setEmail] = useState(field(initial.email));
  const [age, setAge] = useState(field(initial.age));
  const [city, setCity] = useState(field(initial.city));
  const [metro, setMetro] = useState(field(initial.metro));
  const [salary, setSalary] = useState(field(initial.salary_expected));
  const [resumeLink, setResumeLink] = useState(field(initial.resume_link));
  const [hhLink, setHhLink] = useState(field(initial.hh_resume_link));
  const [anonResume, setAnonResume] = useState(payloadStr(initial, "anonymized_resume_link"));
  const [previewIncluded, setPreviewIncluded] = useState(payloadFlag(initial, "resume_preview_included"));
  const [portfolio, setPortfolio] = useState(field(initial.portfolio_link));
  const [video, setVideo] = useState(field(initial.video_link));
  const [taskLink, setTaskLink] = useState(field(initial.task_link));
  const [hrComment, setHrComment] = useState(field(initial.hr_comment));
  const [interviewEvalNotes, setInterviewEvalNotes] = useState(field(initial.interview_eval_notes));
  const [interviewDate, setInterviewDate] = useState(field(initial.office_interview_date));
  const [interviewTime, setInterviewTime] = useState(field(initial.office_interview_time));
  const [remoteInterview, setRemoteInterview] = useState(
    Boolean((initial.payload as { remote_interview?: boolean } | undefined)?.remote_interview),
  );
  const [meetingLink, setMeetingLink] = useState(
    field((initial.payload as { meeting_link?: string } | undefined)?.meeting_link),
  );
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [scheduleBusy, setScheduleBusy] = useState(false);
  const [copyInviteDone, setCopyInviteDone] = useState(false);
  const [stage, setStage] = useState(initial.hr_stage);
  const [stageOptions, setStageOptions] = useState<{ id: string; label: string }[]>(
    STAGE_ORDER.map((id) => ({ id, label: HR_STAGE_LABELS[id] || id })),
  );
  const [funnelStages, setFunnelStages] = useState<string[]>([...HR_FUNNEL_STAGES]);
  const [stageLabelsMap, setStageLabelsMap] = useState<Record<string, string>>({ ...HR_STAGE_LABELS });
  const [stageNote, setStageNote] = useState("");
  const [deleteCalendarEvent, setDeleteCalendarEvent] = useState(false);
  const [warrantyDate, setWarrantyDate] = useState("");
  const [warrantyMonths, setWarrantyMonths] = useState(3);
  const [materialTitle, setMaterialTitle] = useState("");
  const [materialUrl, setMaterialUrl] = useState("");
  const [copyTargetId, setCopyTargetId] = useState("");
  const [vacancies, setVacancies] = useState<{ id: number; title: string }[]>([]);
  const [moveToClientReview, setMoveToClientReview] = useState(true);
  const [busy, setBusy] = useState(false);
  const writeLocked = busy || isDemo;
  const [editingProfile, setEditingProfile] = useState(false);
  const [editingMaterials, setEditingMaterials] = useState(false);
  const [editingPipeline, setEditingPipeline] = useState(false);
  const [evalBusy, setEvalBusy] = useState(false);
  const [attachResumeLink, setAttachResumeLink] = useState("");
  const [attachResumeFile, setAttachResumeFile] = useState<File | null>(null);
  const [attachBusy, setAttachBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [aiCommentOpen, setAiCommentOpen] = useState(false);
  const [scoreJumpPending, setScoreJumpPending] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [stageOpen, setStageOpen] = useState(false);
  const [anketaOpen, setAnketaOpen] = useState(false);
  const [questOpen, setQuestOpen] = useState(() => {
    const dig =
      initial.interview_digest ||
      (initial.payload as { interview_digest?: { summary?: string; qa?: unknown[] } } | undefined)
        ?.interview_digest;
    const hasDig = Boolean(
      dig && ((dig.summary || "").trim() || (Array.isArray(dig.qa) && dig.qa.length > 0)),
    );
    return (
      hasDig ||
      (Array.isArray(initial.interview_questionnaire) && initial.interview_questionnaire.length > 0) ||
      Boolean((initial.transcript || "").trim())
    );
  });
  const [clientOpen, setClientOpen] = useState(false);
  const [clientZonePath, setClientZonePath] = useState<string | null>(null);
  const [notifyChannels, setNotifyChannels] = useState<string[]>(["bitrix", "web"]);
  const [aiSectionOpen, setAiSectionOpen] = useState(false);
  const [pendingRemote, setPendingRemote] = useState<CandidateDetail | null>(null);
  const [bannerTone, setBannerTone] = useState<"success" | "warning" | "error">("success");
  const [actionSection, setActionSection] = useState<
    "anketa" | "stage" | "client" | "top" | null
  >(null);

  const sections = useMemo(() => {
    const s = c.ai_comment_sections;
    if (s && typeof s === "object" && !Array.isArray(s)) return s as Record<string, unknown>;
    return null;
  }, [c.ai_comment_sections]);

  const hasAiComment =
    Boolean((c.ai_comment || "").trim()) ||
    Boolean(sections && Object.keys(sections).length > 0);

  const meetingScheduled = Boolean(
    (c.office_interview_date || "").trim() && (c.office_interview_time || "").trim(),
  );
  const meetingHrConfirmed = Boolean(c.payload?.meeting_hr_confirmed);
  const attendanceStatus = String(c.payload?.interview_attendance_status || "").trim();
  const meetingFormat = meetingFormatLabel(c);
  const telegramNotifyEnabled = notifyChannels.includes("telegram");
  const bitrixNotifyEnabled = notifyChannels.includes("bitrix");
  const webNotifyEnabled = notifyChannels.includes("web");

  useEffect(() => {
    if (!c.client_id) {
      setClientZonePath(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/companies/${c.client_id}/client-zone`, {
          cache: "no-store",
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && typeof data.path === "string" && data.path.startsWith("/c/")) {
          setClientZonePath(data.path);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [c.client_id]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/settings/app`, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        const ch = data?.client_notify?.channels;
        if (!cancelled && Array.isArray(ch) && ch.length) {
          setNotifyChannels(ch);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!scoreJumpPending || !aiSectionOpen) return;
    const el = document.getElementById("ai-comment-block");
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
    setScoreJumpPending(false);
  }, [scoreJumpPending, aiSectionOpen, c.ai_comment, sections]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/vacancies/${c.vacancy_id}/stage-schema`,
          { cache: "no-store" },
        );
        if (!res.ok) return;
        const data = await res.json();
        const items = (data.schema?.hr_stages || []) as {
          id: string;
          label: string;
          enabled?: boolean;
        }[];
        const opts = items
          .filter((i) => i.enabled !== false || i.id === c.hr_stage)
          .map((i) => ({ id: i.id, label: i.label || HR_STAGE_LABELS[i.id] || i.id }));
        if (!cancelled && opts.length) setStageOptions(opts);
        if (!cancelled) {
          const labels: Record<string, string> = { ...HR_STAGE_LABELS };
          for (const i of items) {
            if (i.label) labels[i.id] = i.label;
          }
          setStageLabelsMap(labels);
          const enabledFunnel = items
            .filter((i) => i.enabled !== false && !isRejectionStage(i.id) && i.id !== "archived")
            .map((i) => i.id);
          if (enabledFunnel.length) setFunnelStages(enabledFunnel);
        }
      } catch {
        /* keep defaults */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [c.vacancy_id, c.hr_stage]);

  const openAiComment = () => {
    if (!hasAiComment && c.ai_score == null) return;
    setActiveTab("ai");
    setAiSectionOpen(true);
    setAiCommentOpen(true);
    setScoreJumpPending(true);
  };

  const inWorkDays = daysBetween(c.created_at);
  const waiting = useMemo(() => resolveWaiting(c), [c]);
  const nextAction = useMemo(() => resolveNextAction(c), [c]);
  const isLiked = Boolean(c.liked ?? payloadFlag(c, "liked"));
  const inReserve = Boolean(c.talent_reserve ?? payloadFlag(c, "talent_reserve"));
  const LATE_STAGES = new Set([
    "client_meeting", "offer", "internship", "started_work",
    "rejected_candidate", "rejected_client", "rejected_hr",
    "rejected_vacancy_closed", "archived",
  ]);
  const showReserveBtn = inReserve || isLiked || LATE_STAGES.has(c.hr_stage);

  const hasQuestionnaire = Array.isArray(c.interview_questionnaire) && c.interview_questionnaire.length > 0;

  const applyCandidate = (next: CandidateDetail) => {
    setC(next);
    setName(next.name || "");
    setPhone(field(next.phone));
    setEmail(field(next.email));
    setAge(field(next.age));
    setCity(field(next.city));
    setMetro(field(next.metro));
    setSalary(field(next.salary_expected));
    setResumeLink(field(next.resume_link));
    setHhLink(field(next.hh_resume_link));
    setAnonResume(payloadStr(next, "anonymized_resume_link"));
    setPreviewIncluded(payloadFlag(next, "resume_preview_included"));
    setPortfolio(field(next.portfolio_link));
    setVideo(field(next.video_link));
    setTaskLink(field(next.task_link));
    setHrComment(field(next.hr_comment));
    setInterviewEvalNotes(field(next.interview_eval_notes));
    setInterviewDate(field(next.office_interview_date));
    setInterviewTime(field(next.office_interview_time));
    setRemoteInterview(Boolean((next.payload as { remote_interview?: boolean } | undefined)?.remote_interview));
    setMeetingLink(field((next.payload as { meeting_link?: string } | undefined)?.meeting_link));
    setStage(next.hr_stage);
    setPendingRemote(null);
  };

  const isFormDirty = () =>
    name !== (c.name || "") ||
    phone !== field(c.phone) ||
    email !== field(c.email) ||
    age !== field(c.age) ||
    city !== field(c.city) ||
    metro !== field(c.metro) ||
    salary !== field(c.salary_expected) ||
    resumeLink !== field(c.resume_link) ||
    hhLink !== field(c.hh_resume_link) ||
    anonResume !== payloadStr(c, "anonymized_resume_link") ||
    previewIncluded !== payloadFlag(c, "resume_preview_included") ||
    portfolio !== field(c.portfolio_link) ||
    video !== field(c.video_link) ||
    taskLink !== field(c.task_link) ||
    hrComment !== field(c.hr_comment) ||
    interviewEvalNotes !== field(c.interview_eval_notes) ||
    interviewDate !== field(c.office_interview_date) ||
    interviewTime !== field(c.office_interview_time) ||
    stage !== c.hr_stage ||
    stageNote.trim() !== "";

  const dirtyRef = useRef(false);
  const fingerprintRef = useRef(chatFingerprint(c));
  const candidateIdRef = useRef(c.id);
  dirtyRef.current = isFormDirty();
  fingerprintRef.current = chatFingerprint(c);
  candidateIdRef.current = c.id;

  const reloadCandidate = async () => {
    const res = await apiFetch(`/api/v1/candidates/${c.id}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const next: CandidateDetail = await res.json();
    applyCandidate(next);
    return next;
  };

  /** Poll for Telegram / external changes while the card is open. */
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const id = candidateIdRef.current;
      try {
        const res = await apiFetch(`/api/v1/candidates/${id}`, { cache: "no-store" });
        if (!res.ok || cancelled) return;
        const next: CandidateDetail = await res.json();
        if (cancelled) return;
        if (chatFingerprint(next) === fingerprintRef.current) return;
        if (dirtyRef.current) {
          setPendingRemote(next);
          return;
        }
        applyCandidate(next);
        setMsg("Карточка обновлена из чата");
      } catch {
        /* ignore polling errors */
      }
    };
    const timer = setInterval(tick, CHAT_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- poll only while mounted; refs hold latest
  }, []);

  const setFeedback = (
    section: "anketa" | "stage" | "client" | "top",
    nextMsg: string | null,
    nextErr: string | null = null,
    tone: "success" | "warning" | "error" = nextErr ? "error" : "success",
  ) => {
    setActionSection(section);
    setMsg(nextMsg);
    setErr(nextErr);
    setBannerTone(tone);
  };

  const saveCard = async () => {
    if (isDemo) {
      setFeedback("anketa", null, DEMO_WRITE_HINT, "warning");
      return;
    }
    setBusy(true);
    setFeedback("anketa", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          phone,
          email,
          age,
          city,
          metro,
          salary_expected: salary,
          resume_link: resumeLink,
          hh_resume_link: hhLink,
          anonymized_resume_link: anonResume,
          ...(isOwner ? { resume_preview_included: previewIncluded } : {}),
          portfolio_link: portfolio,
          video_link: video,
          task_link: taskLink,
          hr_comment: hrComment,
          interview_eval_notes: interviewEvalNotes,
          office_interview_date: interviewDate,
          office_interview_time: interviewTime,
          remote_interview: remoteInterview,
          meeting_link: meetingLink,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const next: CandidateDetail = await res.json();
      applyCandidate(next);
      setFeedback(
        "anketa",
        "Карточка сохранена (чат обновлён, если была Telegram-карточка)",
      );
      router.refresh();
    } catch (e) {
      setFeedback("anketa", null, e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  };

  const toggleLike = async (next: boolean) => {
    if (isDemo) {
      setFeedback("top", null, DEMO_WRITE_HINT, "warning");
      return;
    }
    setBusy(true);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ liked: next }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: CandidateDetail = await res.json();
      applyCandidate(updated);
      setFeedback("top", next ? "Кандидат понравился" : "Отметка снята");
      router.refresh();
    } catch (e) {
      setFeedback("top", null, e instanceof Error ? e.message : "Ошибка", "error");
    } finally {
      setBusy(false);
    }
  };

  const toggleReserve = async (next: boolean) => {
    if (isDemo) {
      setFeedback("top", null, DEMO_WRITE_HINT, "warning");
      return;
    }
    setBusy(true);
    setFeedback("top", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ talent_reserve: next }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: CandidateDetail = await res.json();
      applyCandidate(updated);
      setFeedback(
        "top",
        next ? "Кандидат добавлен в кадровый резерв" : "Кандидат убран из кадрового резерва",
      );
      router.refresh();
    } catch (e) {
      setFeedback(
        "top",
        null,
        e instanceof Error ? e.message : "Не удалось обновить резерв",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) return;
    const timer = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/v1/jobs/${job.id}`, { cache: "no-store" });
        if (!res.ok) return;
        const next = (await res.json()) as JobStatus;
        setJob(next);
        if (next.status === "completed") {
          await reloadCandidate();
          setMsg(next.progress_label || "Готово");
          if (next.job_type === "candidate_evaluate_resume") {
            setScoreJumpPending(true);
            setQuestOpen(true);
          }
          if (next.job_type === "candidate_interview_process") {
            setQuestOpen(true);
            setTimeout(() => {
              document.getElementById("interview-digest")?.scrollIntoView({
                behavior: "smooth",
                block: "start",
              });
            }, 120);
          }
          setJob(null);
        } else if (next.status === "failed" || next.status === "cancelled") {
          setErr(next.error || next.progress_label || "Задача не завершена");
          setJob(null);
        }
      } catch {
        /* ignore polling errors */
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [job]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/jobs?limit=40`, { cache: "no-store" });
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as {
          items?: Array<{
            id: string;
            status: string;
            job_type: string;
            progress_label: string | null;
            error: string | null;
            payload?: { candidate_id?: string };
          }>;
        };
        const hit = (data.items || []).find(
          (j) =>
            (j.status === "queued" || j.status === "running") &&
            (j.job_type === "candidate_evaluate_resume" ||
              j.job_type === "candidate_interview_process") &&
            String(j.payload?.candidate_id || "") === c.id,
        );
        if (hit && !cancelled) {
          setJob({
            id: hit.id,
            status: hit.status,
            progress_label: hit.progress_label,
            error: hit.error,
            job_type: hit.job_type,
          });
          setMsg(
            hit.job_type === "candidate_evaluate_resume"
              ? "Оценка резюме уже идёт — можно следить в «Задачи»"
              : "Обработка собеседования уже идёт",
          );
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- restore once per candidate
  }, [c.id]);

  const saveStage = async () => {
    setBusy(true);
    setFeedback("stage", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}/stage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hr_stage: stage,
          note: stageNote,
          office_interview_date: interviewDate || null,
          office_interview_time: interviewTime || null,
          keep_calendar_event: !deleteCalendarEvent,
          warranty_start_date: warrantyDate || null,
          warranty_months: ["offer", "internship", "started_work"].includes(stage)
            ? warrantyMonths
            : null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const next: CandidateDetail = await res.json();
      applyCandidate(next);
      setStageNote("");
      setDeleteCalendarEvent(false);
      setFeedback("stage", `Этап: ${hrStageLabel(next.hr_stage)}`);
      router.refresh();
    } catch (e) {
      setFeedback("stage", null, e instanceof Error ? e.message : "Ошибка смены этапа");
    } finally {
      setBusy(false);
    }
  };

  const applyClientStage = async () => {
    setBusy(true);
    setFeedback("stage", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}/apply-client-stage`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      const next: CandidateDetail = await res.json();
      applyCandidate(next);
      setFeedback("stage", `Этап применён: ${hrStageLabel(next.hr_stage)}`);
      router.refresh();
    } catch (e) {
      setFeedback("stage", null, e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const remind = async (kind: "evaluate" | "decide") => {
    setBusy(true);
    setFeedback("client", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}/remind?kind=${kind}`,
        { method: "POST" },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : await res.text());
      setFeedback("client", data.message || "Напоминание отправлено");
    } catch (e) {
      setFeedback("client", null, e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const refreshClientCard = async () => {
    setBusy(true);
    setFeedback("client", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}/refresh-telegram?notify=true`,
        { method: "POST" },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Ошибка");
      setFeedback("client", data.message || "Карточка в чате обновлена");
    } catch (e) {
      setFeedback("client", null, e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const sendMaterial = async () => {
    setBusy(true);
    setFeedback("client", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}/extra-material`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: materialTitle, url: materialUrl }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Ошибка");
      if (data.candidate) applyCandidate(data.candidate);
      setMaterialTitle("");
      setMaterialUrl("");
      setFeedback("client", data.message || "Материал отправлен");
      router.refresh();
    } catch (e) {
      setFeedback("client", null, e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const copyCandidate = async () => {
    if (!copyTargetId) return;
    setBusy(true);
    setFeedback("stage", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}/copy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_vacancy_id: Number(copyTargetId) }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Ошибка");
      setFeedback("stage", "Кандидат скопирован");
      router.push(`/candidates/${data.id}`);
      router.refresh();
    } catch (e) {
      setFeedback("stage", null, e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/vacancies?active=true`, {
          cache: "no-store",
        });
        if (!res.ok) return;
        const rows = (await res.json()) as { id: number; title: string; active?: boolean }[];
        if (!cancelled) {
          setVacancies(
            rows
              .filter((v) => v.active !== false && v.id !== c.vacancy_id)
              .map((v) => ({ id: v.id, title: v.title })),
          );
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [c.vacancy_id]);

  const remove = async () => {
    if (isDemo) return;
    if (!window.confirm(`Удалить кандидата «${c.name}»?`)) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) throw new Error(await res.text());
      router.push(`/vacancies/${c.vacancy_id}?section=candidates`);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка удаления");
      setBusy(false);
    }
  };

  const sendToChat = async () => {
    if (isDemo) {
      setFeedback("client", null, DEMO_WRITE_HINT, "warning");
      return;
    }
    setBusy(true);
    setClientOpen(true);
    setFeedback("client", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}/send-to-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ move_to_client_review: moveToClientReview }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data?.detail;
        throw new Error(
          typeof detail === "string"
            ? detail
            : detail
              ? JSON.stringify(detail)
              : `HTTP ${res.status}`,
        );
      }
      if (data.candidate) applyCandidate(data.candidate as CandidateDetail);
      const zonePath = clientZonePathFromSendResults(data.results);
      if (zonePath) setClientZonePath(zonePath);
      const partial =
        Array.isArray(data.errors) && data.errors.length > 0 && Boolean(data.ok);
      setFeedback(
        "client",
        data.message || "Отправлено заказчику",
        null,
        partial ? "warning" : "success",
      );
      setStage(data.hr_stage || c.hr_stage);
      document.getElementById("cand-client")?.scrollIntoView({ behavior: "smooth", block: "start" });
      router.refresh();
    } catch (e) {
      setFeedback("client", null, e instanceof Error ? e.message : "Ошибка отправки заказчику");
      document.getElementById("cand-client")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } finally {
      setBusy(false);
    }
  };

  const confirmMeeting = async () => {
    setBusy(true);
    setFeedback("client", null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${c.id}/confirm-meeting`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
      }
      applyCandidate(data as CandidateDetail);
      setFeedback("client", "Встреча подтверждена HR");
      router.refresh();
    } catch (e) {
      setFeedback("client", null, e instanceof Error ? e.message : "Ошибка подтверждения");
    } finally {
      setBusy(false);
    }
  };

  const evaluateInterview = async () => {
    setEvalBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const saveRes = await apiFetch(`/api/v1/candidates/${c.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interview_eval_notes: interviewEvalNotes }),
      });
      if (!saveRes.ok) throw new Error(await saveRes.text());

      const res = await apiFetch(`/api/v1/candidates/${c.id}/evaluate-interview`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      if (data.candidate) applyCandidate(data.candidate as CandidateDetail);
      const score = data.ai_score ?? "—";
      let note = `Оценка по интервью: ${score}/4`;
      if (!data.profile_present) note += " · профиль вакансии пуст — оценка менее точная";
      setMsg(note);
      setScoreJumpPending(false);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка оценки по интервью");
    } finally {
      setEvalBusy(false);
    }
  };

  const evaluateResume = async (opts?: { skipQuestionnaire?: boolean }) => {
    setErr(null);
    setMsg(null);
    const skipQuestionnaire = Boolean(opts?.skipQuestionnaire);
    const res = await apiFetch(`/api/v1/candidates/${c.id}/evaluate-resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skip_questionnaire: skipQuestionnaire }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
    }
    setJob({
      id: String(data.id || ""),
      status: String(data.status || "queued"),
      progress_label: data.progress_label || "Оценка резюме в очереди",
      error: null,
      job_type: "candidate_evaluate_resume",
    });
    setMsg(
      data.reused
        ? "Оценка резюме уже идёт — следите в «Задачи» или строке статуса ниже"
        : skipQuestionnaire
          ? "Запущена оценка резюме (без опросника)"
          : "Запущена оценка резюме и формирование опросника",
    );
  };

  const attachResumeThenEvaluate = async () => {
    setAttachBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const body = new FormData();
      if (attachResumeFile) {
        body.append("file", attachResumeFile);
      } else if (attachResumeLink.trim()) {
        body.append("resume_link", attachResumeLink.trim());
      } else {
        throw new Error("Добавьте файл или ссылку на PDF");
      }
      const res = await apiFetch(`/api/v1/candidates/${c.id}/attach-resume`, {
        method: "POST",
        body,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      applyCandidate(data as CandidateDetail);
      setAttachResumeFile(null);
      setAttachResumeLink("");
      await evaluateResume();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось прикрепить резюме");
    } finally {
      setAttachBusy(false);
    }
  };

  const transcribeAndEvaluate = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const saveRes = await apiFetch(`/api/v1/candidates/${c.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_link: video,
          interview_eval_notes: interviewEvalNotes,
        }),
      });
      if (!saveRes.ok) throw new Error(await saveRes.text());
      const res = await apiFetch(`/api/v1/candidates/${c.id}/transcribe-and-evaluate`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setJob({
        id: String(data.id || ""),
        status: String(data.status || "queued"),
        progress_label: data.progress_label || "Задача поставлена в очередь",
        error: null,
        job_type: "candidate_interview_process",
      });
      await reloadCandidate();
      setMsg(
        data.reused
          ? "Уже идёт обработка этой записи — следим за статусом"
          : "Запущена расшифровка и оценка собеседования",
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка запуска обработки собеседования");
    } finally {
      setBusy(false);
    }
  };

  const activeJob =
    job && (job.status === "queued" || job.status === "running") ? job : null;
  const transcriptionBusy = activeJob?.job_type === "candidate_interview_process";
  const resumeEvalBusy = activeJob?.job_type === "candidate_evaluate_resume";

  const showInterviewDateFields =
    stage === "interview_scheduled" ||
    stage === "client_meeting" ||
    c.hr_stage === "interview_scheduled" ||
    c.hr_stage === "client_meeting";

  const clientComments = splitClientComments(c.client_comment);
  const bannerFor = (section: typeof actionSection) =>
    actionSection === section ? (
      <ActionBanner msg={msg} err={err} tone={bannerTone} />
    ) : null;

  return (
    <>
      <div className="cand-workspace-head">
        <CandidateAvatar
          name={c.name || "Без имени"}
          photoUrl={photoUrlFromCandidate(c)}
          gender={c.gender}
          size={64}
        />
        <div className="cand-workspace-main">
          <h1 className="cand-workspace-title page-title">{c.name || "Без имени"}</h1>
          <p className="muted cand-workspace-meta">
            {c.vacancy_title || `Вакансия #${c.vacancy_id}`}
            {c.client_name ? ` · ${c.client_name}` : ""}
          </p>
          <div className="cand-workspace-badges">
            <span className="cand-workspace-badge is-accent">
              <StageMarker stage={c.hr_stage} />
            </span>
            {c.ai_score != null ? (
              <span className="cand-workspace-badge">
                ИИ {c.ai_score}/4
                {c.ai_score_source ? ` · ${aiScoreSourceLabel(c.ai_score_source)}` : ""}
              </span>
            ) : null}
            <span className="cand-workspace-badge">
              {clientStatusLabelForCard(c.hr_stage, c.client_status)}
            </span>
            {inReserve ? (
              <span className="cand-workspace-badge is-accent">Кадровый резерв</span>
            ) : null}
          </div>
          {!isDemo ? (
            <div className="cand-workspace-actions">
              <button
                type="button"
                className={`cand-like-btn${isLiked ? " is-liked" : ""}`}
                disabled={writeLocked}
                onClick={() => void toggleLike(!isLiked)}
                title={isLiked ? "Убрать отметку" : "Нравится"}
              >
                <Heart size={20} fill={isLiked ? "currentColor" : "none"} strokeWidth={2} />
                {isLiked ? "Нравится" : "Нравится"}
              </button>
              {showReserveBtn ? (
                <button
                  type="button"
                  className={inReserve ? "chip chip-active" : "chip"}
                  disabled={writeLocked}
                  onClick={() => void toggleReserve(!inReserve)}
                >
                  {inReserve ? "Убрать из резерва" : "Добавить в резерв"}
                </button>
              ) : null}
              {inReserve ? (
                <Link href="/talent-reserve" className="chip">
                  Открыть резерв
                </Link>
              ) : null}
            </div>
          ) : null}
          {isDemo ? (
            <p className="muted hh-micro">
              Демо: оценка, опросник и конспект уже заполнены. Сохранить, отправить в чат или
              запустить ИИ нельзя.
            </p>
          ) : null}
        </div>
      </div>

      <div className="cand-summary">
        <div className="cand-summary-row">
          <span className="cand-summary-label">Оценка ИИ</span>
          <span className="cand-summary-value">
            {c.ai_score != null ? (
              <button type="button" className="score-jump-link cand-summary-score" onClick={openAiComment}>
                <strong>{c.ai_score}/4</strong>
                {c.ai_score_source ? (
                  <span className="cand-summary-muted"> · {aiScoreSourceLabel(c.ai_score_source)}</span>
                ) : null}
              </button>
            ) : (
              <span className="cand-summary-muted">ещё нет</span>
            )}
          </span>
        </div>
        <div className="cand-summary-row">
          <span className="cand-summary-label">Статус</span>
          <span className="cand-summary-value">
            <strong>
              <StageMarker stage={c.hr_stage} />
            </strong>
            <span className="cand-summary-muted">
              {" "}
              · {clientStatusLabelForCard(c.hr_stage, c.client_status)}
            </span>
            {c.control_word_status ? (
              <span className="cand-summary-muted">
                {" "}
                · контроль: {controlWordStatusLabel(c.control_word_status)}
                {c.control_word_match ? ` (${c.control_word_match})` : ""}
              </span>
            ) : c.vacancy_control_word_enabled && c.vacancy_control_word ? (
              <span className="cand-summary-muted">
                {" "}
                · контроль: {c.vacancy_control_word} (не проверено)
              </span>
            ) : null}
          </span>
        </div>
        {clientComments.status.length ? (
          <div className="cand-summary-row">
            <span className="cand-summary-label">К решению</span>
            <span className="cand-summary-value">
              {clientComments.status.map((line) => (
                <div key={line} style={{ marginBottom: "0.2rem" }}>
                  {line}
                </div>
              ))}
            </span>
          </div>
        ) : null}
        {clientComments.free.length ? (
          <div className="cand-summary-row">
            <span className="cand-summary-label">Коммент. заказчика</span>
            <span className="cand-summary-value">
              {clientComments.free.map((line) => (
                <div key={line} style={{ marginBottom: "0.2rem" }}>
                  {line}
                </div>
              ))}
            </span>
          </div>
        ) : null}
        {meetingScheduled ? (
          <div className="cand-summary-row cand-summary-meeting">
            <span className="cand-summary-label">Встреча</span>
            <span className="cand-summary-value">
              <strong>
                {formatMeetingDateRu(c.office_interview_date)}
                {c.office_interview_time ? `, ${c.office_interview_time}` : ""}
              </strong>
              {meetingFormat ? (
                <span className="cand-summary-muted"> · {meetingFormat}</span>
              ) : null}
              <span
                className={
                  meetingHrConfirmed ? "cand-summary-confirm is-yes" : "cand-summary-confirm is-no"
                }
              >
                {" · "}
                {meetingHrConfirmed ? "встреча подтверждена HR" : "ожидает подтверждения HR"}
              </span>
              {meetingHrConfirmed && attendanceStatus === "confirmed" ? (
                <span className="cand-summary-confirm is-yes"> · кандидат подтвердил явку</span>
              ) : null}
              {meetingHrConfirmed && attendanceStatus === "cancelled_candidate" ? (
                <span className="cand-summary-confirm is-no"> · кандидат отменил в день встречи</span>
              ) : null}
              {meetingHrConfirmed && attendanceStatus === "cancelled_client" ? (
                <span className="cand-summary-confirm is-no"> · заказчик отменил в день встречи</span>
              ) : null}
              {!meetingHrConfirmed ? (
                <button
                  type="button"
                  className="chip"
                  disabled={writeLocked}
                  onClick={confirmMeeting}
                  style={{ marginLeft: "0.5rem", verticalAlign: "middle" }}
                >
                  Подтвердить встречу
                </button>
              ) : null}
            </span>
          </div>
        ) : null}
        <div className="cand-summary-row cand-summary-work">
          <span className="cand-summary-label">В работе</span>
          <span className="cand-summary-value">
            {c.created_at ? (
              <>
                с {formatDateRu(c.created_at)}
                {inWorkDays != null ? (
                  <>
                    {" · "}
                    <strong>{daysLabel(inWorkDays)}</strong>
                  </>
                ) : null}
              </>
            ) : (
              <span className="cand-summary-muted">дата неизвестна</span>
            )}
          </span>
        </div>
        {waiting ? (
          <div className="cand-summary-row cand-summary-wait">
            <span className="cand-summary-label">Ждёт решения</span>
            <span className="cand-summary-value">
              с {formatDateRu(waiting.since)} · <strong>{daysLabel(waiting.days)}</strong>
              <span className="cand-summary-wait-reason"> · {waiting.reason}</span>
            </span>
          </div>
        ) : null}
      </div>

      {pendingRemote ? (
        <div className="cand-remote-banner" role="status">
          <span>В чате изменились данные кандидата (статус / встреча / комментарий).</span>
          <button
            type="button"
            className="btn secondary"
            onClick={() => {
              applyCandidate(pendingRemote);
              setMsg("Карточка обновлена из чата");
            }}
          >
            Обновить карточку
          </button>
        </div>
      ) : null}

      {nextAction ? (
        <div className="cand-next-action" role="status">
          <div className="cand-next-action-body">
            <span className="cand-next-action-kicker">Следующий шаг</span>
            <strong>{nextAction.label}</strong>
            {nextAction.detail ? (
              <span className="cand-next-action-detail">{nextAction.detail}</span>
            ) : null}
          </div>
          <button
            type="button"
            className="chip chip-active"
            onClick={() => {
              if (nextAction.section === "top") {
                document.querySelector(".cand-summary-meeting")?.scrollIntoView({
                  behavior: "smooth",
                  block: "start",
                });
                return;
              }
              setActiveTab(sectionToTab(nextAction.section));
              if (nextAction.section === "ai") {
                setAiSectionOpen(true);
              }
            }}
          >
            Открыть
          </button>
        </div>
      ) : null}

      <nav className="cand-tabs cand-action-nav" aria-label="Разделы карточки">
        {CAND_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`cand-tab${activeTab === tab.id ? " is-active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <StageProgress
        stage={c.hr_stage}
        funnelStages={funnelStages}
        stageLabels={stageLabelsMap}
      />

      {err || msg ? (
        <ActionBanner msg={msg} err={err} tone={bannerTone} />
      ) : null}

      {activeTab === "profile" ? (
      <div className="rec-card">
        {!editingProfile ? (
          <>
            <div className="cand-profile-view">
              <div className="cand-profile-row">
                <span className="cand-profile-label">Телефон</span>
                <span className="cand-profile-value">{phone || "—"}</span>
              </div>
              <div className="cand-profile-row">
                <span className="cand-profile-label">Email</span>
                <span className="cand-profile-value">{email || "—"}</span>
              </div>
              <div className="cand-profile-row">
                <span className="cand-profile-label">Возраст</span>
                <span className="cand-profile-value">{age || "—"}</span>
              </div>
              <div className="cand-profile-row">
                <span className="cand-profile-label">Город</span>
                <span className="cand-profile-value">{city || "—"}{metro ? `, м. ${metro}` : ""}</span>
              </div>
              <div className="cand-profile-row">
                <span className="cand-profile-label">Зарплата</span>
                <span className="cand-profile-value">{salary || "—"}</span>
              </div>
              {hrComment ? (
                <div className="cand-profile-row" style={{ alignItems: "flex-start" }}>
                  <span className="cand-profile-label">HR</span>
                  <span className="cand-profile-value">{hrComment}</span>
                </div>
              ) : null}
              {c.vacancy_control_word_enabled && c.vacancy_control_word ? (
                <div className="cand-profile-row" style={{ alignItems: "flex-start" }}>
                  <span className="cand-profile-label">Контрольное слово</span>
                  <span className="cand-profile-value">
                    ожидается: <strong>{c.vacancy_control_word}</strong>
                    {c.control_word_status ? (
                      <>
                        {" "}
                        · {controlWordStatusLabel(c.control_word_status)}
                        {c.control_word_match ? ` («${c.control_word_match}»)` : ""}
                      </>
                    ) : (
                      <span className="muted"> · не проверено (запустите оценку резюме)</span>
                    )}
                    {c.control_word_note ? (
                      <span className="muted hh-micro" style={{ display: "block", marginTop: "0.25rem" }}>
                        {c.control_word_note}
                      </span>
                    ) : null}
                  </span>
                </div>
              ) : null}
            </div>

            <div className="cand-profile-links">
              {resumeLink ? (
                <a href={resumeLink} target="_blank" rel="noreferrer" className="chip chip-active">PDF резюме</a>
              ) : null}
              {hhLink ? (
                <a href={hhLink} target="_blank" rel="noreferrer" className="chip">HH.ru</a>
              ) : null}
              {isOwner && anonResume ? (
                <a href={anonResume} target="_blank" rel="noreferrer" className="chip">
                  Макет PDF
                </a>
              ) : null}
              {!resumeLink && !hhLink && !anonResume ? (
                <span className="muted hh-micro">Ссылки на резюме не добавлены</span>
              ) : null}
            </div>

            <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
              {isDemo ? (
                <p className="muted hh-micro">{DEMO_WRITE_HINT}</p>
              ) : (
                <>
              <button type="button" className="chip" onClick={() => setEditingProfile(true)}>
                Редактировать
              </button>
              <button type="button" className="chip" disabled={writeLocked} onClick={remove}>
                Удалить
              </button>
                </>
              )}
            </div>
          </>
        ) : (
          <>
            {bannerFor("anketa")}
            <div className="hh-field">
              <label className="hh-label" htmlFor="cand-name">Имя</label>
              <input id="cand-name" value={name} onChange={(e) => setName(e.target.value)} disabled={writeLocked} />
            </div>
            <div className="hh-inline-pair">
              <div className="hh-field">
                <label className="hh-label" htmlFor="cand-phone">Телефон</label>
                <input id="cand-phone" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={writeLocked} />
              </div>
              <div className="hh-field">
                <label className="hh-label" htmlFor="cand-email">Email</label>
                <input id="cand-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={writeLocked} placeholder="опционально" />
              </div>
            </div>
            <div className="hh-inline-pair">
              <div className="hh-field">
                <label className="hh-label" htmlFor="cand-age">Возраст</label>
                <input id="cand-age" value={age} onChange={(e) => setAge(e.target.value)} disabled={writeLocked} />
              </div>
              <div className="hh-field">
                <label className="hh-label" htmlFor="cand-city">Город</label>
                <input id="cand-city" value={city} onChange={(e) => setCity(e.target.value)} disabled={writeLocked} />
              </div>
            </div>
            <div className="hh-field">
              <label className="hh-label" htmlFor="cand-metro">Метро</label>
              <input id="cand-metro" value={metro} onChange={(e) => setMetro(e.target.value)} disabled={writeLocked} />
            </div>
            <div className="hh-field">
              <label className="hh-label" htmlFor="cand-salary">Зарплатные ожидания</label>
              <input id="cand-salary" value={salary} onChange={(e) => setSalary(e.target.value)} disabled={writeLocked} />
            </div>

            <h3 className="hh-subhead">Ссылки</h3>
            <LinkField id="cand-resume" label="Резюме PDF (Яндекс.Диск)" openLabel="Открыть PDF" value={resumeLink} onChange={setResumeLink} disabled={writeLocked} placeholder="https://disk.yandex.ru/…" />
            <LinkField id="cand-hh" label="HH (без контактов)" openLabel="Открыть HH" value={hhLink} onChange={setHhLink} disabled={writeLocked} placeholder="https://hh.ru/resume/…" />
            {isOwner ? (
            <>
            <LinkField
              id="cand-anon-resume"
              label="Макет PDF без контактов"
              openLabel="Открыть макет"
              value={anonResume}
              onChange={setAnonResume}
              disabled={writeLocked}
              placeholder="https://disk.yandex.ru/… PDF без телефона и почты"
            />
            <label className="hh-check">
              <input
                type="checkbox"
                checked={previewIncluded}
                onChange={(e) => setPreviewIncluded(e.target.checked)}
                disabled={writeLocked}
              />
              Показать в зоне макетов заказчика
            </label>
            </>
            ) : null}

            <div className="hh-field">
              <label className="hh-label" htmlFor="cand-hr">Комментарий HR</label>
              <textarea id="cand-hr" rows={3} value={hrComment} onChange={(e) => setHrComment(e.target.value)} disabled={writeLocked} />
            </div>

            <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
              <button type="button" className="chip chip-active" disabled={writeLocked} onClick={() => { void saveCard(); setEditingProfile(false); }}>
                Сохранить
              </button>
              <button type="button" className="chip" onClick={() => setEditingProfile(false)}>
                Отмена
              </button>
              <button type="button" className="chip" disabled={writeLocked} onClick={remove}>
                Удалить
              </button>
            </div>
          </>
        )}
      </div>
      ) : null}

      {activeTab === "materials" ? (
      <div className="rec-card">
        <h3 className="rec-card-title">Материалы кандидата</h3>
        {!editingMaterials ? (
          <>
            <div className="cand-profile-view">
              <div className="cand-profile-row">
                <span className="cand-profile-label">Запись</span>
                <span className="cand-profile-value">
                  {video ? (
                    <a href={video} target="_blank" rel="noreferrer">Открыть запись</a>
                  ) : (
                    "—"
                  )}
                </span>
              </div>
              <div className="cand-profile-row">
                <span className="cand-profile-label">Портфолио</span>
                <span className="cand-profile-value">
                  {portfolio ? (
                    <a href={portfolio} target="_blank" rel="noreferrer">Открыть портфолио</a>
                  ) : (
                    "—"
                  )}
                </span>
              </div>
              <div className="cand-profile-row">
                <span className="cand-profile-label">Задание</span>
                <span className="cand-profile-value">
                  {taskLink ? (
                    <a href={taskLink} target="_blank" rel="noreferrer">Открыть задание</a>
                  ) : (
                    "—"
                  )}
                </span>
              </div>
            </div>
            <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
              <button type="button" className="chip" onClick={() => setEditingMaterials(true)}>
                Редактировать
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="muted hh-micro" style={{ marginBottom: "0.75rem" }}>
              Записи собеседований, портфолио, задания и другие файлы.
            </p>
            <LinkField
              id="cand-video"
              label="Запись собеседования"
              openLabel="Открыть запись"
              value={video}
              onChange={setVideo}
              disabled={writeLocked || transcriptionBusy}
              placeholder="Ссылка на запись видео/аудио"
            />
            <LinkField
              id="cand-portfolio"
              label="Портфолио"
              openLabel="Открыть портфолио"
              value={portfolio}
              onChange={setPortfolio}
              disabled={writeLocked}
            />
            <LinkField
              id="cand-task"
              label="Тестовое задание"
              openLabel="Открыть задание"
              value={taskLink}
              onChange={setTaskLink}
              disabled={writeLocked}
              placeholder="https://…"
            />
            <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
              <button
                type="button"
                className="chip chip-active"
                disabled={writeLocked}
                onClick={() => {
                  void saveCard();
                  setEditingMaterials(false);
                }}
              >
                Сохранить
              </button>
              <button type="button" className="chip" onClick={() => setEditingMaterials(false)}>
                Отмена
              </button>
            </div>
          </>
        )}
      </div>
      ) : null}

      {activeTab === "pipeline" ? (
      <>
      <div className="rec-card" id="cand-stage">
        <h3 className="rec-card-title">
          Этап
          <span className="muted hh-micro" style={{ marginLeft: "0.5rem" }}>
            {hrStageLabel(stage || c.hr_stage)}
          </span>
        </h3>
        {bannerFor("stage")}
        {!editingPipeline ? (
          <>
            <div className="cand-profile-view">
              <div className="cand-profile-row">
                <span className="cand-profile-label">HR-этап</span>
                <span className="cand-profile-value">{hrStageLabel(stage || c.hr_stage)}</span>
              </div>
              {showInterviewDateFields ? (
                <div className="cand-profile-row">
                  <span className="cand-profile-label">
                    {stage === "client_meeting" || c.hr_stage === "client_meeting"
                      ? "Встреча"
                      : "Собеседование"}
                  </span>
                  <span className="cand-profile-value">
                    {[interviewDate, interviewTime].filter(Boolean).join(" · ") || "—"}
                  </span>
                </div>
              ) : null}
              {meetingLink ? (
                <div className="cand-profile-row">
                  <span className="cand-profile-label">Zoom</span>
                  <span className="cand-profile-value">
                    <a href={meetingLink} target="_blank" rel="noreferrer">Открыть ссылку</a>
                  </span>
                </div>
              ) : null}
              {stageNote ? (
                <div className="cand-profile-row">
                  <span className="cand-profile-label">Заметка</span>
                  <span className="cand-profile-value">{stageNote}</span>
                </div>
              ) : null}
              {["offer", "internship", "started_work"].includes(stage) ? (
                <div className="cand-profile-row">
                  <span className="cand-profile-label">Гарантия</span>
                  <span className="cand-profile-value">
                    {[warrantyDate, warrantyMonths ? `${warrantyMonths} мес.` : ""]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </span>
                </div>
              ) : null}
            </div>
            <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
              {isDemo ? (
                <>
                  <p className="muted hh-micro">{DEMO_WRITE_HINT}</p>
                  <button type="button" className="chip" onClick={() => setActiveTab("offer")}>
                    К разделу «Сделать оффер»
                  </button>
                </>
              ) : (
                <>
                  <button type="button" className="chip" onClick={() => setEditingPipeline(true)}>
                    Изменить статус
                  </button>
                  <button type="button" className="chip" disabled={writeLocked} onClick={applyClientStage}>
                    Применить этап по статусу заказчика
                  </button>
                  <button type="button" className="chip" onClick={() => setActiveTab("offer")}>
                    К разделу «Сделать оффер»
                  </button>
                </>
              )}
            </div>
          </>
        ) : (
          <>
        <div className="hh-field">
          <label className="hh-label" htmlFor="hr-stage">
            HR-этап
          </label>
          <select
            id="hr-stage"
            value={stage}
            onChange={(e) => setStage(e.target.value)}
            disabled={writeLocked}
          >
            {stageOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        {showInterviewDateFields ? (
          <>
            <div className="hh-inline-pair">
              <div className="hh-field">
                <label className="hh-label" htmlFor="iv-date">
                  {stage === "client_meeting" || c.hr_stage === "client_meeting"
                    ? "Дата встречи с заказчиком"
                    : "Дата собеседования"}
                </label>
                <input
                  id="iv-date"
                  type="date"
                  value={interviewDate}
                  onChange={(e) => setInterviewDate(e.target.value)}
                  disabled={writeLocked}
                />
              </div>
              <div className="hh-field">
                <label className="hh-label" htmlFor="iv-time">
                  Время
                </label>
                <input
                  id="iv-time"
                  type="time"
                  value={interviewTime}
                  onChange={(e) => setInterviewTime(e.target.value)}
                  disabled={writeLocked}
                />
              </div>
            </div>
            {/* Zoom meeting: schedule → join_url → copy invite / mailto */}
            <div className="hh-meeting-block">
              <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.35rem" }}>
                <button
                  type="button"
                  className="chip chip-active"
                  disabled={writeLocked || scheduleBusy}
                  onClick={() => setScheduleModalOpen(true)}
                >
                  Назначить встречу
                </button>
              </div>
              {meetingLink ? (
                <div className="hh-field" style={{ marginTop: "0.55rem" }}>
                  <label className="hh-label" htmlFor="meet-link">
                    Ссылка на встречу (Zoom)
                  </label>
                  <input id="meet-link" value={meetingLink} readOnly disabled={writeLocked} />
                  <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.45rem" }}>
                    <button
                      type="button"
                      className="chip chip-active"
                      disabled={writeLocked}
                      onClick={async () => {
                        const text = buildMeetingInviteText({
                          name,
                          date: interviewDate,
                          time: interviewTime,
                          link: meetingLink,
                        });
                        try {
                          await navigator.clipboard.writeText(text);
                          setCopyInviteDone(true);
                          setTimeout(() => setCopyInviteDone(false), 2000);
                        } catch {
                          setFeedback("stage", null, "Не удалось скопировать — скопируйте ссылку вручную");
                        }
                      }}
                    >
                      {copyInviteDone ? "Скопировано" : "📋 Скопировать приглашение"}
                    </button>
                    {email.trim() ? (
                      <a
                        className="chip"
                        href={buildMailtoHref(
                          email.trim(),
                          `Встреча — ${(name || "").trim() || "кандидат"}`,
                          buildMeetingInviteText({
                            name,
                            date: interviewDate,
                            time: interviewTime,
                            link: meetingLink,
                          }),
                        )}
                      >
                        📧 Отправить Email
                      </a>
                    ) : (
                      <button type="button" className="chip" disabled title="Укажите email в анкете">
                        📧 Отправить Email
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                <p className="muted hh-micro" style={{ marginTop: "0.35rem" }}>
                  Ссылка появится после назначения через Zoom.
                </p>
              )}
            </div>
          </>
        ) : null}
        <div className="hh-field">
          <label className="hh-label" htmlFor="stage-note">
            Заметка к этапу
          </label>
          <input
            id="stage-note"
            value={stageNote}
            onChange={(e) => setStageNote(e.target.value)}
            disabled={writeLocked}
            placeholder="необязательно"
          />
        </div>
        {["offer", "internship", "started_work"].includes(stage) ? (
          <div className="hh-inline-pair">
            <div className="hh-field">
              <label className="hh-label" htmlFor="warranty-date">
                Дата начала гарантии
              </label>
              <input
                id="warranty-date"
                type="date"
                value={warrantyDate}
                onChange={(e) => setWarrantyDate(e.target.value)}
                disabled={writeLocked}
              />
            </div>
            <div className="hh-field">
              <label className="hh-label" htmlFor="warranty-months">
                Срок (мес)
              </label>
              <select
                id="warranty-months"
                value={warrantyMonths}
                onChange={(e) => setWarrantyMonths(Number(e.target.value))}
                disabled={writeLocked}
              >
                {[1, 2, 3, 4, 5, 6].map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ) : null}
        <label className="hh-check">
          <input
            type="checkbox"
            checked={deleteCalendarEvent}
            onChange={(e) => setDeleteCalendarEvent(e.target.checked)}
            disabled={writeLocked}
          />
          Удалить событие из Google Calendar
        </label>
        <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
          <button
            type="button"
            className="chip chip-active"
            disabled={writeLocked}
            onClick={() => {
              void (async () => {
                await saveStage();
                setEditingPipeline(false);
              })();
            }}
          >
            Зафиксировать этап
          </button>
          <button type="button" className="chip" onClick={() => setEditingPipeline(false)}>
            Отмена
          </button>
          <button type="button" className="chip" disabled={writeLocked} onClick={applyClientStage}>
            Применить этап по статусу заказчика
          </button>
        </div>
          </>
        )}
      </div>

      <div className="rec-card" id="cand-stage-history">
        <h3 className="rec-card-title">
          История этапов
          {Array.isArray(c.payload?.hr_stage_history) ? (
            <span className="muted hh-micro" style={{ marginLeft: "0.5rem" }}>
              {(c.payload.hr_stage_history as unknown[]).length}
            </span>
          ) : null}
        </h3>
        <ul className="muted" style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {(Array.isArray(c.payload?.hr_stage_history)
            ? (c.payload.hr_stage_history as { stage?: string; at?: string; note?: string }[])
            : []
          ).map((h, i) => (
            <li key={`${h.at || i}-${h.stage}`}>
              {hrStageLabel(h.stage || "")} · {formatDateRu(h.at || null)}
              {h.note ? ` — ${h.note}` : ""}
            </li>
          ))}
          {!Array.isArray(c.payload?.hr_stage_history) ||
          !(c.payload.hr_stage_history as unknown[]).length ? (
            <li>Пока пусто</li>
          ) : null}
        </ul>
      </div>

      {!isDemo ? (
      <div className="rec-card">
        <div className="hh-field">
          <label className="hh-label" htmlFor="copy-target">
            Копировать в вакансию
          </label>
          <select
            id="copy-target"
            value={copyTargetId}
            onChange={(e) => setCopyTargetId(e.target.value)}
            disabled={writeLocked}
          >
            <option value="">— выбрать —</option>
            {vacancies.map((v) => (
              <option key={v.id} value={v.id}>
                {v.title}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="chip"
            disabled={writeLocked || !copyTargetId}
            onClick={copyCandidate}
            style={{ marginTop: "0.35rem" }}
          >
            Скопировать кандидата
          </button>
        </div>
      </div>
      ) : null}
      </>
      ) : null}

      {activeTab === "offer" ? <CandidateOfferPanel candidateId={c.id} /> : null}

      <div className="rec-card" id="questionnaire" hidden={activeTab !== "interview"}>
        <h3 className="rec-card-title">
          Опросник и собеседование
          {(() => {
            const dig =
              c.interview_digest ||
              (c.payload as { interview_digest?: { summary?: string; qa?: unknown[] } } | undefined)
                ?.interview_digest;
            const hasDig = Boolean(
              dig &&
                ((dig.summary || "").trim() || (Array.isArray(dig.qa) && dig.qa.length > 0)),
            );
            let hint: string | undefined;
            if (hasDig && hasQuestionnaire) {
              hint = `${(c.interview_questionnaire as unknown[]).length} вопросов · есть конспект`;
            } else if (hasQuestionnaire) {
              hint = `${(c.interview_questionnaire as unknown[]).length} вопросов`;
            } else if (hasDig) {
              hint = "есть конспект";
            } else if ((c.transcript || "").trim()) {
              hint = "есть расшифровка";
            }
            return hint ? (
              <span className="muted hh-micro" style={{ marginLeft: "0.5rem" }}>
                {hint}
              </span>
            ) : null;
          })()}
        </h3>
        <QuestionnairePanel
          embedded
          readOnly={isDemo}
          candidate={c}
          initialItems={
            Array.isArray(c.interview_questionnaire)
              ? (c.interview_questionnaire as QItem[])
              : null
          }
          videoLinkDraft={video}
          interviewNotesDraft={interviewEvalNotes}
          onInterviewNotesChange={setInterviewEvalNotes}
          onCandidateChange={applyCandidate}
          onTranscribeAndEvaluate={transcribeAndEvaluate}
          onEvaluateInterview={evaluateInterview}
          onEvaluateResume={evaluateResume}
          transcriptionBusy={transcriptionBusy}
          transcriptionStatus={transcriptionBusy && job ? job.progress_label : null}
          evaluateBusy={evalBusy}
          evaluateResumeBusy={resumeEvalBusy}
          evaluateResumeStatus={resumeEvalBusy && job ? job.progress_label : null}
        />
      </div>

      {activeTab === "client" ? (
      <div className="rec-card" id="cand-client">
        <h3 className="rec-card-title">
          Заказчик
          <span className="muted hh-micro" style={{ marginLeft: "0.5rem" }}>
            {c.client_status === "wait"
              ? clientStatusLabelForCard(c.hr_stage, c.client_status)
              : clientStatusLabel(c.client_status)}
          </span>
        </h3>
        {bannerFor("client")}
        {webNotifyEnabled ? (
          <ClientZoneLink
            path={clientZonePath}
            label="Ссылка клиентской зоны для заказчика"
            compact={Boolean(clientZonePath)}
          />
        ) : null}
        <p className="muted hh-micro">
          {telegramNotifyEnabled && bitrixNotifyEnabled
            ? "Отправка в Telegram и Bitrix24 (каналы в настройках Bitrix24)."
            : bitrixNotifyEnabled
              ? "Отправка создаёт задачу в Bitrix24 со ссылками решения."
              : telegramNotifyEnabled
                ? "Отправка карточки в Telegram-чат с кнопками статуса."
                : "Включите канал в настройках Bitrix24."}
          {telegramNotifyEnabled
            ? " «Обновить данные» пересобирает карточку в Telegram."
            : null}
        </p>
        <label className="hh-check">
          <input
            type="checkbox"
            checked={moveToClientReview}
            onChange={(e) => setMoveToClientReview(e.target.checked)}
            disabled={writeLocked}
          />
          Перевести на этап «На оценке у заказчика»
        </label>
        <div className="hh-row-actions" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
          <button type="button" className="chip chip-active" disabled={writeLocked} onClick={sendToChat}>
            Отправить заказчику
          </button>
          {telegramNotifyEnabled ? (
            <>
              <button type="button" className="chip" disabled={writeLocked} onClick={refreshClientCard}>
                Обновить данные по кандидату
              </button>
              <button
                type="button"
                className="chip"
                disabled={writeLocked}
                onClick={() => remind("evaluate")}
              >
                Напомнить о кандидате
              </button>
              <button type="button" className="chip" disabled={writeLocked} onClick={() => remind("decide")}>
                Напомнить принять решение
              </button>
            </>
          ) : null}
        </div>
        {telegramNotifyEnabled ? (
        <div className="hh-field" style={{ marginTop: "0.75rem" }}>
          <label className="hh-label">Доп. материал в Telegram</label>
          <input
            value={materialTitle}
            onChange={(e) => setMaterialTitle(e.target.value)}
            disabled={writeLocked}
            placeholder="Заголовок"
          />
          <input
            value={materialUrl}
            onChange={(e) => setMaterialUrl(e.target.value)}
            disabled={writeLocked}
            placeholder="https://…"
            style={{ marginTop: "0.35rem" }}
          />
          <button
            type="button"
            className="chip"
            disabled={writeLocked || !materialUrl.trim()}
            onClick={sendMaterial}
            style={{ marginTop: "0.35rem" }}
          >
            Отправить материал
          </button>
        </div>
        ) : null}
        {telegramNotifyEnabled &&
        Array.isArray(c.payload?.extra_materials) &&
        (c.payload.extra_materials as unknown[]).length ? (
          <ul className="muted" style={{ marginTop: "0.5rem", paddingLeft: "1.1rem" }}>
            {(
              c.payload.extra_materials as {
                title?: string;
                url?: string;
                sent_at?: string;
              }[]
            ).map((m, i) => (
              <li key={`${m.url || i}-${m.sent_at || i}`}>
                {m.title || "Материал"}
                {m.url ? (
                  <>
                    {" · "}
                    <a href={m.url} target="_blank" rel="noreferrer">
                      открыть
                    </a>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      ) : null}

      {activeTab === "ai" && (c.client_comment || hasAiComment || c.ai_score != null) ? (
        <div className="rec-card" id="ai-comment-block">
          <h3 className="rec-card-title">
            Комментарий ИИ
            {c.ai_score != null ? (
              <span className="muted hh-micro" style={{ marginLeft: "0.5rem" }}>
                {c.ai_score}/4
              </span>
            ) : null}
          </h3>
          <div className="meta-grid">
            <div className="meta-item">
              <span>Оценка</span>
              <strong>
                {c.ai_score != null ? `${c.ai_score}/4` : "—"}
                {c.ai_score_source ? ` · ${aiScoreSourceLabel(c.ai_score_source)}` : ""}
              </strong>
            </div>
            <div className="meta-item">
              <span>Добавлен</span>
              <strong>{formatDateRu(c.created_at)}</strong>
            </div>
            <div className="meta-item">
              <span>Статус обновлён</span>
              <strong>{formatDateRu(c.status_updated_at)}</strong>
            </div>
          </div>
          {c.client_comment ? (
            <div className="doc-block" style={{ marginTop: "0.75rem" }}>
              <h3 className="hh-subhead">Комментарий заказчика</h3>
              <div className="doc-text">{c.client_comment}</div>
            </div>
          ) : null}
          <AiCommentBlock
            id="ai-comment-inner"
            comment={c.ai_comment}
            sections={sections}
            open={aiCommentOpen}
            onOpenChange={setAiCommentOpen}
          />
        </div>
      ) : null}

      {activeTab === "ai" && !(c.client_comment || hasAiComment || c.ai_score != null) ? (
        <div className="rec-card">
          <h3 className="rec-card-title">Комментарий ИИ</h3>
          {resumeEvalBusy ? (
            <p className="muted hh-micro">
              {job?.progress_label || "Оценка резюме в очереди…"}
            </p>
          ) : null}
          {candidateHasResumeForEval(c) ? (
            <>
              <p className="muted">
                Резюме уже есть в карточке, но оценка ИИ ещё не запускалась или не завершилась.
              </p>
              <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
                <button
                  type="button"
                  className="chip chip-active"
                  disabled={isDemo || resumeEvalBusy || attachBusy}
                  onClick={() => {
                    void evaluateResume().catch((e) => {
                      setErr(e instanceof Error ? e.message : "Ошибка оценки");
                    });
                  }}
                >
                  {resumeEvalBusy ? "Оценка…" : "Оценить по резюме"}
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="muted">
                {candidateCreatedManually(c)
                  ? "Кандидат создан вручную, резюме не подгружалось — поэтому оценки ИИ нет."
                  : "Текста резюме в карточке нет — оценку ИИ запустить нельзя."}
              </p>
              <p className="muted hh-micro">
                Добавьте PDF по ссылке или файлом прямо здесь, затем запустится оценка.
              </p>
              <div className="hh-field">
                <label className="hh-label" htmlFor="ai-resume-link">
                  Ссылка на PDF резюме
                </label>
                <input
                  id="ai-resume-link"
                  value={attachResumeLink}
                  onChange={(e) => setAttachResumeLink(e.target.value)}
                  disabled={isDemo || attachBusy || resumeEvalBusy}
                  placeholder="https://disk.yandex.ru/…"
                />
              </div>
              <div className="hh-field">
                <label className="hh-label" htmlFor="ai-resume-file">
                  Или файл (PDF, Word)
                </label>
                <input
                  id="ai-resume-file"
                  type="file"
                  accept=".pdf,.doc,.docx,.txt"
                  disabled={isDemo || attachBusy || resumeEvalBusy}
                  onChange={(e) => setAttachResumeFile(e.target.files?.[0] || null)}
                />
              </div>
              <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  className="chip chip-active"
                  disabled={
                    attachBusy ||
                    resumeEvalBusy ||
                    (!attachResumeFile && !attachResumeLink.trim())
                  }
                  onClick={() => void attachResumeThenEvaluate()}
                >
                  {attachBusy ? "Загрузка…" : "Загрузить и оценить"}
                </button>
              </div>
            </>
          )}
        </div>
      ) : null}

      {scheduleModalOpen ? (
        <div
          className="cz-modal-backdrop"
          role="presentation"
          onClick={() => !scheduleBusy && setScheduleModalOpen(false)}
        >
          <div
            className="cz-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="schedule-meeting-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="schedule-meeting-title">Назначить встречу</h2>
            <p className="muted hh-micro" style={{ margin: 0 }}>
              Дата и время берутся из полей выше. Zoom создаст встречу и сохранит ссылку.
            </p>
            <p className="muted hh-micro" style={{ margin: 0 }}>
              {interviewDate && interviewTime
                ? `${formatMeetingDateRu(interviewDate)} · ${interviewTime}`
                : "Сначала укажите дату и время собеседования."}
            </p>
            <button
              type="button"
              className="chip chip-active"
              disabled={isDemo || scheduleBusy || !interviewDate || !interviewTime}
              onClick={async () => {
                setScheduleBusy(true);
                setFeedback("stage", null);
                try {
                  const res = await apiFetch(`/api/v1/candidates/${c.id}/zoom-meeting`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      start_date: interviewDate,
                      start_time: interviewTime,
                      duration_minutes: 60,
                    }),
                  });
                  const data = await res.json().catch(() => ({}));
                  if (!res.ok) {
                    const detail =
                      data && typeof data === "object" && "detail" in data
                        ? String((data as { detail?: unknown }).detail || "")
                        : "";
                    throw new Error(detail || `HTTP ${res.status}`);
                  }
                  applyCandidate(data as CandidateDetail);
                  setRemoteInterview(true);
                  setScheduleModalOpen(false);
                  setFeedback("stage", "Zoom-встреча создана, ссылка сохранена");
                  router.refresh();
                } catch (e) {
                  setFeedback(
                    "stage",
                    null,
                    e instanceof Error ? e.message : "Не удалось создать Zoom-встречу",
                  );
                } finally {
                  setScheduleBusy(false);
                }
              }}
            >
              {scheduleBusy ? "Создаём…" : "Zoom (авто-генерация)"}
            </button>
            <button
              type="button"
              className="chip"
              disabled={isDemo || scheduleBusy}
              onClick={() => setScheduleModalOpen(false)}
            >
              Отмена
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
