(() => {
  const app = document.getElementById("timeline-app");
  if (!app) return;
  const esc = (s) =>
    String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");

  async function load() {
    const board = document.getElementById("timeline-board");
    const err = document.getElementById("timeline-error");
    err.hidden = true;
    try {
      const res = await fetch("/api/timeline/", { credentials: "same-origin" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to load timeline");
      if (!data.phases.length) {
        board.innerHTML = `<p class="empty-state">No phases configured.</p>`;
        return;
      }
      board.innerHTML = data.phases
        .map((p) => {
          const pct = p.completion_pct || 0;
          return `<div class="timeline-row">
            <div class="timeline-label">
              <strong>${esc(p.name)}</strong>
              <div class="muted">${esc(p.start_date || "—")} → ${esc(p.end_date || "—")}</div>
              <div class="muted">${p.closed}/${p.total} closed · ${p.overdue} overdue · ${p.issues} open issues</div>
            </div>
            <div class="timeline-track">
              <div class="timeline-fill" style="width:${pct}%"></div>
              <span>${pct}%</span>
            </div>
          </div>`;
        })
        .join("");
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  }
  load();
})();
