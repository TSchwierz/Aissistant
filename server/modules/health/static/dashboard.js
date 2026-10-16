(() => {
  const rangeBtns = document.querySelectorAll(".range-btn");
  const profileForm = document.getElementById("profile-form");
  const profileStatus = document.getElementById("profile-status");
  const recalcBtn = document.getElementById("recalc-btn");
  const exportLink = document.getElementById("export-link");
  const editDialog = document.getElementById("edit-dialog");
  const editForm = document.getElementById("edit-form");
  const editStatus = document.getElementById("edit-status");
  const editCancel = document.getElementById("edit-cancel");

  let currentRange = "30";
  let charts = { weight: null, fat: null, comp: null };
  let rowsById = new Map();
  let nutrition = null;
  let mealsTimer = null;

  const chartDefaults = {
    responsive: true,
    maintainAspectRatio: true,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: "#8b9aab" } },
    },
    scales: {
      x: {
        ticks: { color: "#8b9aab", maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
        grid: { color: "rgba(46,58,72,0.6)" },
      },
      y: {
        ticks: { color: "#8b9aab" },
        grid: { color: "rgba(46,58,72,0.6)" },
      },
    },
  };

  function fmt(n, digits = 1, suffix = "") {
    if (n === null || n === undefined || Number.isNaN(n)) return "—";
    return `${Number(n).toFixed(digits)}${suffix}`;
  }

  function pair(pct, kg) {
    if ((pct === null || pct === undefined) && (kg === null || kg === undefined)) return "—";
    const left = pct === null || pct === undefined ? "—" : fmt(pct, 1, "%");
    const right = kg === null || kg === undefined ? "—" : fmt(kg, 1, " kg");
    return `${left} · ${right}`;
  }

  function fmtWhen(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /** Convert ISO datetime to value for datetime-local input (local timezone). */
  function toLocalInputValue(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function rangeFrom() {
    if (currentRange === "all") return null;
    const days = Number(currentRange);
    const d = new Date();
    d.setDate(d.getDate() - days);
    return d.toISOString();
  }

  function queryUrl(path) {
    const from = rangeFrom();
    if (!from) return path;
    const u = new URL(path, window.location.origin);
    u.searchParams.set("from", from);
    return u.pathname + u.search;
  }

  async function loadStats() {
    const res = await fetch("/api/stats");
    const s = await res.json();
    const L = s.latest;
    document.getElementById("s-weight").textContent = L ? fmt(L.weight_kg, 2, " kg") : "—";
    document.getElementById("s-bmi").textContent = L ? fmt(L.bmi, 1) : "—";
    document.getElementById("s-fat").textContent = L ? pair(L.body_fat_pct, L.body_fat_kg) : "—";
    document.getElementById("s-muscle").textContent = L ? pair(L.muscle_pct, L.muscle_mass_kg) : "—";
    document.getElementById("s-water").textContent = L ? pair(L.water_pct, L.water_kg) : "—";
    document.getElementById("s-bone").textContent = L ? pair(L.bone_pct, L.bone_mass_kg) : "—";
    document.getElementById("s-bmr").textContent = L && L.bmr != null ? `${Math.round(L.bmr)}` : "—";
    paintNutrition(s, L);
    document.getElementById("s-when").textContent = L ? fmtWhen(L.measured_at) : "—";
    const delta = s.weight_delta_7d;
    document.getElementById("s-delta").textContent =
      delta == null ? "—" : `${delta > 0 ? "+" : ""}${fmt(delta, 2, " kg")}`;
  }

  function lineDataset(label, data, color, yAxisID) {
    return {
      label,
      data,
      borderColor: color,
      backgroundColor: color + "33",
      tension: 0.25,
      pointRadius: 2,
      borderWidth: 2,
      yAxisID,
    };
  }

  function ensureCharts() {
    if (charts.weight) return;
    charts.weight = new Chart(document.getElementById("chart-weight"), {
      type: "line",
      data: { labels: [], datasets: [lineDataset("Weight", [], "#3d9b8f")] },
      options: chartDefaults,
    });
    charts.fat = new Chart(document.getElementById("chart-fat"), {
      type: "line",
      data: { labels: [], datasets: [lineDataset("Body fat %", [], "#d4a056")] },
      options: chartDefaults,
    });
    charts.comp = new Chart(document.getElementById("chart-comp"), {
      type: "line",
      data: {
        labels: [],
        datasets: [
          lineDataset("Muscle kg", [], "#6b9bd4", "y"),
          lineDataset("Water %", [], "#9b7ed4", "y1"),
        ],
      },
      options: {
        ...chartDefaults,
        scales: {
          ...chartDefaults.scales,
          y1: {
            position: "right",
            ticks: { color: "#8b9aab" },
            grid: { drawOnChartArea: false },
          },
        },
      },
    });
  }

  function shortLabel(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  function openEdit(id) {
    const row = rowsById.get(id);
    if (!row) return;
    document.getElementById("edit-id").value = String(row.id);
    document.getElementById("edit-measured-at").value = toLocalInputValue(row.measured_at);
    document.getElementById("edit-weight").value = row.weight_kg;
    document.getElementById("edit-impedance").value =
      row.impedance_ohm != null ? row.impedance_ohm : "";
    editStatus.textContent = "";
    editStatus.className = "status";
    editDialog.showModal();
  }

  async function deleteRow(id) {
    const row = rowsById.get(id);
    const when = row ? fmtWhen(row.measured_at) : `#${id}`;
    if (!confirm(`Delete measurement from ${when}?`)) return;
    try {
      const res = await fetch(`/api/measurements/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await res.text());
      await refreshData();
    } catch (err) {
      alert("Delete failed: " + err.message);
    }
  }

  async function refreshData() {
    ensureCharts();
    exportLink.href = queryUrl("/api/measurements/export.csv");

    const params = new URLSearchParams({ limit: "500" });
    const from = rangeFrom();
    if (from) params.set("from", from);

    const [, measRes] = await Promise.all([
      loadStats(),
      fetch(`/api/measurements?${params}`),
    ]);
    const rows = await measRes.json();
    rowsById = new Map(rows.map((r) => [r.id, r]));

    // Chronological for charts
    const chrono = [...rows].reverse();
    const labels = chrono.map((r) => shortLabel(r.measured_at));

    charts.weight.data.labels = labels;
    charts.weight.data.datasets[0].data = chrono.map((r) => r.weight_kg);
    charts.weight.update();

    charts.fat.data.labels = labels;
    charts.fat.data.datasets[0].data = chrono.map((r) => r.body_fat_pct);
    charts.fat.update();

    charts.comp.data.labels = labels;
    charts.comp.data.datasets[0].data = chrono.map((r) => r.muscle_mass_kg);
    charts.comp.data.datasets[1].data = chrono.map((r) => r.water_pct);
    charts.comp.update();

    const tbody = document.querySelector("#meas-table tbody");
    tbody.innerHTML = rows
      .map(
        (r) => `<tr data-id="${r.id}">
        <td class="row-actions">
          <button type="button" class="btn-icon" data-action="edit" data-id="${r.id}">Edit</button>
          <button type="button" class="btn-icon danger" data-action="delete" data-id="${r.id}">Delete</button>
        </td>
        <td>${fmtWhen(r.measured_at)}</td>
        <td>${fmt(r.weight_kg, 2)}</td>
        <td>${r.impedance_ohm != null ? fmt(r.impedance_ohm, 1) : "—"}</td>
        <td>${fmt(r.bmi, 1)}</td>
        <td>${pair(r.body_fat_pct, r.body_fat_kg)}</td>
        <td>${pair(r.muscle_pct, r.muscle_mass_kg)}</td>
        <td>${pair(r.water_pct, r.water_kg)}</td>
        <td>${pair(r.bone_pct, r.bone_mass_kg)}</td>
        <td>${fmt(r.visceral_fat, 1)}</td>
        <td>${r.bmr != null ? Math.round(r.bmr) : "—"}</td>
        <td>${r.body_age != null ? Math.round(r.body_age) : "—"}</td>
      </tr>`
      )
      .join("");
  }

  document.querySelector("#meas-table tbody").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    if (btn.dataset.action === "edit") openEdit(id);
    if (btn.dataset.action === "delete") deleteRow(id);
  });

  editCancel.addEventListener("click", () => editDialog.close());

  editForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = Number(document.getElementById("edit-id").value);
    const measuredLocal = document.getElementById("edit-measured-at").value;
    const weight = Number(document.getElementById("edit-weight").value);
    const impRaw = document.getElementById("edit-impedance").value.trim();
    const body = {
      measured_at: new Date(measuredLocal).toISOString(),
      weight_kg: weight,
      impedance_ohm: impRaw === "" ? null : Number(impRaw),
    };
    editStatus.textContent = "Saving…";
    editStatus.className = "status";
    try {
      const res = await fetch(`/api/measurements/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      editDialog.close();
      await refreshData();
    } catch (err) {
      editStatus.textContent = "Save failed: " + err.message;
      editStatus.className = "status err";
    }
  });

  rangeBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      rangeBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentRange = btn.dataset.range;
      refreshData().catch(console.error);
    });
  });

  function profileBody() {
    const fd = new FormData(profileForm);
    const fat = String(fd.get("target_fat_pct") || "").trim();
    const meals = Number(document.getElementById("meals-per-day").value);
    return {
      name: fd.get("name") || "",
      height_cm: fd.get("height_cm") ? Number(fd.get("height_cm")) : null,
      age: fd.get("age") ? Number(fd.get("age")) : null,
      sex: fd.get("sex") || null,
      activity_level: fd.get("activity_level") || "moderate",
      target_fat_pct: fat ? Number(fat) : null,
      meals_per_day: Number.isFinite(meals) ? meals : 3,
    };
  }

  function paintMealLine() {
    const meals = Number(document.getElementById("meals-per-day").value) || 1;
    document.getElementById("meals-label").textContent = String(meals);
    const line = document.getElementById("n-meal");
    if (!nutrition || nutrition.target_calories == null) {
      line.textContent = "Each meal: —";
      return;
    }
    const cal = Math.round(nutrition.target_calories / meals);
    const protein =
      nutrition.protein_g == null ? "—" : `${(nutrition.protein_g / meals).toFixed(1)} g protein`;
    const fiber =
      nutrition.fiber_g == null ? "—" : `${(nutrition.fiber_g / meals).toFixed(1)} g fiber`;
    line.textContent = `Each meal: ${cal} kcal · ${protein} · ${fiber}`;
  }

  function paintNutrition(stats, latest) {
    nutrition = stats.nutrition || null;
    const basis = document.getElementById("n-basis");
    const n = nutrition;
    if (!n) {
      basis.textContent = "Set an activity level to calculate a daily calorie target from BMR.";
      return;
    }
    const level = String(n.activity_level || "moderate").replace(/_/g, " ");
    basis.textContent = n.bmr
      ? `Target calories = BMR ${Math.round(n.bmr)} × ${n.activity_factor} (${level}). Protein follows your latest weight. Fiber is 14 g per 1,000 kcal.`
      : "A measurement with BMR is needed before calories, protein, and fiber can be calculated.";
    document.getElementById("n-cal").textContent =
      n.target_calories != null ? `${n.target_calories} kcal` : "—";
    document.getElementById("n-protein").textContent =
      n.protein_g != null ? `${n.protein_g} g` : "—";
    document.getElementById("n-fiber").textContent = n.fiber_g != null ? `${n.fiber_g} g` : "—";
    const goal = n.target_fat_pct;
    const current = latest && latest.body_fat_pct;
    document.getElementById("n-fat").textContent =
      goal == null
        ? "—"
        : current == null
          ? fmt(goal, 1, "%")
          : `${fmt(current, 1, "%")} now · ${fmt(goal, 1, "%")} goal`;
    const slider = document.getElementById("meals-per-day");
    if (document.activeElement !== slider && n.meals_per_day) {
      slider.value = String(n.meals_per_day);
    }
    paintMealLine();
  }

  async function saveProfile(announce) {
    if (announce) {
      profileStatus.textContent = "Saving…";
      profileStatus.className = "status";
    }
    try {
      const res = await fetch("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profileBody()),
      });
      if (!res.ok) throw new Error(await res.text());
      const p = await res.json();
      if (announce) {
        profileStatus.textContent = p.is_complete
          ? "Profile saved. Recalculating metrics…"
          : "Profile saved (incomplete — body fat needs height, age, sex).";
        profileStatus.className = "status ok";
      }
      if (p.is_complete) {
        await fetch("/api/measurements/recalculate", { method: "POST" });
        if (announce) profileStatus.textContent = "Profile saved and metrics recalculated.";
        const banner = document.getElementById("profile-banner");
        if (banner) banner.remove();
      }
      await refreshData();
    } catch (err) {
      profileStatus.textContent = "Save failed: " + err.message;
      profileStatus.className = "status err";
    }
  }

  profileForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    await saveProfile(true);
  });

  document.getElementById("meals-per-day").addEventListener("input", () => {
    paintMealLine();
    clearTimeout(mealsTimer);
    mealsTimer = setTimeout(() => saveProfile(false), 400);
  });

  recalcBtn.addEventListener("click", async () => {
    profileStatus.textContent = "Recalculating…";
    profileStatus.className = "status";
    try {
      const res = await fetch("/api/measurements/recalculate", { method: "POST" });
      const data = await res.json();
      profileStatus.textContent = `Recalculated ${data.recalculated} measurement(s).`;
      profileStatus.className = "status ok";
      await refreshData();
    } catch (err) {
      profileStatus.textContent = "Recalc failed: " + err.message;
      profileStatus.className = "status err";
    }
  });

  refreshData().catch(console.error);
  setInterval(() => refreshData().catch(console.error), 30000);
})();
