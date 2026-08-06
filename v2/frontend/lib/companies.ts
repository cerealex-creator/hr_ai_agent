export type ChannelBrief = { id: string; name: string | null; external_id: string };

export type CompanyDept = {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
  chat_mode: string;
  kind: string;
  channel: ChannelBrief | null;
  client_zone_token?: string | null;
  has_client_zone?: boolean;
};

export type CompanyNode = CompanyDept & { departments: CompanyDept[] };

export function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

export function companyModeLabel(mode: string): string {
  return mode === "departments" ? "чаты по подразделениям" : "один чат на компанию";
}
