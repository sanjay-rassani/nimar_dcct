(() => {
  const app = document.getElementById("metrics-app");
  if (!app) return;

  const escapeHtml = (s) =>
    String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");

  async function get(url) {
    const res = await fetch(url, { credentials: "same-origin" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Request failed");
    return data;
  }

  async function load() {
    const err = document.getElementById("metrics-error");
    err.hidden = true;
    try {
      const [overview, phases, modules, issues, trends] = await Promise.all([
        get("/api/metrics/overview/"),
        get("/api/metrics/phases/"),
        get("/api/metrics/modules/"),
        get("/api/metrics/issues/"),
        get("/api/metrics/trends/"),
      ]);

      document.getElementById("metrics-kpis").innerHTML = [
        ["Total", overview.total],
        ["Closed", overview.closed],
        ["Open", overview.open],
        ["In progress", overview.in_progress],
        ["Completion %", `${overview.completion_pct}%`],
        ["Overdue", overview.overdue],
        ["Open issues", overview.open_issues],
        ["Resolved issues", overview.resolved_issues],
      ]
        .map(
          ([label, value]) =>
            `<div class="kpi-card"><span class="kpi-label">${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`
        )
        .join("");

      document.querySelector("#metrics-phase-table tbody").innerHTML = phases.results.length
        ? phases.results
            .map(
              (p) => `<tr>
            <td>${escapeHtml(p.name)}</td><td>${p.total}</td><td>${p.planned}</td><td>${p.in_progress}</td>
            <td>${p.awaiting_verification}</td><td>${p.rework}</td><td>${p.closed}</td><td>${p.completion_pct}%</td>
          </tr>`
            )
            .join("")
        : `<tr><td colspan="8" class="empty-state">No phase data.</td></tr>`;

      document.querySelector("#metrics-module-table tbody").innerHTML = modules.results.length
        ? modules.results
            .map(
              (m) => `<tr>
            <td>${escapeHtml(m.name)}</td><td>${m.total}</td><td>${m.completed}</td>
            <td>${m.open}</td><td>${m.issues}</td><td>${m.completion_pct}%</td>
          </tr>`
            )
            .join("")
        : `<tr><td colspan="6" class="empty-state">No module data.</td></tr>`;

      document.getElementById("metrics-responsibility").innerHTML = `
        <ul class="focus-list">
          <li>Waiting for Forbmax: <strong>${overview.waiting_for_forbmax}</strong></li>
          <li>Waiting for NIMAR: <strong>${overview.waiting_for_nimar}</strong></li>
          <li>Awaiting verification: <strong>${overview.awaiting_verification}</strong></li>
          <li>Rework: <strong>${overview.rework_requested}</strong></li>
        </ul>`;

      document.getElementById("metrics-time").innerHTML = `
        <ul class="focus-list">
          <li>Avg resolution (h): <strong>${issues.avg_resolution_hours ?? "—"}</strong></li>
          <li>Median resolution (h): <strong>${issues.median_resolution_hours ?? "—"}</strong></li>
          <li>Avg NIMAR response (h): <strong>${issues.avg_nimar_response_hours ?? "—"}</strong></li>
          <li>Oldest open issue: <strong>${issues.oldest_open_issue ? escapeHtml(issues.oldest_open_issue.title) : "—"}</strong></li>
        </ul>`;

      if (typeof Chart !== "undefined") {
        const closed = trends.points_closed_over_time || [];
        new Chart(document.getElementById("metrics-chart-closed"), {
          type: "bar",
          data: {
            labels: closed.map((x) => x.date),
            datasets: [{ label: "Points closed", data: closed.map((x) => x.count), backgroundColor: "#245b8a" }],
          },
          options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
        });
        const opened = trends.issues_opened_over_time || [];
        const resolved = trends.issues_resolved_over_time || [];
        const dates = Array.from(new Set([...opened.map((x) => x.date), ...resolved.map((x) => x.date)])).sort();
        const oMap = Object.fromEntries(opened.map((x) => [x.date, x.count]));
        const rMap = Object.fromEntries(resolved.map((x) => [x.date, x.count]));
        new Chart(document.getElementById("metrics-chart-issues"), {
          type: "line",
          data: {
            labels: dates,
            datasets: [
              { label: "Opened", data: dates.map((d) => oMap[d] || 0), borderColor: "#9b2c2c", tension: 0.25 },
              { label: "Resolved", data: dates.map((d) => rMap[d] || 0), borderColor: "#2f6b3a", tension: 0.25 },
            ],
          },
          options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
        });
      }
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  }

  load();
})();
