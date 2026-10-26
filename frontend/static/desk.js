// Receptionist desk: day grid per doctor, walk-ins, statuses, inbox, calls. Refreshes every 5 s.
"use strict";

const $ = id => document.getElementById(id);
let current = null;       // YYYY-MM-DD shown
let today = null;
let pending = null;       // {doctor, time} for the walk-in dialog
const dialog = $("walkin");
const busy = () => dialog.open || document.activeElement?.closest?.(".actions");

const STATUS_LABEL = { booked: "Booked", arrived: "Arrived", no_show: "No-show", done: "Done", cancelled: "Cancelled" };
const OUTCOME_LABEL = { booked: "Booked", changed: "Changed", escalated: "Escalated", callback: "Callback", answered: "Answered", hung_up: "Hung up" };
const REASON_LABEL = { unanswered_question: "Question we couldn't answer", staff_request: "Wants to talk to staff", failover: "Agent had a problem", other: "Other", red_flag: "Red flag", grey_zone: "Possibly medical", caller_request: "Asked for a person" };

const fmtPhone = p => (p || "").replace(/^\+91(\d{5})(\d{5})$/, "$1 $2");

function shift(iso, days) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString("en-CA");
}

async function setStatus(id, status, label) {
  if (status === "cancelled" && !confirm(`Cancel this booking? The slot opens again.`)) return;
  try { await api(`/api/desk/bookings/${id}/status`, { method: "POST", body: { status } }); }
  catch (e) { alert(e.message); }
  loadDay();
}

function bookingCard(b) {
  const actions = b.status === "cancelled" ? [] : [
    ["arrived", "Arrived"], ["no_show", "No-show"], ["done", "Done"], ["cancelled", "Cancel"],
  ].filter(([s]) => s !== b.status).map(([s, label]) =>
    h("button", { class: "btn small" + (s === "cancelled" ? " danger" : ""), type: "button",
      onclick: () => setStatus(b.id, s, label) }, label));
  return h("div", {},
    h("div", { class: "entry" },
      h("span", { class: "name" }, b.name),
      h("span", { class: `tag ${b.source}` }, SOURCE_LABEL[b.source] || b.source),
      b.status !== "booked" ? h("span", { class: `status-pill ${b.status}` }, STATUS_LABEL[b.status]) : null),
    b.phone ? h("div", { class: "muted", style: "font-size:.85rem" }, fmtPhone(b.phone)) : null,
    b.reason ? h("div", { class: "muted", style: "font-size:.85rem" }, b.reason) : null,
    actions.length ? h("div", { class: "actions" }, actions) : null);
}

function renderSlot(sl, col) {
  const wrap = h("div", {}, sl.bookings.map(bookingCard));
  if (sl.state === "free") {
    wrap.append(h("button", { class: "btn small", type: "button", onclick: e => { e.stopPropagation(); openWalkIn(col.doctor, sl.time); } }, "+ add"));
  }
  return wrap;
}

async function loadDay() {
  const day = await api(`/api/desk/day?date=${current}`);
  $("date-label").textContent = `${day.label}, ${day.long.replace(/^\w+, /, "")}`;
  $("pick").value = current;
  $("grid").replaceChildren(renderLedger(day, { onFree: openWalkIn, renderEntry: renderSlot }));
  $("stray").replaceChildren(...(day.stray.length ? [h("section", { class: "panel" },
    h("h2", {}, "Other bookings this day"), day.stray.map(bookingCard))] : []));
}

async function loadSide() {
  const [items, calls, stats] = await Promise.all([api("/api/desk/inbox"), api("/api/desk/calls"), api("/api/desk/stats")]);
  $("stats").textContent = stats.sentence;
  $("inbox").replaceChildren(...(items.length ? items.map(inboxItem) : [h("p", { class: "muted" }, "Nothing waiting.")]));
  $("calls").replaceChildren(...(calls.length ? calls.map(callRow) : [h("p", { class: "muted" }, "No calls yet.")]));
}

function inboxItem(it) {
  const kind = it.kind === "escalation" ? "URGENT · needs a doctor" : it.kind === "ops" ? "For our team" : it.urgent ? "URGENT callback" : "Callback";
  const when = new Date(it.created_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
  return h("div", { class: "inbox-item" + (it.urgent ? " urgent" : "") },
    h("div", { class: "row" },
      h("div", {},
        h("div", { class: "kind" }, `${kind} · ${when}`),
        h("div", {}, h("b", {}, it.name || "No name"), it.phone ? ` · ${fmtPhone(it.phone)}` : ""),
        it.reason ? h("div", { class: "muted", style: "font-size:.88rem" }, REASON_LABEL[it.reason] || it.reason) : null,
        it.note ? h("div", {}, it.note) : null),
      h("button", { class: "btn small", style: "white-space:nowrap", type: "button", onclick: async () => {
        await api(`/api/desk/inbox/${it.id}/done`, { method: "POST" }).catch(e => alert(e.message));
        loadSide();
      } }, "Mark done")));
}

function callRow(c) {
  const when = new Date(c.started_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
  return h("div", { class: "call-row" },
    h("div", {}, h("span", { class: "outcome" }, c.outcome ? OUTCOME_LABEL[c.outcome] || c.outcome : "In progress"), ` · ${when}`),
    c.safety_review ? h("div", { class: "flag-safety" }, `Safety review: the agent may have said "${c.safety_hits.join('", "')}"`) : null,
    c.summary ? h("div", { style: "font-size:.9rem" }, c.summary) : null,
    c.transcript ? h("details", {}, h("summary", {}, "Transcript"), h("pre", { class: "transcript-text" }, c.transcript)) : null);
}

function openWalkIn(doctor, time) {
  pending = { doctor, time };
  $("walkin-slot").textContent = `${doctor.name}, ${time12(time)}, ${$("date-label").textContent}`;
  $("walkin-error").textContent = "";
  $("walkin-form").reset();
  dialog.showModal();
  $("w-name").focus();
}

$("walkin-cancel").addEventListener("click", () => dialog.close());
$("walkin-form").addEventListener("submit", async e => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("/api/desk/bookings", { method: "POST", body: {
      doctor_id: pending.doctor.id, date: current, time: pending.time,
      name: f.get("name").trim(), phone: f.get("phone").trim() || null, source: f.get("source") } });
    dialog.close();
    loadDay(); loadSide();
  } catch (err) { $("walkin-error").textContent = err.message; }
});

$("send-summary").addEventListener("click", async () => {
  const out = $("summary-result");
  out.className = ""; out.textContent = "Sending…";
  try {
    const r = await api("/api/desk/summary/send", { method: "POST" });
    out.className = r.sent ? "result-ok" : "result-err";
    out.textContent = r.sent ? `Sent to ${r.sent} number(s).` : r.note;
  } catch (e) { out.className = "result-err"; out.textContent = e.message; }
});

const go = d => { current = d; loadDay(); };
$("prev").addEventListener("click", () => go(shift(current, -1)));
$("next").addEventListener("click", () => go(shift(current, 1)));
$("today").addEventListener("click", () => go(today));
$("pick").addEventListener("change", e => e.target.value && go(e.target.value));

(async () => {
  const meta = await api("/api/staff/meta");
  $("clinic-name").textContent = meta.clinic;
  document.title = `Front desk · ${meta.clinic}`;
  $("auth-warning").hidden = !meta.authOpen;
  today = current = meta.today;
  poll(async () => { await loadDay(); await loadSide(); }, 5000, busy);
})().catch(e => { $("stats").textContent = `Could not load: ${e.message}`; });
