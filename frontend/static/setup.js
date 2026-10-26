// Clinic settings: plain textareas in, structured settings out. The server validates everything.
"use strict";

const $ = id => document.getElementById(id);
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const lines = id => $(id).value.split("\n").map(l => l.trim()).filter(Boolean);
const splitOnce = (line, sep) => { const i = line.indexOf(sep); return i < 0 ? [line, ""] : [line.slice(0, i).trim(), line.slice(i + 1).trim()]; };

function fill(s) {
  $("clinic-name").textContent = s.name;
  for (const k of ["name", "city", "address", "landmark"]) $(k).value = s[k] || "";
  $("sessions").value = s.sessions.map(([a, b]) => `${a}-${b}`).join("\n");
  $("slot").value = String(s.slot_min);
  $("closed").replaceChildren(...DAYS.map((d, i) => h("label", {},
    h("input", { type: "checkbox", value: i, checked: s.closed_weekdays.includes(i) }), d.slice(0, 3))));
  $("doctors").value = s.doctors.map(d => `${d.id}: ${d.name}`).join("\n");
  $("services").value = s.services.map(x => `${x.name}: ${x.fee}`).join("\n");
  $("faqs").value = s.faqs.map(f => `${f.q} | ${f.a}`).join("\n");
  $("redflags").value = s.red_flags.join("\n");
  $("emergency").value = s.emergency_instruction;
  $("numbers").value = s.whatsapp_numbers.join("\n");
  for (const r of document.querySelectorAll("input[name=voice]")) r.checked = r.value === s.voice;
  $("leave-who").replaceChildren(h("option", { value: "" }, "Whole clinic (holiday)"),
    ...s.doctors.map(d => h("option", { value: d.id }, d.name)));
}

function collect() {
  return {
    name: $("name").value.trim(), city: $("city").value.trim(),
    address: $("address").value.trim(), landmark: $("landmark").value.trim(),
    sessions: lines("sessions").map(l => l.replace(/\s/g, "").split(/[-–to]+/).slice(0, 2)),
    slot_min: Number($("slot").value),
    closed_weekdays: [...$("closed").querySelectorAll("input:checked")].map(i => Number(i.value)),
    doctors: lines("doctors").map(l => {
      const m = l.match(/^([a-z0-9-]+):\s*(.+)$/);
      return m ? { id: m[1], name: m[2] } : { id: null, name: l };
    }),
    services: lines("services").map(l => { const [name, fee] = splitOnce(l, ":"); return { name, fee: fee || "ask the clinic" }; }),
    faqs: lines("faqs").map(l => { const [q, a] = splitOnce(l, "|"); return { q, a }; }),
    red_flags: lines("redflags"),
    emergency_instruction: $("emergency").value.trim(),
    whatsapp_numbers: lines("numbers"),
    voice: (document.querySelector("input[name=voice]:checked") || {}).value || "female",
  };
}

function showResult(el, ok, text) { el.className = ok ? "result-ok" : "result-err"; el.textContent = text; }

function renderBlocks(blocks) {
  $("leave-list").replaceChildren(...(blocks.length ? blocks.map(b => h("li", {},
    h("span", {}, b.label),
    h("button", { class: "btn small", type: "button", onclick: async () => {
      const r = await api(`/api/setup/blocks/${b.id}`, { method: "DELETE" });
      renderBlocks(r.blocks);
      showResult($("leave-result"), true, `Removed. ${r.agent}`);
    } }, "Remove"))) : [h("li", { class: "muted" }, "No leave or holidays coming up.")]));
}

$("settings").addEventListener("submit", async e => {
  e.preventDefault();
  const out = $("save-result");
  out.className = ""; out.textContent = "Saving…";
  try {
    const r = await api("/api/setup", { method: "PUT", body: collect() });
    fill(r.settings);
    showResult(out, !/failed/i.test(r.agent), r.agent.startsWith("Saved") ? r.agent : `Saved. ${r.agent}`);
  } catch (err) { showResult(out, false, err.message); }
});

$("leave-form").addEventListener("submit", async e => {
  e.preventDefault();
  const out = $("leave-result");
  try {
    const r = await api("/api/setup/blocks", { method: "POST", body: { date: $("leave-date").value, doctor_id: $("leave-who").value || null } });
    renderBlocks(r.blocks);
    showResult(out, true, [r.note, r.agent].filter(Boolean).join(" "));
  } catch (err) { showResult(out, false, err.message); }
});

api("/api/setup").then(r => {
  fill(r.settings);
  renderBlocks(r.blocks);
  $("agent-warning").hidden = r.agentConfigured;
  $("leave-date").min = new Date().toLocaleDateString("en-CA");
}).catch(e => showResult($("save-result"), false, e.message));
