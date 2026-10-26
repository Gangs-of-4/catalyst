// Try-it page: one web call to the clinic's assistant, plus the live register.
"use strict";

const $ = id => document.getElementById(id);
const callBtn = $("call"), statusEl = $("status"), meter = $("meter"), transcript = $("transcript");
const bars = [...meter.children];
let vapi = null, config = null, state = "idle"; // idle | connecting | live

function setStatus(html) { statusEl.innerHTML = html; }

function setState(next) {
  state = next;
  callBtn.classList.toggle("live", next === "live");
  callBtn.classList.toggle("connecting", next === "connecting");
  $("call-label").textContent = next === "idle" ? "Talk to the receptionist" : "End the call";
  callBtn.setAttribute("aria-label", next === "idle" ? "Start the call" : "End the call");
  if (next === "idle") showVolume(0);
}

function showVolume(v) {
  callBtn.style.setProperty("--vol", v.toFixed(2));
  meter.classList.toggle("on", v > 0.02);
  bars.forEach((b, i) => { b.style.height = `${4 + Math.max(0, v * 18 - Math.abs(i - 3) * 2.5)}px`; });
}

function addLine(role, text) {
  const who = role === "assistant" ? "Receptionist" : "You";
  transcript.append(h("p", { class: `line ${role}` }, h("span", { class: "who" }, who), text));
  transcript.scrollTop = transcript.scrollHeight;
}

async function loadConfig() {
  config = await api("/api/public-config");
  $("clinic-name").textContent = config.clinic.name;
  $("clinic-place").textContent = config.clinic.city ? ` · ${config.clinic.city}` : "";
  document.title = `Talk to the receptionist · ${config.clinic.name}`;
  if (config.missing.length) {
    const box = $("setup-missing");
    box.hidden = false;
    box.replaceChildren(
      h("b", {}, "The call isn't set up yet. "),
      "Missing in .env: ", ...config.missing.flatMap((k, i) => [i ? ", " : "", h("code", {}, k)]), ". ",
      "Add VAPI_PUBLIC_KEY from the Vapi dashboard (API Keys), then run ", h("code", {}, "python scripts/setup_vapi.py"),
      " to create the assistant. No restart needed; reload this page.");
    callBtn.disabled = true;
    setStatus("Waiting for setup.");
  }
}

function wire() {
  vapi = new window.Vapi(config.publicKey);
  vapi.on("call-start", () => { setState("live"); setStatus("<b>Connected.</b> Go ahead and speak."); });
  vapi.on("speech-start", () => setStatus("<b>Receptionist is speaking…</b>"));
  vapi.on("speech-end", () => setStatus("<b>Listening…</b>"));
  vapi.on("volume-level", v => showVolume(Math.min(1, v)));
  vapi.on("message", m => {
    if (m && m.type === "transcript" && m.transcriptType === "final" && m.transcript) addLine(m.role, m.transcript);
  });
  vapi.on("call-end", () => { setState("idle"); setStatus("Call ended. Press the button to call again."); refresh(); });
  vapi.on("error", e => {
    console.warn("call error", e);
    setState("idle");
    const msg = (e && (e.errorMsg || e.message || (e.error && e.error.message))) || "Something went wrong.";
    setStatus(`<b>Could not connect.</b> ${String(msg).replace(/[<>&]/g, "")}`);
  });
}

callBtn.addEventListener("click", async () => {
  if (state !== "idle") { setStatus("Ending…"); vapi && vapi.stop(); return; }
  if (!vapi) wire();
  transcript.replaceChildren();
  setState("connecting");
  setStatus("<b>Connecting…</b> allow the microphone if asked.");
  try {
    await vapi.start(config.assistantId);
  } catch (e) {
    setState("idle");
    setStatus(`<b>Could not start the call.</b> ${String(e && e.message || e).replace(/[<>&]/g, "")}`);
  }
});

// ---- the register, polled every 3 s; new bookings are written in ----
const seen = new Set();
let firstLoad = true, lastJSON = "";
async function refresh() {
  const data = await api("/api/register");
  const json = JSON.stringify(data);
  if (json === lastJSON) return; // unchanged: keep the DOM so a write-in animation can finish
  lastJSON = json;
  const fresh = new Set();
  for (const day of data.days) for (const col of day.columns) for (const sl of col.slots) {
    if (sl.booking && !seen.has(sl.booking.id)) { if (!firstLoad) fresh.add(sl.booking.id); seen.add(sl.booking.id); }
  }
  firstLoad = false;
  $("register").replaceChildren(...data.days.map(d => renderLedger(d, { fresh })));
}

loadConfig().then(() => poll(refresh, 3000)).catch(e => setStatus(`Could not load the page: ${e.message}`));
