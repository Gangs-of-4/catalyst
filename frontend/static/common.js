// Small helpers shared by the three pages. No framework, no build step.
"use strict";

const h = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
};

async function api(path, options = {}) {
  const opts = { headers: { "Content-Type": "application/json" }, credentials: "same-origin", ...options };
  if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  const res = await fetch(path, opts);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }
  if (!res.ok) {
    const detail = data && data.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return data;
}

function time12(hhmm) {
  const [hh, mm] = hhmm.split(":").map(Number);
  const suffix = hh < 12 ? "am" : "pm";
  const h12 = hh % 12 || 12;
  return mm ? `${h12}:${String(mm).padStart(2, "0")} ${suffix}` : `${h12} ${suffix}`;
}

const SOURCE_LABEL = { phone: "phone", whatsapp: "WhatsApp", walk_in: "walk-in" };
const BLOCK_LABEL = { leave: "Leave", holiday: "Holiday", late_start: "Not in yet", early_close: "Gone for the day", closed: "Closed" };

// Fill a ledger page: rows are times, columns are doctors. `fresh` marks booking ids to animate in.
function renderLedger(day, { fresh = new Set(), onFree = null, renderEntry = null } = {}) {
  const page = h("section", { class: "ledger", "aria-label": `${day.label || ""} ${day.long || day.date}` },
    h("div", { class: "ledger-title" }, h("b", {}, day.label || day.long), h("span", {}, day.long || day.date)));
  if (day.closed) {
    page.append(h("p", { class: "closed-note" }, "Clinic closed this day."));
    return page;
  }
  const head = h("tr", {}, h("th", { class: "time", scope: "col" }, "Time"),
    day.columns.map(c => h("th", { scope: "col" }, c.doctor.name || c.doctor)));
  const rows = day.columns[0].slots.map((_, i) => {
    const t = day.columns[0].slots[i].time;
    const tr = h("tr", { class: day.columns[0].slots[i].past ? "past" : "" },
      h("td", { class: "time" }, time12(t)));
    for (const col of day.columns) {
      const sl = col.slots[i];
      const td = h("td", { class: sl.state });
      if (sl.state === "booked" || (sl.bookings && sl.bookings.length)) {
        td.append(renderEntry ? renderEntry(sl, col) : entry(sl.booking, fresh));
      } else if (sl.state === "blocked") {
        td.append(BLOCK_LABEL[sl.block] || "Blocked");
      } else if (sl.state === "free" && onFree) {
        td.append(h("span", { class: "add" }, "+ add"));
        td.tabIndex = 0;
        td.setAttribute("role", "button");
        td.setAttribute("aria-label", `Add walk-in at ${time12(t)} with ${col.doctor.name || col.doctor}`);
        td.addEventListener("click", () => onFree(col.doctor, t));
        td.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onFree(col.doctor, t); } });
      }
      tr.append(td);
    }
    return tr;
  });
  page.append(h("table", {}, h("thead", {}, head), h("tbody", {}, rows)));
  return page;
}

function entry(b, fresh) {
  if (!b) return "";
  return h("div", { class: "entry" + (fresh.has(b.id) ? " fresh" : "") },
    h("span", { class: "name" }, b.name),
    h("span", { class: `tag ${b.source}` }, SOURCE_LABEL[b.source] || b.source));
}

// Poll `fn` every `ms`, skipping a tick while `paused()` is true or the tab is hidden.
function poll(fn, ms, paused = () => false) {
  const tick = async () => {
    if (!document.hidden && !paused()) { try { await fn(); } catch (e) { console.warn(e); } }
    setTimeout(tick, ms);
  };
  tick();
}
