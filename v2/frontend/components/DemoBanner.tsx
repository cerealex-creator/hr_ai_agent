"use client";

import { DEMO_CONTACT } from "@/lib/demo";

export function DemoBanner() {
  return (
    <div className="demo-banner" role="status">
      Это демо-режим. Для полного доступа напишите:{" "}
      <a href={`mailto:${DEMO_CONTACT}`}>{DEMO_CONTACT}</a>
    </div>
  );
}
