(() => {
  const app = document.getElementById("users-app");
  if (!app) return;
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

  async function api(url, options = {}) {
    const headers = { "X-CSRFToken": csrf(), ...(options.headers || {}) };
    if (options.json) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.json);
      delete options.json;
    }
    const res = await fetch(url, { credentials: "same-origin", ...options, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const d = data.detail;
      throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.join(" ") : JSON.stringify(d || "Error"));
    }
    return data;
  }

  async function load() {
    const tbody = document.getElementById("users-tbody");
    try {
      const data = await api("/api/users/");
      tbody.innerHTML = data.results
        .map(
          (u) => `<tr data-id="${u.id}">
          <td>${esc(u.name)}</td>
          <td>${esc(u.email)}</td>
          <td>${esc(u.organization || "—")}</td>
          <td>
            <select class="user-role">
              <option value="FORBMAX_ADMIN" ${u.role === "FORBMAX_ADMIN" ? "selected" : ""}>Forbmax Admin</option>
              <option value="FORBMAX_MEMBER" ${u.role === "FORBMAX_MEMBER" ? "selected" : ""}>Forbmax Member</option>
              <option value="NIMAR_USER" ${u.role === "NIMAR_USER" ? "selected" : ""}>NIMAR User</option>
            </select>
          </td>
          <td>${u.is_active ? "Active" : "Inactive"}</td>
          <td>
            <button type="button" class="btn btn-small btn-ghost btn-toggle">${u.is_active ? "Deactivate" : "Activate"}</button>
          </td>
        </tr>`
        )
        .join("");
    } catch (e) {
      document.getElementById("users-error").textContent = e.message;
      document.getElementById("users-error").hidden = false;
    }
  }

  document.getElementById("user-create-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("user-create-error");
    err.hidden = true;
    const fd = new FormData(e.target);
    try {
      await api("/api/users/", {
        method: "POST",
        json: {
          name: fd.get("name"),
          email: fd.get("email"),
          role: fd.get("role"),
          password: fd.get("password"),
        },
      });
      e.target.reset();
      await load();
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    }
  });

  document.getElementById("users-tbody").addEventListener("change", async (e) => {
    const sel = e.target.closest(".user-role");
    if (!sel) return;
    const id = sel.closest("tr").dataset.id;
    try {
      await api(`/api/users/${id}/`, { method: "PATCH", json: { role: sel.value } });
      await load();
    } catch (ex) {
      alert(ex.message);
      await load();
    }
  });

  document.getElementById("users-tbody").addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-toggle");
    if (!btn) return;
    const row = btn.closest("tr");
    const active = btn.textContent.trim() === "Activate";
    try {
      await api(`/api/users/${row.dataset.id}/`, { method: "PATCH", json: { is_active: active } });
      await load();
    } catch (ex) {
      alert(ex.message);
    }
  });

  load();
})();
