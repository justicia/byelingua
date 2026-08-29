#!/usr/bin/env node

"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const SOURCE = "munich_bayerische_staatsoper";
const BRETT_DEAN_ID = "58eca23f-8249-45c8-b35d-18ba60242924";

const EXISTING_WORK_IDS = {
  "ariadne-auf-naxos": "38ac1e96-7b0d-4601-9338-f69022c0dc0f",
  carmen: "e7484cde-f5e2-4718-985d-ccf5bc5d0428",
  "das-rheingold": "c2bab1a9-16e2-421e-8ef4-b312a2accb57",
  "der-fliegende-hollaender": "b37e7330-a724-4f70-adc8-6bb25f19f700",
  "der-rosenkavalier": "72413b78-c83c-4131-ac0c-d2452ae71131",
  "die-entfuehrung-aus-dem-serail": "6b0a1285-f351-4459-aa47-18821fca3551",
  "die-fledermaus": "93072805-d1ae-472c-a7c9-3a2237962b97",
  "die-walkuere": "59101410-97f9-42ad-9b89-f7cab20eaf63",
  "die-zauberfloete": "a4333e3e-56c3-46ae-9910-d62f4e838ca1",
  "doctor-atomic": "a3a7935a-1e43-4d48-931a-a92fc53533c7",
  "don-giovanni": "bcafbec4-3252-4856-a10c-557fef25c529",
  goetterdaemmerung: "46141d16-fb84-4634-ad82-432ea815566b",
  idomeneo: "852d9462-99a5-48a3-95e1-7914a1540031",
  "il-barbiere-di-siviglia": "98b6ff5a-9462-4359-9183-6991ed83ef7f",
  "la-boheme": "5fc01cf2-8e65-4536-9d94-1fc59fa630e1",
  "la-traviata": "ae7c773a-8caf-4854-8a21-49b396647378",
  "lelisir-damore": "184e5141-64ff-47df-b222-86104fae4ff5",
  macbeth: "7f552f18-d0bf-4ad7-bb2c-812ae1e05821",
  "madama-butterfly": "2746a542-69dc-4047-856d-6f2162bdcd46",
  "manon-lescaut": "3e854127-e1f0-48e0-848d-45ed3f8d80b9",
  parsifal: "bc9d6a6f-6ad0-417a-a64c-d3813c56030e",
  siegfried: "c7b6cef4-fe70-48a8-a7a2-710058c2861f",
  tannhaeuser: "8a8d9b81-329e-45c9-9ac7-3665898bd139",
  tosca: "c4551c69-40aa-41d6-8d8b-8f4caa9b372f",
  "un-ballo-in-maschera": "73e51cd4-2d41-44ea-868a-c0b8fa3dcee1",
  werther: "34151afa-505c-4f03-b190-9774d6b81630",
};

const NEW_WORKS = {
  "die-nacht-vor-weihnachten": ["Die Nacht vor Weihnachten", "Nikolai Rimsky-Korsakov", "da3c5b27-e804-41ad-8165-59cd4cc01223"],
  faust: ["Faust", "Charles Gounod", "c0f523a8-6792-41b4-9f9e-01f3af470caa"],
  "katja-kabanova": ["Káťa Kabanová", "Leoš Janáček", "01b5135b-0613-4a5e-9cff-d32fa11364b6"],
  "la-cenerentola": ["La Cenerentola", "Gioachino Rossini", "c694a27d-d9b4-4d26-86fa-414e6b17554f"],
  "lucrezia-borgia": ["Lucrezia Borgia", "Gaetano Donizetti", "2dac964d-5543-45ca-a5c7-4121c61e9fab"],
  "maria-stuarda": ["Maria Stuarda", "Gaetano Donizetti", "2dac964d-5543-45ca-a5c7-4121c61e9fab"],
  mazeppa: ["Mazeppa", "Piotr Ilitch Tchaïkovski", "8b8442d0-dd77-4c59-ab2e-d897abb10408"],
  "of-one-blood": ["Of One Blood", "Brett Dean", BRETT_DEAN_ID],
  "pique-dame": ["Pique Dame", "Piotr Ilitch Tchaïkovski", "8b8442d0-dd77-4c59-ab2e-d897abb10408"],
  rigoletto: ["Rigoletto", "Giuseppe Verdi", "b75ade14-9776-424c-8229-d32d98861611"],
  semele: ["Semele", "Georg Friedrich Händel", "8cfdf8f7-929a-48bc-9400-cd88d41c5904"],
};

