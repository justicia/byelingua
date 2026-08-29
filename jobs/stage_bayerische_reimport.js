#!/usr/bin/env node

"use strict";

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const PLAYWRIGHT_PATH = process.env.BYELINGUA_PLAYWRIGHT_PATH || "playwright";
const { chromium } = require(PLAYWRIGHT_PATH);

const BASE_URL = "https://www.staatsoper.de";
const SOURCE = "munich_bayerische_staatsoper";
const OCCURRENCE_RE = /\/stuecke\/([^/?#]+)\/(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})-(\d+)(?:[/?#]|$)/i;
const TEAM_ROLES = new Map([
  ["musikalische leitung", "conductor"],
  ["inszenierung", "stage_director"],
  ["regie", "stage_director"],
  ["nach einer produktion von", "stage_director"],
  ["szenische einrichtung", "stage_director"],
  ["bühne", "set_designer"],
  ["bühnenbild", "set_designer"],
  ["kostüme", "costume_designer"],
  ["bühne und kostüme", "production_designer"],
  ["ausstattung", "production_designer"],
  ["licht", "lighting_designer"],
  ["lichtdesign", "lighting_designer"],
  ["chor", "chorus_master"],
  ["chorleitung", "chorus_master"],
  ["dramaturgie", "dramaturg"],
  ["choreographie", "choreographer"],
  ["choreografie", "choreographer"],
  ["video", "video_designer"],
]);
const ENSEMBLE_ROLES = new Map([
  ["Bayerisches Staatsorchester", "orchestra"],
  ["Bayerischer Staatsopernchor", "choir"],
  ["Kinderchor der Bayerischen Staatsoper", "choir"],
]);

function fetchOfficialHtml(url) {
  const python = process.env.BYELINGUA_PYTHON_PATH || "python";
  const script = [
    "import sys",
    "from urllib.request import Request, urlopen",
    "request = Request(sys.argv[1], headers={",
    "  'User-Agent': 'Mozilla/5.0 (compatible; ByelinguaSeasonIngestion/1.0; +https://github.com/justicia/byelingua)',",
    "  'Accept': 'text/html,application/xhtml+xml',",
    "  'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',",
    "})",
    "with urlopen(request, timeout=60) as response:",
    "  sys.stdout.buffer.write(response.read())",
  ].join("\n");
  return execFileSync(python, ["-c", script, url], { encoding: "utf8", maxBuffer: 20 * 1024 * 1024, timeout: 90000 });
}

function argument(name, fallback = null) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function monthRange(season) {
  const startYear = Number(season.slice(0, 4));
  const months = [];
  for (let offset = 0; offset < 12; offset += 1) {
    const monthIndex = 8 + offset;
    const year = startYear + Math.floor(monthIndex / 12);
    const month = (monthIndex % 12) + 1;
    months.push(`${year}-${String(month).padStart(2, "0")}`);
  }
  return months;
}

function cleanLines(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

function titleFromSlug(slug) {
  return slug
    .split("-")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function parseCalendarLink(link) {
  if (!/\|\s*Nationaltheater(?:\s|[A-ZÄÖÜ]|$)/.test(link.text)) return null;
  const match = link.href.match(OCCURRENCE_RE);
  if (!match) return null;
  const [, slug, date, hour, minute, occurrenceId] = match;
  const typeMatch = link.text.match(/\b(Oper|Ballett|Konzert|Extra|Kind&Co)\s*$/i);
  const typeMap = { oper: "opera", ballett: "ballet", konzert: "concert", extra: "other", "kind&co": "other" };
  return {
    source: SOURCE,
    source_event_id: occurrenceId,
    source_url: link.href,
    occurrence_id: occurrenceId,
    slug,
    title: titleFromSlug(slug),
    date,
    start_time: `${hour}:${minute}`,
    organization: "Bayerische Staatsoper",
    venue: "Nationaltheater",
    city: "Munich",
    country: "Germany",
    timezone: "Europe/Berlin",
    event_type: typeMap[(typeMatch ? typeMatch[1] : "other").toLowerCase()] || "other",
    calendar_text: link.text,
  };
}

function castSlice(lines) {
  const endCandidates = ["KOMMENDE VORSTELLUNGEN", "WEITERE VORSTELLUNGEN", "UPCOMING PERFORMANCES"];
  const end = lines.findIndex((line) => endCandidates.includes(line.toUpperCase()));
  const effectiveEnd = end >= 0 ? end : lines.length;
  let start = -1;
  for (let index = 0; index < effectiveEnd; index += 1) {
    if (["BESETZUNG", "CAST"].includes(lines[index].toUpperCase())) start = index;
  }
  return start >= 0 ? lines.slice(start + 1, effectiveEnd) : [];
}

function normalizedLabel(value) {
  return value.toLocaleLowerCase("de-DE").replace(/\s+/g, " ").trim();
}

function detailHeader(lines, occurrence) {
  const compactDate = `${Number(occurrence.date.slice(8, 10))}.${Number(occurrence.date.slice(5, 7))}.${occurrence.date.slice(2, 4)}`;
  const index = lines.findIndex((line) => line.startsWith(compactDate));
  if (index < 0) return { title: occurrence.title, composer: null };
  let cursor = index + 1;
  while (cursor < lines.length && !lines[cursor].includes("Nationaltheater")) cursor += 1;
  const title = lines[cursor + 1] || occurrence.title;
  const composer = lines[cursor + 2] && !/^(Preise|Oper|Ballett|Konzert|Extra)\b/i.test(lines[cursor + 2]) ? lines[cursor + 2] : null;
  return { title, composer };
}

function parseCredits(lines, occurrence) {
  const credits = [];
  let order = 1;
  for (let index = 0; index < lines.length; index += 1) {
    const label = lines[index];
    const ensembleRole = ENSEMBLE_ROLES.get(label);
    if (ensembleRole) {
      credits.push({
        artist_name: label,
        role: ensembleRole,
        source_role: label,
        credit_kind: "ensemble",
        billing_order: order++,
      });
      continue;
    }
    const artistName = lines[index + 1];
    if (!artistName || ENSEMBLE_ROLES.has(artistName)) continue;
    const teamRole = TEAM_ROLES.get(normalizedLabel(label));
    if (teamRole) {
      credits.push({
        artist_name: artistName,
        role: teamRole,
        source_role: label,
        credit_kind: "artistic_team",
        billing_order: order++,
      });
      index += 1;
      continue;
    }
    if (occurrence.event_type === "opera") {
      credits.push({
        artist_name: artistName,
        role: "performer",
        source_role: label,
        character: label,
        raw_character: label,
        credit_kind: "cast",
        billing_order: order++,
      });
      index += 1;
    }
  }
  return credits;
}

async function discoverCalendar(page, season) {
  const occurrences = [];
  const sourceFailures = [];
  for (const month of monthRange(season)) {
    const url = `${BASE_URL}/spielplan/${month}`;
    try {
      await page.setContent(fetchOfficialHtml(url), { waitUntil: "domcontentloaded", timeout: 60000 });
      const links = await page.locator('a[href*="/stuecke/"]').evaluateAll((nodes) =>
        nodes.map((node) => ({ href: node.href, text: (node.innerText || node.textContent || "").replace(/\s+/g, " ").trim() }))
      );
      for (const link of links) {
        const parsed = parseCalendarLink(link);
        if (parsed && parsed.date.startsWith(month)) occurrences.push(parsed);
      }
    } catch (error) {
      sourceFailures.push({ url, error: String(error) });
    }
  }
  const unique = new Map(occurrences.map((event) => [event.source_url, event]));
  return { occurrences: [...unique.values()].sort((a, b) => `${a.date} ${a.start_time}`.localeCompare(`${b.date} ${b.start_time}`)), sourceFailures };
}

async function inspectOccurrence(context, occurrence) {
  const page = await context.newPage();
  try {
    const response = await page.goto(occurrence.source_url, { waitUntil: "domcontentloaded", timeout: 60000 });
    if (!response || !response.ok()) throw new Error(`HTTP ${response ? response.status() : "no-response"}`);
    await page.waitForTimeout(600);
    const lines = cleanLines(await page.locator("body").innerText());
    const cast = castSlice(lines);
    const header = detailHeader(lines, occurrence);
    const credits = parseCredits(cast, occurrence);
    return {
      ...occurrence,
      ...header,
      detail_status: "ok",
      programme: header.title ? [{ source_title: header.title, composer: header.composer, order: 1 }] : [],
      credits,
      cast_section_lines: cast,
    };
  } catch (error) {
    return { ...occurrence, detail_status: "failed", detail_error: String(error), cast_section_lines: [] };
  } finally {
    await page.close();
  }
}

async function mapLimit(items, limit, mapper) {
  const output = new Array(items.length);
  let cursor = 0;
  async function worker() {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      output[index] = await mapper(items[index], index);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return output;
}

async function main() {
  const season = argument("season", "2026-27");
  const outputDir = path.resolve(argument("output", "artifacts/bayerische-staatsoper-reimport"));
  const requestedLimit = Number(argument("limit", "0"));
  const inspectOnly = process.argv.includes("--inspect");
  const executablePath = process.env.BYELINGUA_CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const browser = await chromium.launch({
    headless: true,
    executablePath,
    args: ["--disable-blink-features=AutomationControlled"],
  });
  try {
    const context = await browser.newContext({
      locale: "de-DE",
      userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
      extraHTTPHeaders: { "Accept-Language": "de-DE,de;q=0.9,en;q=0.8" },
    });
    await context.addInitScript(() => {
      Object.defineProperty(navigator, "webdriver", { get: () => undefined });
    });
    const calendarPage = await context.newPage();
    const discovery = await discoverCalendar(calendarPage, season);
    await calendarPage.close();
    const selected = requestedLimit > 0 ? discovery.occurrences.slice(0, requestedLimit) : discovery.occurrences;
    const events = await mapLimit(selected, 3, (event) => inspectOccurrence(context, event));
    const summary = {
      schema_version: "bayerische-staatsoper-readonly-staging-v1",
      generated_at: new Date().toISOString(),
      season,
      production_writes: 0,
      months_checked: monthRange(season).length,
      official_occurrences: discovery.occurrences.length,
      detail_pages_checked: events.length,
      detail_pages_loaded: events.filter((event) => event.detail_status === "ok").length,
      events_with_cast_section: events.filter((event) => event.cast_section_lines.length > 0).length,
      credits_total: events.reduce((sum, event) => sum + (event.credits || []).length, 0),
      cast_rows: events.reduce((sum, event) => sum + (event.credits || []).filter((credit) => credit.credit_kind === "cast").length, 0),
      team_rows: events.reduce((sum, event) => sum + (event.credits || []).filter((credit) => credit.credit_kind === "artistic_team").length, 0),
      ensemble_rows: events.reduce((sum, event) => sum + (event.credits || []).filter((credit) => credit.credit_kind === "ensemble").length, 0),
      source_failures: discovery.sourceFailures.length + events.filter((event) => event.detail_status !== "ok").length,
    };
    if (inspectOnly) {
      process.stdout.write(`${JSON.stringify({ summary, discovery_failures: discovery.sourceFailures, sample: events[0] || null }, null, 2)}\n`);
      return;
    }
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(path.join(outputDir, "bayerische_reimport_staging.json"), `${JSON.stringify({ summary, events }, null, 2)}\n`, "utf8");
    fs.writeFileSync(path.join(outputDir, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`, "utf8");
    process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

module.exports = { castSlice, detailHeader, parseCalendarLink, parseCredits };

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
}
