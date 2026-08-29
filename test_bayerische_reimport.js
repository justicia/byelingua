"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { castSlice, composerFromCalendar, dedupeCredits, detailHeader, normalizeCreditRows, normalizeEvents, parseCalendarLink, parseCredits, splitArtistNames } = require("./jobs/stage_bayerische_reimport");

test("authoritative occurrence URL controls date and time", () => {
  const event = parseCalendarLink({
    href: "https://www.staatsoper.de/stuecke/carmen/2027-07-09-1900-16339",
    text: "9.7.27 Freitag 19.00 Uhr | Nationaltheater CARMEN Georges Bizet Preise Oper",
  });
  assert.equal(event.date, "2027-07-09");
  assert.equal(event.start_time, "19:00");
  assert.equal(event.source_event_id, "16339");
  assert.equal(event.event_type, "opera");
});

test("relative official occurrence links resolve against the Staatsoper origin", () => {
  const event = parseCalendarLink({
    href: "/stuecke/la-cenerentola/2026-09-19-1800-16092",
    text: "19.9.26 Samstag 18.00 Uhr | Nationaltheater LA CENERENTOLA Gioachino Rossini Oper",
  });
  assert.equal(event.source_url, "https://www.staatsoper.de/stuecke/la-cenerentola/2026-09-19-1800-16092");
  assert.equal(event.source_event_id, "16092");
});

test("non-target rooms are excluded", () => {
  assert.equal(parseCalendarLink({
    href: "https://www.staatsoper.de/stuecke/workshop/2027-07-09-1000-99999",
    text: "9.7.27 Freitag 10.00 Uhr | Salon Luitpold Workshop Extra",
  }), null);
});

test("official cast section becomes canonical team, cast, and ensemble credits", () => {
  const body = [
    "Navigation",
    "9.7.27 Freitag Fr.",
    "19.00 Uhr | Nationaltheater",
    "CARMEN",
    "Georges Bizet",
    "Besetzung",
    "Musikalische Leitung",
    "Francesco Ivan Ciampa",
    "Nach einer Produktion von",
    "Lina Wertmüller",
    "Carmen",
    "Aigul Akhmetshina",
    "Bayerisches Staatsorchester",
    "Bayerischer Staatsopernchor",
    "Kommende Vorstellungen",
  ];
  const occurrence = { date: "2027-07-09", title: "Carmen", event_type: "opera" };
  assert.deepEqual(detailHeader(body, occurrence), { title: "CARMEN", composer: "Georges Bizet" });
  const credits = parseCredits(castSlice(body), occurrence);
  assert.deepEqual(credits.map((credit) => credit.role), ["conductor", "stage_director", "performer", "orchestra", "choir"]);
  assert.equal(credits[2].character, "Carmen");
  assert.equal(credits[2].artist_name, "Aigul Akhmetshina");
});

test("staging cleanup deduplicates credits and propagates official production metadata", () => {
  const duplicate = { artist_name: "Tom Visser", role: "lighting_designer" };
  const events = normalizeEvents([
    { slug: "doctor-atomic", event_type: "opera", title: "Doctor Atomic", programme: [{ source_title: "Doctor Atomic", composer: null }], credits: [duplicate, duplicate] },
    { slug: "doctor-atomic", event_type: "opera", title: "DOCTOR ATOMIC", programme: [{ source_title: "DOCTOR ATOMIC", composer: "John Adams" }], credits: [] },
  ]);
  assert.equal(events[0].title, "DOCTOR ATOMIC");
  assert.equal(events[0].programme[0].composer, "John Adams");
  assert.equal(dedupeCredits(events[0].credits).length, 1);
});

test("official calendar text recovers a missing opera composer", () => {
  assert.equal(
    composerFromCalendar(
      "3. Juli 2027 19.00 Uhr | Nationaltheater PIQUE DAME Pjotr Tschaikowski Preise M",
      "PIQUE DAME",
    ),
    "Pjotr Tschaikowski",
  );
});

test("adjacent official artist links split without splitting ordinary names", () => {
  assert.deepEqual(splitArtistNames("Sarah DufresneAntonia CáceresLucy Altus"), ["Sarah Dufresne", "Antonia Cáceres", "Lucy Altus"]);
  assert.deepEqual(splitArtistNames("Anna McDonald"), ["Anna McDonald"]);
});

test("legacy staged team and adjacent choir rows normalize without another source request", () => {
  const team = normalizeCreditRows({ artist_name: "Jane DoeJohn Roe", source_role: "Mitarbeit Inszenierung", role: "performer", raw_character: "Mitarbeit Inszenierung" });
  assert.deepEqual(team.map((credit) => credit.artist_name), ["Jane Doe", "John Roe"]);
  assert.equal(team[0].role, "stage_director");
  const choirs = normalizeCreditRows({ artist_name: "Extrachor der Bayerischen Staatsoper", source_role: "Bayerischer Staatsopernchor und Zusatzchor der Bayerischen Staatsoper", role: "performer" });
  assert.deepEqual(choirs.map((credit) => credit.role), ["choir", "choir"]);
});