function normalized(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("en-US")
    .replace(/[’']/g, " ")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function md5(value) {
  return crypto.createHash("md5").update(value, "utf8").digest("hex");
}

function workIdentity(composerId, title) {
  return `work:${md5(`${composerId}|${normalized(title)}`)}`;
}

function eventKey(event) {
  return `${SOURCE}:${event.source_event_id}`;
}

function main() {
  const input = process.argv[2];
  const output = process.argv[3];
  if (!input || !output) throw new Error("usage: build_bayerische_release_bundle.js <safe-staging.json> <bundle.json>");
  const staging = JSON.parse(fs.readFileSync(input, "utf8"));
  const works = Object.entries(NEW_WORKS).map(([slug, [title, composer, composerId]]) => ({
    candidate_key: slug,
    normalized_source_title: workIdentity(composerId, title),
    proposed_canonical_title: title,
    composer,
    composer_id: composerId,
  }));
  const events = staging.events.map((event) => ({
    event_key: eventKey(event),
    source: SOURCE,
    source_event_id: event.source_event_id,
    source_url: event.source_url,
    organization: "Bayerische Staatsoper",
    venue: "Nationaltheater",
    city: "Munich",
    country: "Germany",
    timezone: "Europe/Berlin",
    title: event.title,
    original_title: event.title,
    date: event.date,
    start_time: event.start_time,
    end_time: null,
    room: null,
    event_type: event.event_type,
    ticket_url: event.source_url,
  }));
  const relationships = staging.events
    .filter((event) => event.event_type === "opera")
    .map((event) => ({
      event_key: eventKey(event),
      ...(EXISTING_WORK_IDS[event.slug] ? { work_id: EXISTING_WORK_IDS[event.slug] } : { candidate_key: event.slug }),
      order: 1,
    }));
  const creditRows = staging.events.flatMap((event) => (event.credits || []).map((credit) => ({
    event_key: eventKey(event),
    artist_name: credit.artist_name,
    artist_identity_key: normalized(credit.artist_name),
    entity_type: credit.credit_kind === "ensemble" ? "ensemble" : "person",
    role: credit.role,
    character: credit.character || null,
    raw_character: credit.raw_character || null,
  })));
  const graphPayload = {
    source: SOURCE,
    organization: { name: "Bayerische Staatsoper", slug: "bayerische-staatsoper" },
    venue: { name: "Nationaltheater", city: "Munich", country_code: "DE" },
    events,
    event_sources: events.map((event) => ({
      event_key: event.event_key,
      source: SOURCE,
      source_event_id: event.source_event_id,
      source_url: event.source_url,
    })),
    composers: [],
    works,
    relationships,
    artists: [],
    event_credits: [],
  };
  const bundle = {
    schema_version: "bayerische-staatsoper-production-release-bundle-v1",
    production_writes: 0,
    bootstrap_composers: [{
      id: BRETT_DEAN_ID,
      canonical_name: "Brett Dean",
      identity_key: `composer:${md5("brett dean")}`,
    }],
    graph_payload: graphPayload,
    credit_rows: creditRows,
    summary: {
      events: events.length,
      event_sources: graphPayload.event_sources.length,
      relationships: relationships.length,
      existing_works_reused: Object.keys(EXISTING_WORK_IDS).length,
      new_works: works.length,
      new_composers: 1,
      credits: creditRows.length,
      unique_artists: new Set(creditRows.map((credit) => credit.artist_name)).size,
    },
  };
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify(bundle, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify(bundle.summary, null, 2)}\n`);
}

main();
