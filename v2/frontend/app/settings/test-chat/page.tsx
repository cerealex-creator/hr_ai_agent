"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Test chat moved into «Настройка взаимодействия». */
export default function TestChatSettingsPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/settings/companies#test-chat");
  }, [router]);
  return <p className="muted">Перенос в настройку взаимодействия…</p>;
}
