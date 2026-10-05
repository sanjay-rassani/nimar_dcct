(() => {
  const app = document.getElementById("dashboard-app");
  if (!app) return;
  const isNimar = app.dataset.isNimar === "true";

  const escapeHtml = (s) =>
    String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");

  function kpi(label, value) {
    return `<div class="kpi-card"><span class="kpi-label">${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`;
  }

  function bar(pct) {
    const width = Math.max(0, Math.min(100, pct || 0));
    return `<div class="progress-bar"><span style="width:${width}%"></span><em>${width}%</em></div>`;
  }

  function lineChart(canvasId, label, series, color) {
    const el = document.getElementById(canvasId);
    if (!el || typeof Chart === "undefined") return;
    const labels = series.map((r) => r.date);
    const data = series.map((r) => r.count);
    new Chart(el, {
      type: "line",
      data: {
        labels: labels.length ? labels : ["—"],
        datasets: [
          {
            label,
            data: data.length ? data : [0],
            borderColor: color,
            backgroundColor: color + "33",
            tension: 0.25,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });
  }

  async function load() {
    const err = document.getElementById("dash-error");
    err.hidden = true;
    try {
      const res = await fetch("/api/dashboard/", { credentials: "same-origin" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to load dashboard");
      const o = data.overview;
      document.getElementById("dash-subtitle").textContent = isNimar
        ? `${o.completion_pct}% complete · ${o.awaiting_verification} awaiting your review`
        : `${o.open} open points · ${o.overdue} overdue · ${o.open_issues} open issues`;

      document.getElementById("dash-kpis").innerHTML = [
        kpi("Total", o.total),
        kpi("Closed", o.closed),
        kpi("Open", o.open),
        kpi("In progress", o.in_progress),
        kpi("Awaiting NIMAR", o.awaiting_verification),
        kpi("Rework", o.rework_requested),
        kpi("Open issues", o.open_issues),
        kpi("Overdue", o.overdue),
        kpi("Completion", `${o.completion_pct}%`),
      ].join("");

      document.getElementById("dash-phases").innerHTML = data.phases.length
        ? data.phases
            .map(
              (p) => `<div class="metric-row"><div><strong>${escapeHtml(p.name)}</strong> · ${p.closed}/${p.total}</div>${bar(p.completion_pct)}</div>`
            )
            .join("")
        : `<p class="empty-state">No phase data yet.</p>`;

      document.getElementById("dash-modules").innerHTML = data.modules.length
        ? data.modules
            .map(
              (m) => `<div class="metric-row"><div><strong>${escapeHtml(m.name)}</strong> · ${m.completed}/${m.total}</div>${bar(m.completion_pct)}</div>`
            )
            .join("")
        : `<p class="empty-state">No module data yet.</p>`;

      if (isNimar) {
        document.getElementById("dash-focus").innerHTML = data.needs_nimar_review.length
          ? `<ul class="focus-list">${data.needs_nimar_review
              .map(
                (p) =>
                  `<li><a href="/points/"><strong>${escapeHtml(p.external_id)}</strong></a> ${escapeHtml(p.title || "")}</li>`
              )
              .join("")}</ul>`
          : `<p class="empty-state">No points awaiting NIMAR review.</p>`;
      } else {
        const f = data.forbmax_focus || {};
        document.getElementById("dash-focus").innerHTML = `
          <ul class="focus-list">
            <li>Remaining work: <strong>${f.remaining_work}</strong></li>
            <li>Overdue: <strong>${f.overdue}</strong></li>
            <li>Rework: <strong>${f.rework}</strong></li>
            <li>Client pending: <strong>${f.client_pending}</strong></li>
            <li>Open issues: <strong>${f.open_issues}</strong></li>
            <li>In progress: <strong>${f.in_progress}</strong></li>
          </ul>`;
      }

      const iss = data.issues;
      document.getElementById("dash-issues").innerHTML = `
        <ul class="focus-list">
          <li>Open: <strong>${iss.open_issues}</strong></li>
          <li>Resolved/closed: <strong>${iss.resolved_issues}</strong></li>
          <li>Oldest open: <strong>${iss.oldest_open_issue ? escapeHtml(iss.oldest_open_issue.title) + " (" + iss.oldest_open_issue.age_days + "d)" : "—"}</strong></li>
        </ul>`;

      document.getElementById("dash-recent").innerHTML = data.recent_updates.length
        ? `<table class="compact-table"><thead><tr><th>ID</th><th>Title</th><th>Status</th><th>Updated</th></tr></thead><tbody>${data.recent_updates
            .map(
              (u) =>
                `<tr><td><strong>${escapeHtml(u.external_id)}</strong></td><td>${escapeHtml(u.title || "—")}</td><td>${escapeHtml(u.status_label)}</td><td>${escapeHtml((u.updated_at || "").replace("T", " ").slice(0, 16))}</td></tr>`
            )
            .join("")}</tbody></table>`
        : `<p class="empty-state">No recent updates.</p>`;

      lineChart("chart-closed", "Points closed", data.trends.points_closed_over_time || [], "#245b8a");
      const opened = data.trends.issues_opened_over_time || [];
      const resolved = data.trends.issues_resolved_over_time || [];
      const dates = Array.from(new Set([...opened.map((x) => x.date), ...resolved.map((x) => x.date)])).sort();
      const openMap = Object.fromEntries(opened.map((x) => [x.date, x.count]));
      const resMap = Object.fromEntries(resolved.map((x) => [x.date, x.count]));
      const el = document.getElementById("chart-issues");
      if (el && typeof Chart !== "undefined") {
        new Chart(el, {
          type: "line",
          data: {
            labels: dates.length ? dates : ["—"],
            datasets: [
              {
                label: "Issues opened",
                data: dates.length ? dates.map((d) => openMap[d] || 0) : [0],
                borderColor: "#9b2c2c",
                tension: 0.25,
              },
              {
                label: "Issues resolved",
                data: dates.length ? dates.map((d) => resMap[d] || 0) : [0],
                borderColor: "#2f6b3a",
                tension: 0.25,
              },
            ],
          },
          options: {
            responsive: true,
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
          },
        });
      }
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  }

  load();
})();
