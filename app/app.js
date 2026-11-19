// Address lookup: Census Geocoder (JSONP; the API sends no CORS headers) -> 2020 block group
// -> precomputed values in data/{state}.json. Nothing is stored; no other service is called.
"use strict";

const GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress";
const SOURCES = [
  { key: "road", label: "Major roads", color: "var(--road)" },
  { key: "rail", label: "Rail (no subways)", color: "var(--rail)" },
  { key: "aviation", label: "Aircraft", color: "var(--aviation)" },
];
const $ = (id) => document.getElementById(id);
const cache = {};
let meta = null;

function jsonp(url, params, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const cb = "ne_cb_" + Math.random().toString(36).slice(2);
    const q = new URLSearchParams({ ...params, format: "jsonp", callback: cb });
    const s = document.createElement("script");
    const done = () => { delete window[cb]; s.remove(); clearTimeout(t); };
    const t = setTimeout(() => { done(); reject(new Error("timeout")); }, timeoutMs);
    window[cb] = (data) => { done(); resolve(data); };
    s.onerror = () => { done(); reject(new Error("network")); };
    s.src = url + "?" + q.toString();
    document.head.appendChild(s);
  });
}

async function getJSON(path) {
  if (!cache[path]) {
    cache[path] = fetch(path).then((r) => {
      if (!r.ok) throw new Error(path + " " + r.status);
      return r.json();
    });
  }
  return cache[path];
}

async function geocode(address) {
  const res = await jsonp(GEOCODER, {
    address, benchmark: "Public_AR_Current", vintage: "Census2020_Current", layers: "10",
  });
  const m = res && res.result && res.result.addressMatches;
  if (!m || !m.length) return null;
  const blocks = m[0].geographies["Census Blocks"] || [];
  if (!blocks.length) return null;
  return { matched: m[0].matchedAddress, bg: blocks[0].GEOID.slice(0, 12) };
}

const pct = (v) => (v === null || v === undefined ? "–" : v.toFixed(1).replace(/\.0$/, "") + "%");

function row(fields, rec) {
  const o = {};
  fields.forEach((f, i) => (o[f] = rec[i]));
  return o;
}

function render(match, r) {
  const metro = meta.metros[r.metro];
  $("matched").textContent = "Matched: " + match.matched + " · census block group " + match.bg + " · " + metro + " metro";
  const result = $("result");
  if (!r.pop) {
    $("big").textContent = "–";
    $("big-text").textContent = "No residents were counted in this block group in 2020, so there is no neighbourhood estimate.";
    $("rank-marker").style.display = "none";
    $("rank-text").textContent = "";
    $("sources").querySelector("tbody").innerHTML = "";
    $("context").textContent = "";
    result.hidden = false;
    return;
  }
  $("rank-marker").style.display = "";
  $("big").textContent = pct(r.all_55);
  $("big-text").innerHTML = "of residents in this neighbourhood live where modelled road, rail and aircraft noise reaches <strong>55&nbsp;dBA or more</strong>. "
    + pct(r.all_65) + " live at 65&nbsp;dBA or more.";
  $("rank-marker").style.left = Math.max(0, Math.min(100, r.pct)) + "%";
  $("rank-text").textContent = "That is louder than the neighbourhoods of about " + r.pct + "% of " + metro
    + " metro residents. The metro average is " + pct(meta.metro_all_55[metro]) + ".";
  const tb = $("sources").querySelector("tbody");
  tb.innerHTML = "";
  for (const s of SOURCES) {
    const v55 = r[s.key + "_55"], v65 = r[s.key + "_65"];
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><span class="swatch" style="background:${s.color}"></span>${s.label}</td>
      <td><div class="bar"><div class="bar-track"><div class="bar-fill" style="width:${v55 || 0}%;background:${s.color}"></div></div>
      <span class="bar-val">${pct(v55)}</span></div></td><td class="num">${pct(v65)}</td>`;
    tb.appendChild(tr);
  }
  $("context").textContent = r.income
    ? "Median household income in this block group: $" + r.income.toLocaleString() + " (ACS 2018–22)."
    : "No reliable income estimate for this block group.";
  result.hidden = false;
}

async function lookup(ev) {
  ev.preventDefault();
  const address = $("address").value.trim();
  if (!address) return;
  const btn = ev.target.querySelector("button");
  btn.disabled = true;
  $("result").hidden = true;
  $("status").textContent = "Finding your census block group…";
  try {
    meta = meta || (await getJSON("data/meta.json"));
    const match = await geocode(address);
    if (!match) {
      $("status").textContent = "The Census geocoder couldn't match that address. Try adding the city and ZIP code.";
      return;
    }
    const st = match.bg.slice(0, 2);
    if (!meta.states.includes(st)) {
      $("status").textContent = "That address is outside the 20 metro areas this analysis covers.";
      return;
    }
    const data = await getJSON("data/" + st + ".json");
    const rec = data[match.bg];
    if (!rec) {
      $("status").textContent = "That address is outside the 20 metro areas this analysis covers.";
      return;
    }
    $("status").textContent = "";
    render(match, row(meta.fields, rec));
  } catch (e) {
    $("status").textContent = "Something went wrong reaching the Census geocoder. Please try again in a moment.";
  } finally {
    btn.disabled = false;
  }
}

$("lookup").addEventListener("submit", lookup);
