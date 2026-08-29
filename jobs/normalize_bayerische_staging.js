#!/usr/bin/env node

"use strict";

const fs = require("fs");
const path = require("path");
const { normalizeEvents } = require("./stage_bayerische_reimport");

const input = process.argv[2];
const output = process.argv[3];
if (!input || !output) {
  throw new Error("usage: normalize_bayerische_staging.js <input.json> <output.json>");
}

const staging = JSON.parse(fs.readFileSync(input, "utf8"));
const events = normalizeEvents(staging.events || []);
const credits = events.flatMap((event) => event.credits || []);
const summary = {
  ...staging.summary,
  production_writes: 0,
  official_occurrences: events.length,
  events_with_programme: events.filter((event) => (event.programme || []).length > 0).length,
  programme_with_composer: events.filter((event) => event.programme?.[0]?.composer).length,
  events_with_credits: events.filter((event) => (event.credits || []).length > 0).length,
  credits_total: credits.length,
  cast_rows: credits.filter((credit) => credit.credit_kind === "cast").length,
  team_rows: credits.filter((credit) => credit.credit_kind === "artistic_team").length,
  ensemble_rows: credits.filter((credit) => credit.credit_kind === "ensemble").length,
};
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, `${JSON.stringify({ ...staging, summary, events }, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
