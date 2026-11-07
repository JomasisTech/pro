"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const DISMISSED_KEY = "bizpilotpro-leads-card-dismissed";
const STARTED_KEY = "bizpilotpro-leads-card-started";

export function LeadsDiscoveryCard() {
  const [ready, setReady] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    setDismissed(window.localStorage.getItem(DISMISSED_KEY) === "true");
    setStarted(window.localStorage.getItem(STARTED_KEY) === "true");
    setReady(true);
  }, []);

  if (!ready || dismissed) return null;

  function dismiss() {
    window.localStorage.setItem(DISMISSED_KEY, "true");
    setDismissed(true);
  }

  return (
    <section className={`db-leads-card${started ? " is-compact" : ""}`} aria-label="Lead generation">
      <div className="db-leads-card-mark" aria-hidden="true"><span>✦</span></div>
      <div className="db-leads-card-copy">
        {started ? <>
          <strong>Lead Generation</strong>
          <span>Explore business prospects and organise your pipeline.</span>
        </> : <>
          <span className="db-leads-eyebrow">NEW · BUSINESS GROWTH</span>
          <strong>Find your next customers with Leads</strong>
          <span>Discover relevant businesses, review prospects and build a stronger pipeline from one workspace.</span>
        </>}
      </div>
      <div className="db-leads-card-actions">
        <Link href="/leads" className="db-leads-action">{started ? "Open Leads" : "Explore Leads"}<span aria-hidden="true">→</span></Link>
        <button type="button" className="db-leads-dismiss" onClick={dismiss} aria-label="Dismiss lead generation announcement" title="Dismiss">×</button>
      </div>
    </section>
  );
}
