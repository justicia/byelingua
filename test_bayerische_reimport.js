"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { castSlice, detailHeader, parseCalendarLink, parseCredits } = require("./jobs/stage_bayerische_reimport");

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
