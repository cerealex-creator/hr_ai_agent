"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Legacy URL — Disk setup lives under candidate intake channels. */
export default function YandexDiskSettingsRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/settings/candidate-intake#yandex-disk-connect");
  }, [router]);
  return (
    <p className="muted" style={{ padding: "1.5rem" }}>
      Переход к способам добавления кандидатов…
    </p>
  );
}
