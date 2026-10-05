(() => {
  const app = document.getElementById("import-app");
  if (!app) return;

  const csrfToken = () => {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  };

  let job = null;
  let systemFields = [];
  let systemStatuses = [];
  let systemPhases = [];

  const els = {
    uploadForm: document.getElementById("upload-form"),
    uploadFile: document.getElementById("upload-file"),
    uploadError: document.getElementById("upload-error"),
    sheetSelect: document.getElementById("sheet-select"),
    sheetMeta: document.getElementById("sheet-meta"),
    btnSheet: document.getElementById("btn-select-sheet"),
    columnMapping: document.getElementById("column-mapping"),
    statusMapping: document.getElementById("status-mapping"),
    phaseMapping: document.getElementById("phase-mapping"),
    btnPreview: document.getElementById("btn-preview"),
    btnConfirm: document.getElementById("btn-confirm"),
    previewError: document.getElementById("preview-error"),
    previewCounts: document.getElementById("preview-counts"),
    previewTbody: document.getElementById("preview-tbody"),
    historyTbody: document.getElementById("history-tbody"),
  };

  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
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
    const headers = { "X-CSRFToken": csrfToken(), ...(options.headers || {}) };
    if (options.json) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.json);
      delete options.json;
    }
    const res = await fetch(url, { credentials: "same-origin", ...options, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(parseError(data));
    return data;
  }

  async function loadHistory() {
    try {
      const data = await api("/api/import/");
      if (!data.results.length) {
        els.historyTbody.innerHTML = `<tr><td colspan="9" class="empty-state">No spreadsheet has been imported.</td></tr>`;
        return;
      }
      els.historyTbody.innerHTML = data.results
        .map(
          (j) => `<tr>
            <td>${j.id}</td>
            <td>${escapeHtml(j.original_filename)}</td>
            <td>${escapeHtml(j.uploaded_by || "—")}</td>
            <td>${escapeHtml((j.created_at || "").replace("T", " ").slice(0, 16))}</td>
            <td>${j.total_rows}</td>
            <td>${j.created_count}</td>
            <td>${j.updated_count}</td>
            <td>${j.failed_count}</td>
            <td>${escapeHtml(j.status_label)}</td>
          </tr>`
        )
        .join("");
    } catch (err) {
      els.historyTbody.innerHTML = `<tr><td colspan="9" class="error">${escapeHtml(err.message)}</td></tr>`;
    }
  }

  function populateSheets(analysis) {
    const sheets = (analysis && analysis.sheets) || [];
    els.sheetSelect.innerHTML = sheets.length
      ? sheets.map((s) => `<option value="${escapeHtml(s.name)}">${escapeHtml(s.name)} (${s.row_count} rows)</option>`).join("")
      : `<option value="">No sheets found</option>`;
    els.sheetSelect.disabled = !sheets.length;
    els.btnSheet.disabled = !sheets.length;
    if (sheets.length) {
      els.sheetMeta.textContent = `Detected ${sheets.length} sheet(s).`;
    }
  }

  function renderColumnMapping(jobData) {
    const headers = (jobData.analysis && jobData.analysis.headers) || [];
    systemFields = (jobData.analysis && jobData.analysis.system_fields) || [];
    const mapping = jobData.column_mapping || {};
    if (!headers.length) {
      els.columnMapping.innerHTML = `<span class="muted">Select a sheet to map columns.</span>`;
      return;
    }
    els.columnMapping.innerHTML = systemFields
      .map((f) => {
        const options = [`<option value="">— unmapped —</option>`]
          .concat(
            headers.map(
              (h) =>
                `<option value="${escapeHtml(h)}" ${mapping[f.field] === h ? "selected" : ""}>${escapeHtml(h)}</option>`
            )
          )
          .join("");
        return `<label>${escapeHtml(f.label)}${f.required ? " *" : ""}
          <select data-field="${escapeHtml(f.field)}">${options}</select>
        </label>`;
      })
      .join("");
  }

  function renderStatusMapping(jobData) {
    systemStatuses = (jobData.analysis && jobData.analysis.system_statuses) || [];
    const unique = (jobData.analysis && jobData.analysis.unique_statuses) || [];
    const mapping = jobData.status_mapping || {};
    if (!unique.length) {
      els.statusMapping.innerHTML = `<span class="muted">No status values detected (or status column not mapped yet).</span>`;
      return;
    }
    const statusOpts = systemStatuses
      .map((s) => `<option value="${escapeHtml(s.value)}">${escapeHtml(s.label)}</option>`)
      .join("");
    els.statusMapping.innerHTML = unique
      .map((raw) => {
        const selected = mapping[raw] || "";
        return `<label>Spreadsheet: <code>${escapeHtml(raw)}</code>
          <select data-status-source="${escapeHtml(raw)}">
            <option value="">— not mapped (FAIL) —</option>
            ${systemStatuses
              .map(
                (s) =>
                  `<option value="${escapeHtml(s.value)}" ${selected === s.value ? "selected" : ""}>${escapeHtml(s.label)}</option>`
              )
              .join("")}
          </select>
        </label>`;
      })
      .join("");
  }

  function renderPhaseMapping(jobData) {
    systemPhases = (jobData.analysis && jobData.analysis.system_phases) || [];
    const unique = (jobData.analysis && jobData.analysis.unique_phases) || [];
    const mapping = jobData.phase_mapping || {};
    if (!unique.length) {
      els.phaseMapping.innerHTML = `<span class="muted">No phase values detected.</span>`;
      return;
    }
    els.phaseMapping.innerHTML = unique
      .map((raw) => {
        const selected = mapping[raw] || "";
        return `<label>Spreadsheet: <code>${escapeHtml(raw)}</code>
          <select data-phase-source="${escapeHtml(raw)}">
            <option value="">— not mapped (FAIL) —</option>
            ${systemPhases
              .map(
                (p) =>
                  `<option value="${escapeHtml(p.code)}" ${selected === p.code ? "selected" : ""}>${escapeHtml(p.name)}</option>`
              )
              .join("")}
          </select>
        </label>`;
      })
      .join("");
  }

  function collectMappings() {
    const column_mapping = {};
    els.columnMapping.querySelectorAll("select[data-field]").forEach((sel) => {
      if (sel.value) column_mapping[sel.dataset.field] = sel.value;
    });
    const status_mapping = {};
    els.statusMapping.querySelectorAll("select[data-status-source]").forEach((sel) => {
      if (sel.value) status_mapping[sel.getAttribute("data-status-source")] = sel.value;
    });
    const phase_mapping = {};
    els.phaseMapping.querySelectorAll("select[data-phase-source]").forEach((sel) => {
      if (sel.value) phase_mapping[sel.getAttribute("data-phase-source")] = sel.value;
    });
    return { column_mapping, status_mapping, phase_mapping };
  }

  function renderPreview(jobData) {
    const preview = jobData.preview_summary || {};
    const counts = preview.counts || {};
    els.previewCounts.innerHTML = ["CREATE", "UPDATE", "SKIP", "FAIL"]
      .map(
        (k) =>
          `<div class="kpi-card"><span class="kpi-label">${k}</span><strong>${counts[k] || 0}</strong></div>`
      )
      .join("");

    const rows = preview.rows || [];
    if (!rows.length) {
      els.previewTbody.innerHTML = `<tr><td colspan="5" class="empty-state">No rows to preview.</td></tr>`;
      els.btnConfirm.disabled = true;
      return;
    }
    els.previewTbody.innerHTML = rows
      .map((r) => {
        let detail = "";
        if (r.errors && r.errors.length) detail = r.errors.join("; ");
        else if (r.conflicts && Object.keys(r.conflicts).length) {
          detail = Object.entries(r.conflicts)
            .map(([k, v]) => `${k}: "${v.old}" → "${v.new}"`)
            .join("; ");
        } else detail = "—";
        return `<tr>
          <td>${r.row}</td>
          <td><strong>${escapeHtml(r.external_id || "—")}</strong></td>
          <td><span class="status-pill action-${r.action}">${escapeHtml(r.action)}</span></td>
          <td>${escapeHtml((r.values && r.values.status) || "—")}</td>
          <td class="req-cell">${escapeHtml(detail)}</td>
        </tr>`;
      })
      .join("");

    const canConfirm =
      jobData.status === "PREVIEWED" && !preview.has_failures && (counts.CREATE || counts.UPDATE);
    els.btnConfirm.disabled = !canConfirm;
    if (preview.file_errors && preview.file_errors.length) {
      els.previewError.textContent = preview.file_errors.join(" ");
      els.previewError.hidden = false;
    }
  }

  els.uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    els.uploadError.hidden = true;
    const file = els.uploadFile.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      job = await api("/api/import/excel/", { method: "POST", body: fd });
      populateSheets(job.analysis);
      els.btnPreview.disabled = true;
      els.btnConfirm.disabled = true;
      await loadHistory();
    } catch (err) {
      els.uploadError.textContent = err.message;
      els.uploadError.hidden = false;
    }
  });

  els.btnSheet.addEventListener("click", async () => {
    if (!job) return;
    try {
      job = await api(`/api/import/${job.id}/sheet/`, {
        method: "POST",
        json: { sheet_name: els.sheetSelect.value },
      });
      renderColumnMapping(job);
      renderStatusMapping(job);
      renderPhaseMapping(job);
      els.btnPreview.disabled = false;
      els.sheetMeta.textContent = `Sheet "${job.sheet_name}" · ${job.total_rows} data rows`;
    } catch (err) {
      alert(err.message);
    }
  });

  els.btnPreview.addEventListener("click", async () => {
    if (!job) return;
    els.previewError.hidden = true;
    try {
      const maps = collectMappings();
      job = await api(`/api/import/${job.id}/preview/`, { method: "POST", json: maps });
      renderPreview(job);
      await loadHistory();
    } catch (err) {
      els.previewError.textContent = err.message;
      els.previewError.hidden = false;
    }
  });

  els.btnConfirm.addEventListener("click", async () => {
    if (!job) return;
    if (!confirm("Confirm import? UPDATE rows will overwrite mapped fields as shown in the preview.")) {
      return;
    }
    els.previewError.hidden = true;
    try {
      job = await api(`/api/import/${job.id}/confirm/`, { method: "POST", json: {} });
      els.previewError.hidden = true;
      alert(
        `Import complete. Created ${job.created_count}, updated ${job.updated_count}, skipped ${job.skipped_count}, failed ${job.failed_count}.`
      );
      await loadHistory();
      els.btnConfirm.disabled = true;
    } catch (err) {
      els.previewError.textContent = err.message;
      els.previewError.hidden = false;
    }
  });

  loadHistory();
})();
