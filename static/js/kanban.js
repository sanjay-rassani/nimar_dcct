(() => {
  const app = document.getElementById("kanban-app");
  if (!app) return;
  const isForbmax = app.dataset.isForbmax === "true";
  const csrf = () => {
    const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  };
  const esc = (s) =>
    String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");

  async function load() {
    const board = document.getElementById("kanban-board");
    const err = document.getElementById("kanban-error");
    err.hidden = true;
    try {
      const res = await fetch("/api/kanban/", { credentials: "same-origin" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to load kanban");
      board.innerHTML = data.columns
        .map((col) => {
          const cards = col.cards.length
            ? col.cards
                .map((c) => {
                  const opts = [{ value: c.status, label: col.label }]
                    .concat(c.allowed_next_statuses || [])
                    .filter((o, i, arr) => arr.findIndex((x) => x.value === o.value) === i);
                  const select = isForbmax
                    ? `<select class="kanban-status" data-id="${c.id}">${opts
                        .map((o) => `<option value="${o.value}" ${o.value === c.status ? "selected" : ""}>${esc(o.label)}</option>`)
                        .join("")}</select>`
                    : `<span class="status-pill">${esc(col.label)}</span>`;
                  return `<article class="kanban-card">
                    <div><strong>${esc(c.external_id)}</strong> · ${esc(c.module || "—")}</div>
                    <div class="muted">${esc(c.title || "—")}</div>
                    <div class="kanban-meta">${esc(c.phase || "—")} · Due ${esc(c.due_date || "—")} · Issues ${c.open_issue_count || 0}</div>
                    ${select}
                  </article>`;
                })
                .join("")
            : `<p class="muted">No cards</p>`;
          return `<div class="kanban-col"><h3>${esc(col.label)} <span class="muted">(${col.cards.length})</span></h3>${cards}</div>`;
        })
        .join("");
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  }

  document.getElementById("kanban-board").addEventListener("change", async (e) => {
    const sel = e.target.closest(".kanban-status");
    if (!sel) return;
    try {
      const res = await fetch(`/api/points/${sel.dataset.id}/`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
        body: JSON.stringify({ status: sel.value }),
      });
      const data = await res.json();
      if (!res.ok) {
        const detail = data.detail;
        throw new Error(Array.isArray(detail) ? detail.join(" ") : detail || "Update failed");
      }
      await load();
    } catch (err) {
      alert(err.message);
      await load();
    }
  });

  load();
})();
