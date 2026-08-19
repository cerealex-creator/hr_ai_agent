"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useAuth } from "@/components/AuthGate";
import { RecruitingShell } from "@/components/RecruitingShell";
import { DEMO_WRITE_HINT } from "@/lib/demo";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { isDemo } = useAuth();
  const isHub = pathname === "/settings";
  if (isDemo && !isHub) {
    return (
      <RecruitingShell activePath="/settings" title="Настройки">
        <p className="warn cz-banner">{DEMO_WRITE_HINT}</p>
        <p className="muted">Внутри разделов настроек в демо нельзя. Снаружи видны только плашки.</p>
        <Link href="/settings" className="chip">
          К плашкам настроек
        </Link>
      </RecruitingShell>
    );
  }
  return <>{children}</>;
}
