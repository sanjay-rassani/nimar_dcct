(() => {
  const app = document.getElementById("points-app");
  if (!app) return;

  const writable = new Set(window.DCCT_WRITABLE || []);
  const isNimar = app.dataset.isNimar === "true";
  const isForbmax = app.dataset.isForbmax === "true";

  const csrfToken = () => {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  };

  let state = { page: 1, currentId: null, point: null, owners: [] };

  const els = {
    tbody: document.getElementById("points-tbody"),
    count: document.getElementById("result-count"),
    pagination: document.getElementById("pagination-bar"),
    drawer: document.getElementById("point-drawer"),
    backdrop: document.getElementById("drawer-backdrop"),
    form: document.getElementById("drawer-form"),
    error: document.getElementById("drawer-error"),
    activity: document.getElementById("activity-list"),
    issuesList: document.getElementById("issues-list"),
    issueForm: document.getElementById("issue-create-form"),
    issueError: document.getElementById("issue-create-error"),
    evidenceList: document.getElementById("evidence-list"),
    evidenceForm: document.getElementById("evidence-create-form"),
    evidenceError: document.getElementById("evidence-create-error"),
    pointComments: document.getElementById("point-comments-list"),
    pointCommentForm: document.getElementById("point-comment-form"),
    createDialog: document.getElementById("create-dialog"),
    createForm: document.getElementById("create-form"),
    createError: document.getElementById("create-error"),
  };

  function filters() {
    return {
      q: document.getElementById("filter-q").value.trim(),
      phase: document.getElementById("filter-phase").value,
      module: document.getElementById("filter-module").value,
      status: document.getElementById("filter-status").value,
      annexure: document.getElementById("filter-annexure").value.trim(),
      issue_status: document.getElementById("filter-issue-status").value,
      owner: document.getElementById("filter-owner").value,
      due_from: document.getElementById("filter-due-from").value,
      due_to: document.getElementById("filter-due-to").value,
      sort: document.getElementById("sort-field").value,
      dir: document.getElementById("sort-dir").value,
      page: state.page,
      page_size: 25,
    };
  }

  function toQuery(params) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v).length) q.set(k, v);
    });
    return q.toString();
  }

  function parseError(data) {
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.join(" ");
    if (detail && typeof detail === "object") {
      return Object.entries(detail)
        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`)
        .join(" ");
    }
    return "Request failed.";
  }

  async function api(url, options = {}) {
    const opts = {
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
        ...(options.headers || {}),
      },
      ...options,
    };
    const res = await fetch(url, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(parseError(data));
      err.status = res.status;
      throw err;
    }
    return data;
  }

  async function apiForm(url, formData, method = "POST") {
    const res = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken() },
      body: formData,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(parseError(data));
    return data;
  }

  function formatDate(value) {
    if (!value) return "—";
    return value.slice(0, 10);
  }

  function formatDateTime(value) {
    if (!value) return "—";
    return value.replace("T", " ").slice(0, 16);
  }

  function truncate(text, n = 80) {
    const s = (text || "").trim();
    if (!s) return "—";
    return s.length > n ? `${s.slice(0, n)}…` : s;
  }

  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  async function loadSummary() {
    try {
      const s = await api("/api/register/summary/");
      document.getElementById("kpi-total").textContent = s.total_points;
      document.getElementById("kpi-closed").textContent = s.closed_points;
      document.getElementById("kpi-open-issues").textContent = s.open_issues;
      document.getElementById("kpi-overdue").textContent = s.overdue_points;
      document.querySelectorAll(".nimar-only").forEach((el) => {
        el.hidden = s.view !== "nimar";
      });
      document.querySelectorAll(".forbmax-only").forEach((el) => {
        el.hidden = s.view !== "forbmax";
      });
      if (s.view === "nimar") {
        document.getElementById("kpi-nimar-review").textContent = s.needs_nimar_review;
      } else {
        document.getElementById("kpi-in-progress").textContent = s.in_progress;
        document.getElementById("kpi-client-pending").textContent = s.client_pending;
      }
    } catch (_) {
      /* non-blocking */
    }
  }

  async function loadPoints() {
    els.tbody.innerHTML = `<tr><td colspan="9" class="muted">Loading…</td></tr>`;
    try {
      const data = await api(`/api/points/?${toQuery(filters())}`);
      els.count.textContent = `${data.count} point${data.count === 1 ? "" : "s"}`;
      if (!data.results.length) {
        els.tbody.innerHTML = `<tr><td colspan="9" class="empty-state">No points match the selected filters.</td></tr>`;
      } else {
        els.tbody.innerHTML = data.results
          .map(
            (p) => `
          <tr data-id="${p.id}" tabindex="0">
            <td><strong>${escapeHtml(p.external_id)}</strong></td>
            <td>${escapeHtml(p.module || "—")}</td>
            <td class="req-cell">${escapeHtml(truncate(p.title || p.requirement))}</td>
            <td>${escapeHtml(p.phase || "—")}</td>
            <td><span class="status-pill">${escapeHtml(p.status_label)}</span></td>
            <td>${escapeHtml(p.owner || "—")}</td>
            <td>${formatDate(p.due_date)}</td>
            <td>${p.open_issue_count ? `<span class="issue-badge">${p.open_issue_count}</span>` : "—"}</td>
            <td>${formatDateTime(p.updated_at)}</td>
          </tr>`
          )
          .join("");
      }
      renderPagination(data);
      loadSummary();
    } catch (err) {
      els.tbody.innerHTML = `<tr><td colspan="9" class="error">${escapeHtml(err.message)}</td></tr>`;
    }
  }

  function renderPagination(data) {
    if (data.num_pages <= 1) {
      els.pagination.innerHTML = "";
      return;
    }
    els.pagination.innerHTML = `
      <button type="button" class="btn btn-small btn-ghost" data-page="${data.page - 1}" ${data.page <= 1 ? "disabled" : ""}>Prev</button>
      <span class="muted">Page ${data.page} of ${data.num_pages}</span>
      <button type="button" class="btn btn-small btn-ghost" data-page="${data.page + 1}" ${data.page >= data.num_pages ? "disabled" : ""}>Next</button>
    `;
  }

  function renderComments(comments) {
    els.pointComments.innerHTML = (comments || []).length
      ? comments
          .map(
            (c) => `<li><div class="comment-head"><strong>${escapeHtml(c.author)}</strong> · ${formatDateTime(c.created_at)}</div><div>${escapeHtml(c.message)}</div></li>`
          )
          .join("")
      : `<li class="muted">No comments yet.</li>`;
  }

  function renderEvidence(items) {
    els.evidenceList.innerHTML = (items || []).length
      ? items
          .map(
            (a) => `<li>
              <div><strong>${escapeHtml(a.label)}</strong> · ${escapeHtml(a.attachment_type)} · ${escapeHtml(a.uploaded_by || "")}</div>
              ${a.url ? `<a href="${escapeHtml(a.url)}" target="_blank" rel="noopener">${escapeHtml(a.url)}</a>` : `<span class="muted">—</span>`}
            </li>`
          )
          .join("")
      : `<li class="muted">No evidence attached yet.</li>`;
  }

  function issueStatusOptions(issue) {
    const opts = [{ value: issue.status, label: issue.status_label }];
    (issue.allowed_next_statuses || []).forEach((o) => opts.push(o));
    const seen = new Set();
    return opts.filter((o) => {
      if (seen.has(o.value)) return false;
      seen.add(o.value);
      return true;
    });
  }

  function renderIssues(issues) {
    if (!issues || !issues.length) {
      els.issuesList.innerHTML = `<p class="muted empty-state">No issues yet.</p>`;
      return;
    }
    els.issuesList.innerHTML = issues
      .map((issue) => {
        const statusSelect =
          isForbmax || (isNimar && issue.status === "RESOLVED")
            ? `<select class="issue-status-select" data-issue-id="${issue.id}">
              ${issueStatusOptions(issue)
                .map((o) => `<option value="${o.value}">${escapeHtml(o.label)}</option>`)
                .join("")}
            </select>`
          : `<span class="status-pill">${escapeHtml(issue.status_label)}</span>`;
        const assignSelect = isForbmax
          ? `<select class="issue-assign-select" data-issue-id="${issue.id}">
              <option value="">Unassigned</option>
              ${state.owners.map((o) => `<option value="${o.id}" ${issue.assigned_to_id === o.id ? "selected" : ""}>${escapeHtml(o.name)}</option>`).join("")}
            </select>`
          : `<span>${escapeHtml(issue.assigned_to || "—")}</span>`;
        return `<article class="issue-card" data-issue-id="${issue.id}">
          <div class="issue-head"><strong>#${issue.id}</strong> ${escapeHtml(issue.title)}</div>
          <div class="muted">${escapeHtml(issue.description || "")}</div>
          <div class="issue-meta">Raised by ${escapeHtml(issue.raised_by || "—")} · ${formatDateTime(issue.created_at)}</div>
          <div class="issue-actions">
            <label>Status ${statusSelect}</label>
            <label>Assigned ${assignSelect}</label>
          </div>
          <form class="issue-comment-form stack-tight" data-issue-id="${issue.id}">
            <textarea name="message" rows="2" placeholder="Comment on this issue" required></textarea>
            <button type="submit" class="btn btn-small btn-ghost">Comment</button>
          </form>
          <ul class="comment-list compact">${(issue.comments || [])
            .map(
              (c) => `<li><strong>${escapeHtml(c.author)}</strong> · ${formatDateTime(c.created_at)} — ${escapeHtml(c.message)}</li>`
            )
            .join("")}</ul>
        </article>`;
      })
      .join("");
  }

  function renderActivity(activity) {
    els.activity.innerHTML = (activity || []).length
      ? activity
          .map(
            (a) => `<li>
              <div class="activity-head"><strong>${escapeHtml(a.action)}</strong> · ${escapeHtml(a.actor || "system")} · ${formatDateTime(a.created_at)}</div>
              <div class="muted">${escapeHtml(a.message || "")}</div>
            </li>`
          )
          .join("")
      : `<li class="muted">No activity recorded yet.</li>`;
  }

  function applyFieldPermissions() {
    const map = [
      ["field-status", "status"],
      ["field-scope-approved", "scope_approved"],
      ["field-requirement", "requirement"],
      ["field-forbmax-response", "forbmax_response"],
      ["field-nimar-response", "nimar_response"],
      ["field-decision", "decision"],
      ["field-remarks", "remarks"],
      ["field-owner", "owner_id"],
      ["field-due-date", "due_date"],
      ["field-phase", "phase_id"],
      ["field-module", "module_id"],
    ];
    map.forEach(([id, key]) => {
      const el = document.getElementById(id);
      if (el) el.disabled = !writable.has(key);
    });
    document.getElementById("drawer-save").hidden = writable.size === 0;
  }

  async function openDrawer(id) {
    state.currentId = id;
    els.error.hidden = true;
    const point = await api(`/api/points/${id}/`);
    state.point = point;

    document.getElementById("drawer-external-id").textContent = point.external_id;
    document.getElementById("drawer-meta").textContent = [
      point.module || "No module",
      point.phase || "No phase",
      point.status_label,
    ].join(" · ");

    const statusSelect = document.getElementById("field-status");
    const options = [{ value: point.status, label: point.status_label }].concat(point.allowed_next_statuses || []);
    const seen = new Set();
    statusSelect.innerHTML = options
      .filter((o) => !seen.has(o.value) && seen.add(o.value))
      .map((o) => `<option value="${o.value}">${escapeHtml(o.label)}</option>`)
      .join("");
    statusSelect.value = point.status;

    document.getElementById("field-scope-approved").checked = !!point.scope_approved;
    document.getElementById("field-requirement").value = point.requirement || "";
    document.getElementById("field-forbmax-response").value = point.forbmax_response || "";
    document.getElementById("field-nimar-response").value = point.nimar_response || "";
    document.getElementById("field-decision").value = point.decision || "";
    document.getElementById("field-remarks").value = point.remarks || "";
    document.getElementById("field-owner").value = point.owner_id || "";
    document.getElementById("field-due-date").value = point.due_date || "";
    document.getElementById("field-phase").value = point.phase_id || "";
    document.getElementById("field-module").value = point.module_id || "";

    renderComments(point.comments);
    renderIssues(point.issues);
    renderEvidence(point.attachments);
    renderActivity(point.activity);

    applyFieldPermissions();
    els.drawer.classList.add("open");
    els.drawer.setAttribute("aria-hidden", "false");
    els.backdrop.hidden = false;
  }

  function closeDrawer() {
    els.drawer.classList.remove("open");
    els.drawer.setAttribute("aria-hidden", "true");
    els.backdrop.hidden = true;
    state.currentId = null;
  }

  async function refreshDrawer() {
    if (state.currentId) await openDrawer(state.currentId);
  }

  els.tbody.addEventListener("click", (e) => {
    const row = e.target.closest("tr[data-id]");
    if (row) openDrawer(row.dataset.id).catch((err) => alert(err.message));
  });

  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  els.backdrop.addEventListener("click", closeDrawer);

  document.querySelectorAll(".drawer-tabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".drawer-tabs .tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.hidden = panel.dataset.panel !== tab.dataset.tab;
      });
    });
  });

  document.getElementById("btn-apply-filters").addEventListener("click", () => {
    state.page = 1;
    loadPoints();
  });
  document.getElementById("btn-reset-filters").addEventListener("click", () => {
    ["filter-q", "filter-annexure", "filter-due-from", "filter-due-to"].forEach((id) => {
      document.getElementById(id).value = "";
    });
    ["filter-phase", "filter-module", "filter-status", "filter-issue-status", "filter-owner"].forEach((id) => {
      document.getElementById(id).value = "";
    });
    state.page = 1;
    loadPoints();
  });
  ["sort-field", "sort-dir"].forEach((id) => {
    document.getElementById(id).addEventListener("change", () => {
      state.page = 1;
      loadPoints();
    });
  });
  els.pagination.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-page]");
    if (!btn || btn.disabled) return;
    state.page = Number(btn.dataset.page);
    loadPoints();
  });

  els.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.currentId) return;
    els.error.hidden = true;
    const payload = {};
    if (writable.has("status")) payload.status = document.getElementById("field-status").value;
    if (writable.has("scope_approved")) payload.scope_approved = document.getElementById("field-scope-approved").checked;
    if (writable.has("requirement")) payload.requirement = document.getElementById("field-requirement").value;
    if (writable.has("forbmax_response")) payload.forbmax_response = document.getElementById("field-forbmax-response").value;
    if (writable.has("nimar_response")) payload.nimar_response = document.getElementById("field-nimar-response").value;
    if (writable.has("decision")) payload.decision = document.getElementById("field-decision").value;
    if (writable.has("remarks")) payload.remarks = document.getElementById("field-remarks").value;
    if (writable.has("owner_id")) {
      const v = document.getElementById("field-owner").value;
      payload.owner = v ? Number(v) : null;
    }
    if (writable.has("due_date")) payload.due_date = document.getElementById("field-due-date").value || null;
    if (writable.has("phase_id")) {
      const v = document.getElementById("field-phase").value;
      payload.phase = v ? Number(v) : null;
    }
    if (writable.has("module_id")) {
      const v = document.getElementById("field-module").value;
      payload.module = v ? Number(v) : null;
    }
    try {
      await api(`/api/points/${state.currentId}/`, { method: "PATCH", body: JSON.stringify(payload) });
      await refreshDrawer();
      await loadPoints();
    } catch (err) {
      els.error.textContent = err.message;
      els.error.hidden = false;
    }
  });

  els.pointCommentForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.currentId) return;
    const fd = new FormData(els.pointCommentForm);
    try {
      await api(`/api/points/${state.currentId}/comments/`, {
        method: "POST",
        body: JSON.stringify({ message: fd.get("message") }),
      });
      els.pointCommentForm.reset();
      await refreshDrawer();
    } catch (err) {
      alert(err.message);
    }
  });

  els.issueForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.currentId) return;
    els.issueError.hidden = true;
    const fd = new FormData(els.issueForm);
    try {
      const issue = await api("/api/issues/", {
        method: "POST",
        body: JSON.stringify({
          point_id: Number(state.currentId),
          title: fd.get("title"),
          description: fd.get("description"),
        }),
      });
      const label = fd.get("evidence_label");
      const url = fd.get("evidence_url");
      const file = fd.get("evidence_file");
      if (label && (url || (file && file.name))) {
        const att = new FormData();
        att.append("label", label);
        att.append("attachment_type", "VERIFICATION");
        if (url) att.append("url", url);
        if (file && file.name) att.append("file", file);
        await apiForm(`/api/issues/${issue.id}/attachments/`, att);
      }
      els.issueForm.reset();
      await refreshDrawer();
      await loadPoints();
    } catch (err) {
      els.issueError.textContent = err.message;
      els.issueError.hidden = false;
    }
  });

  els.evidenceForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.currentId) return;
    els.evidenceError.hidden = true;
    const fd = new FormData(els.evidenceForm);
    try {
      await apiForm(`/api/points/${state.currentId}/attachments/`, fd);
      els.evidenceForm.reset();
      await refreshDrawer();
    } catch (err) {
      els.evidenceError.textContent = err.message;
      els.evidenceError.hidden = false;
    }
  });

  els.issuesList.addEventListener("change", async (e) => {
    const statusSel = e.target.closest(".issue-status-select");
    if (statusSel) {
      try {
        await api(`/api/issues/${statusSel.dataset.issueId}/`, {
          method: "PATCH",
          body: JSON.stringify({ status: statusSel.value }),
        });
        await refreshDrawer();
        await loadPoints();
      } catch (err) {
        alert(err.message);
        await refreshDrawer();
      }
      return;
    }
    const assignSel = e.target.closest(".issue-assign-select");
    if (assignSel) {
      try {
        await api(`/api/issues/${assignSel.dataset.issueId}/`, {
          method: "PATCH",
          body: JSON.stringify({ assigned_to: assignSel.value ? Number(assignSel.value) : null }),
        });
        await refreshDrawer();
      } catch (err) {
        alert(err.message);
        await refreshDrawer();
      }
    }
  });

  els.issuesList.addEventListener("submit", async (e) => {
    const form = e.target.closest(".issue-comment-form");
    if (!form) return;
    e.preventDefault();
    const fd = new FormData(form);
    try {
      await api(`/api/issues/${form.dataset.issueId}/comments/`, {
        method: "POST",
        body: JSON.stringify({ message: fd.get("message") }),
      });
      form.reset();
      await refreshDrawer();
    } catch (err) {
      alert(err.message);
    }
  });

  const createBtn = document.getElementById("btn-create-point");
  if (createBtn && els.createDialog) {
    createBtn.addEventListener("click", () => {
      els.createError.hidden = true;
      els.createDialog.showModal();
    });
    els.createForm.addEventListener("submit", async (e) => {
      if (e.submitter && e.submitter.value === "cancel") return;
      e.preventDefault();
      const fd = new FormData(els.createForm);
      try {
        const created = await api("/api/points/", {
          method: "POST",
          body: JSON.stringify({
            external_id: fd.get("external_id"),
            title: fd.get("title"),
            requirement: fd.get("requirement"),
            phase: fd.get("phase") ? Number(fd.get("phase")) : null,
            module: fd.get("module") ? Number(fd.get("module")) : null,
          }),
        });
        els.createDialog.close();
        els.createForm.reset();
        await loadPoints();
        await openDrawer(created.id);
      } catch (err) {
        els.createError.textContent = err.message;
        els.createError.hidden = false;
      }
    });
  }

  api("/api/owners/")
    .then((data) => {
      state.owners = data.results || [];
    })
    .catch(() => {});

  const exportBtn = document.getElementById("btn-export-filtered");
  if (exportBtn) {
    exportBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const params = filters();
      delete params.page;
      delete params.page_size;
      window.location.href = `/api/export/excel/?${toQuery(params)}`;
    });
  }

  applyFieldPermissions();
  loadSummary();
  loadPoints();
})();
