"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { NavIcon } from "@/components/app-chrome";
import { Select } from "@/components/select";

type Lead = { id: number; company: string; category: string; location: string; website: string; email: string; score: number; status: "New" | "Reviewed" | "Saved"; initials: string; color: string };

// Clearly fictional preview records. Live discovery is intentionally not connected until the backend is built.
const SAMPLE_LEADS: Lead[] = [
  { id: 1, company: "Northstar Creative", category: "Marketing agency", location: "Abuja, Nigeria", website: "northstar.example", email: "hello@northstar.example", score: 94, status: "New", initials: "NC", color: "violet" },
  { id: 2, company: "Greenline Foods", category: "Food & beverage", location: "Lagos, Nigeria", website: "greenline.example", email: "contact@greenline.example", score: 89, status: "New", initials: "GF", color: "green" },
  { id: 3, company: "Atlas Property Group", category: "Real estate", location: "Abuja, Nigeria", website: "atlasproperty.example", email: "info@atlasproperty.example", score: 86, status: "Reviewed", initials: "AP", color: "blue" },
  { id: 4, company: "Mosaic Wellness", category: "Health & wellness", location: "Port Harcourt, Nigeria", website: "mosaicwellness.example", email: "team@mosaicwellness.example", score: 82, status: "Saved", initials: "MW", color: "orange" },
  { id: 5, company: "Brightpath Learning", category: "Education", location: "Lagos, Nigeria", website: "brightpath.example", email: "hello@brightpath.example", score: 78, status: "New", initials: "BL", color: "pink" },
];

const statusClass = (status: Lead["status"]) => status.toLowerCase();

export default function LeadsPage() {
  const [industry, setIndustry] = useState("All industries");
  const [location, setLocation] = useState("Abuja");
  const [keyword, setKeyword] = useState("");
  const [activeTab, setActiveTab] = useState("All leads");
  const [searched, setSearched] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [leads, setLeads] = useState(SAMPLE_LEADS);
  const [notice, setNotice] = useState("This is a front-end preview. Live business discovery and contact verification will be connected in a later backend phase.");

  const visibleLeads = useMemo(() => leads.filter((lead) => {
    const tabMatch = activeTab === "All leads" || lead.status === activeTab;
    const industryMatch = industry === "All industries" || lead.category.toLowerCase().includes(industry.toLowerCase());
    const locationMatch = !searched || !location.trim() || lead.location.toLowerCase().includes(location.toLowerCase());
    const keywordMatch = !keyword.trim() || `${lead.company} ${lead.category} ${lead.location}`.toLowerCase().includes(keyword.toLowerCase());
    return tabMatch && industryMatch && locationMatch && keywordMatch;
  }), [leads, activeTab, industry, location, keyword, searched]);

  function runPreviewSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearched(true);
    window.localStorage.setItem("bizpilotpro-leads-card-started", "true");
    setSelected([]);
    setNotice("Preview filters applied to the sample records below. No external search has been run.");
  }

  function toggleLead(id: number) {
    setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function saveSelected() {
    if (!selected.length) return;
    setLeads((current) => current.map((lead) => selected.includes(lead.id) ? { ...lead, status: "Saved" } : lead));
    setNotice(`${selected.length} sample ${selected.length === 1 ? "lead" : "leads"} saved in this preview.`);
    setSelected([]);
  }

  function exportSelected() {
    const rows = leads.filter((lead) => selected.includes(lead.id));
    if (!rows.length) return;
    const csv = ["Company,Industry,Location,Website,Email,Sample score,Status", ...rows.map((lead) => [lead.company, lead.category, lead.location, lead.website, lead.email, lead.score, lead.status].map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "bizpilotpro-sample-leads.csv"; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice("Your selected sample records were exported. These are fictional preview entries.");
  }

  return (
    <main className="leads-page">
      <div className="leads-breadcrumb"><Link href="/">Dashboard</Link><span>/</span><span>Leads</span></div>
      <header className="leads-heading">
        <div><div className="leads-kicker"><span className="leads-kicker-dot" /> GROW YOUR BUSINESS</div><h1>Lead generation</h1><p>Find relevant businesses, organise promising prospects and build your pipeline.</p></div>
        <div className="leads-heading-actions"><span className="leads-preview-pill"><span /> Front-end preview</span><button type="button" className="leads-help-button" onClick={() => setNotice("Live discovery, verification and enrichment are not connected yet. This page currently demonstrates the planned workflow using fictional sample records.")}> <span aria-hidden="true">ⓘ</span> About this preview</button></div>
      </header>

      <div className="leads-notice" role="status" hidden={!notice}><span className="leads-notice-icon">i</span><p>{notice}</p><button type="button" aria-label="Dismiss notice" onClick={() => setNotice("")}>×</button></div>

      <section className="leads-search-card" aria-labelledby="leads-search-title">
        <div className="leads-section-heading"><div><span className="leads-step">01</span><div><h2 id="leads-search-title">Define your ideal customers</h2><p>Choose the type of businesses you want to reach.</p></div></div><span className="leads-ai-tag">✦ AI-assisted workflow</span></div>
        <form className="leads-search-form" onSubmit={runPreviewSearch}>
          <label className="leads-field leads-field-wide"><span>Industry or niche</span><Select value={industry} onChange={(event) => setIndustry(event.target.value)} className="w-full"><option>All industries</option><option>Marketing</option><option>Food</option><option>Real estate</option><option>Wellness</option><option>Education</option></Select></label>
          <label className="leads-field"><span>Location</span><div className="leads-input-icon"><NavIcon name="building"/><input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="City, region or country" /></div></label>
          <label className="leads-field"><span>Keywords <small>Optional</small></span><input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="e.g. growing local businesses" /></label>
          <button type="submit" className="leads-search-button"><NavIcon name="sparkle"/> Preview results <span>→</span></button>
        </form>
        <div className="leads-search-foot"><span><NavIcon name="shield"/> Only publicly available business information should be used.</span><span>Search criteria can be refined later.</span></div>
      </section>

      <section className="leads-stats" aria-label="Lead pipeline summary">
        <article><span className="leads-stat-icon violet"><NavIcon name="users"/></span><div><small>Sample prospects</small><strong>{leads.length}</strong><span>Fictional preview records</span></div></article>
        <article><span className="leads-stat-icon blue"><NavIcon name="check-circle"/></span><div><small>Reviewed</small><strong>{leads.filter((lead) => lead.status === "Reviewed").length}</strong><span>Marked for review</span></div></article>
        <article><span className="leads-stat-icon green"><NavIcon name="bookmark"/></span><div><small>Saved leads</small><strong>{leads.filter((lead) => lead.status === "Saved").length}</strong><span>In your sample pipeline</span></div></article>
        <article><span className="leads-stat-icon orange"><NavIcon name="target"/></span><div><small>Average fit score</small><strong>{Math.round(leads.reduce((sum, lead) => sum + lead.score, 0) / leads.length)}<em>/100</em></strong><span>Illustrative scoring only</span></div></article>
      </section>

      <section className="leads-results-card" aria-labelledby="leads-results-title">
        <div className="leads-results-header"><div><span className="leads-step">02</span><div><h2 id="leads-results-title">Your prospects</h2><p>Review and organise businesses before taking action.</p></div></div><div className="leads-results-actions"><button type="button" className="leads-secondary-button" disabled={!selected.length} onClick={exportSelected}>↓ Export selected</button><button type="button" className="leads-primary-small" disabled={!selected.length} onClick={saveSelected}>＋ Save selected{selected.length ? ` (${selected.length})` : ""}</button></div></div>
        <div className="leads-tabs" role="tablist" aria-label="Filter leads">{["All leads", "New", "Reviewed", "Saved"].map((tab) => <button type="button" role="tab" aria-selected={activeTab === tab} className={activeTab === tab ? "active" : ""} key={tab} onClick={() => { setActiveTab(tab); setSelected([]); }}>{tab}<span>{tab === "All leads" ? leads.length : leads.filter((lead) => lead.status === tab).length}</span></button>)}</div>
        <div className="leads-table-wrap"><table className="leads-table"><thead><tr><th><input type="checkbox" aria-label="Select all visible leads" checked={visibleLeads.length > 0 && visibleLeads.every((lead) => selected.includes(lead.id))} onChange={(event) => setSelected(event.target.checked ? visibleLeads.map((lead) => lead.id) : [])}/></th><th>Business</th><th>Location</th><th>Contact details</th><th>Fit score</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{visibleLeads.map((lead) => <tr key={lead.id}><td><input type="checkbox" aria-label={`Select ${lead.company}`} checked={selected.includes(lead.id)} onChange={() => toggleLead(lead.id)}/></td><td><div className="leads-company"><span className={`leads-company-avatar ${lead.color}`}>{lead.initials}</span><span><strong>{lead.company}</strong><small>{lead.category}</small></span></div></td><td>{lead.location}</td><td><span className="leads-contact-email">{lead.email}</span><small className="leads-contact-site">{lead.website}</small></td><td><span className="leads-score"><i style={{ width: `${lead.score}%` }}/></span><b className="leads-score-number">{lead.score}</b></td><td><span className={`leads-status ${statusClass(lead.status)}`}>{lead.status}</span></td><td><button type="button" className="leads-row-menu" aria-label={`Save ${lead.company}`} onClick={() => { setLeads((current) => current.map((item) => item.id === lead.id ? { ...item, status: item.status === "Saved" ? "New" : "Saved" } : item)); setNotice(`${lead.company} updated in the sample preview.`); }}>{lead.status === "Saved" ? "★" : "☆"}</button></td></tr>)}</tbody></table>
          {!visibleLeads.length ? <div className="leads-empty"><span>⌕</span><strong>No sample prospects match these filters</strong><p>Try another industry, location or keyword.</p><button type="button" onClick={() => { setIndustry("All industries"); setLocation(""); setKeyword(""); setSearched(false); setActiveTab("All leads"); }}>Clear filters</button></div> : null}
        </div>
        <div className="leads-results-footer"><span>Showing {visibleLeads.length} of {leads.length} fictional sample records</span><span>Live data will appear here when discovery is connected.</span></div>
      </section>

      <section className="leads-next-steps"><div className="leads-next-icon">✦</div><div><strong>From discovery to meaningful conversations</strong><p>Future stages will add contact quality checks, duplicate detection, lead scoring and approval-based outreach.</p></div><span className="leads-coming-soon">Planned workflow</span></section>
    </main>
  );
}
