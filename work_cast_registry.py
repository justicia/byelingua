"""Reviewed GLOBAL Work-role selection policies, shared by API and ingestion.

Canonical Work/Character identities remain in the database global masters.
This registry references existing Work and work_character IDs and reviewed source
spellings only; it never creates identities, aliases or performer assignments.
"""

WORK_CAST_POLICIES = {'1419cf39-79a3-408c-b757-ab0188fb9963': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'864490aa-ca6e-4b61-85a8-8098be2ee2e1': 5,
                                                         'd22b0a9a-eff5-413c-9217-638fc97c6795': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/don-carlos/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Don Carlo': {'label': 'Don Carlo', 'rank': 1},
                                                           'Eboli': {'label': 'La Principessa Eboli',
                                                                     'rank': 5},
                                                           'Elisabetta di Valois': {'label': 'Elisabetta di '
                                                                                             'Valois',
                                                                                    'rank': 2},
                                                           'Filippo II': {'label': 'Filippo II', 'rank': 3},
                                                           'Filippo II.': {'label': 'Filippo II',
                                                                           'rank': 3}}},
 '184e5141-64ff-47df-b222-86104fae4ff5': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'311931a3-68bd-4e8d-9452-4cf3f055f545': 4,
                                                         '31c99d90-88fd-49bf-9b1b-1b0321704c87': 2,
                                                         'ac277c04-3770-43b8-8ca8-dc090b8a0947': 1,
                                                         'f418400b-89a8-430b-9e41-5d25bad35304': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-elixir-of-love/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Adina': {'label': 'Adina', 'rank': 1},
                                                           'Belcore': {'label': 'Belcore', 'rank': 4},
                                                           'Doktor Dulcamara': {'label': 'Dulcamara',
                                                                                'rank': 3},
                                                           'Dulcamara': {'label': 'Dulcamara', 'rank': 3},
                                                           'Il Dottor Dulcamara': {'label': 'Dulcamara',
                                                                                   'rank': 3},
                                                           'Nemorino': {'label': 'Nemorino', 'rank': 2}}},
 '190ee9d0-42d5-5307-889b-b49352384abf': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/akhnaten/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {}},
 '21a7c9de-c36a-4237-b90b-0968380f39ed': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'5ab94be3-6bf0-4605-953c-5e08610762e6': 4,
                                                         '6c6a146c-8c17-47a6-8d27-3b719a1f8df0': 2,
                                                         '925ab0d3-e28d-4794-b15c-d2a052eb7634': 3,
                                                         '9b42e12c-d27d-447a-90d6-556c5ef529fc': 1,
                                                         'aa56de82-3d23-4247-ab8d-93ff1b7c310b': 5},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/tristan-and-isolde/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Brangäne': {'label': 'Brangäne', 'rank': 3},
                                                           'Isolde': {'label': 'Isolde', 'rank': 2},
                                                           'Kurwenal': {'label': 'Kurwenal', 'rank': 4},
                                                           'König Marke': {'label': 'König Marke', 'rank': 5},
                                                           'Tristan': {'label': 'Tristan', 'rank': 1}}},
 '235a807b-cb7a-4f5a-b205-a85e9b30c939': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'06312904-9159-4393-b107-5ede3caeed12': 2,
                                                         '414be9f8-5612-48da-99f3-69df229fe969': 1,
                                                         '47ec297b-1c89-4ff3-ae58-39ea3292354b': 3,
                                                         '6f69cc29-9e3f-4ddf-bfb9-7cd66df6126c': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/fidelio/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Don Pizarro': {'label': 'Don Pizarro', 'rank': 4},
                                                           'Florestan': {'label': 'Florestan', 'rank': 2},
                                                           'Leonore': {'label': 'Leonore', 'rank': 1},
                                                           'Rocco': {'label': 'Rocco', 'rank': 3}}},
 '2746a542-69dc-4047-856d-6f2162bdcd46': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'424b2435-56c0-426a-a5d1-9923e5abdf5a': 3,
                                                         'ac6ceadd-441d-4244-9a29-36dea7f37f08': 1,
                                                         'e57f053e-5306-41df-9422-dfe6ee6e6c10': 4,
                                                         'f56d150d-e640-4da6-bb51-2413a934c79b': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/madam-butterfly/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'B. F. Pinkerton': {'label': 'Pinkerton',
                                                                               'rank': 2},
                                                           'B.F. Pinkerton': {'label': 'Pinkerton',
                                                                              'rank': 2},
                                                           'Benjamin Franklin Pinkerton': {'label': 'Pinkerton',
                                                                                           'rank': 2},
                                                           'Cio-Cio San': {'label': 'Cio-Cio-San', 'rank': 1},
                                                           'Cio-Cio-San': {'label': 'Cio-Cio-San', 'rank': 1},
                                                           'Lieutenant B.F. Pinkerton': {'label': 'Pinkerton',
                                                                                         'rank': 2},
                                                           'Pinkerton': {'label': 'Pinkerton', 'rank': 2},
                                                           'Sharpless': {'label': 'Sharpless', 'rank': 4},
                                                           'Suzuki': {'label': 'Suzuki', 'rank': 3}}},
 '2dad1ff4-64e7-5f6d-aaee-cdb2e602ff79': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/rise-and-fall-of-the-city-of-mahagonny/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Dreieinigkeitsmoses': {'label': 'Dreieinigkeitsmoses',
                                                                                   'rank': 4},
                                                           'Fatty, der Prokurist': {'label': 'Fatty',
                                                                                    'rank': 5},
                                                           'Jenny Hill': {'label': 'Jenny', 'rank': 2},
                                                           'Leokadja Begbick': {'label': 'Leokadja Begbick',
                                                                                'rank': 3}}},
 '32c0bf52-7812-40f3-82bf-27e8749e40df': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'005441d0-612a-44f5-877b-7c5988c6ba86': 1,
                                                         '3ad9dee4-d025-469a-a490-6e0915c0aa48': 3,
                                                         'facdf751-c705-4d32-857e-b5aa6e5c561c': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/orpheus-and-eurydice/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Amour': {'label': 'Amour', 'rank': 3},
                                                           'Eurydice': {'label': 'Eurydice', 'rank': 2},
                                                           'Orphée': {'label': 'Orphée', 'rank': 1}}},
 '33964ebf-6ebe-5646-919f-65e0bc66eda7': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/orpheus-in-the-underworld/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Jupiter': {'label': 'Jupiter', 'rank': 4}}},
 '34151afa-505c-4f03-b190-9774d6b81630': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'1736d2dc-4801-475e-9636-19f20ed00a3d': 4,
                                                         '9d3d8464-046b-473f-8923-f2f964c3adeb': 2,
                                                         'aaba12ef-c83e-47b1-b5a1-e3c2b3fe1d54': 3,
                                                         'e768a957-4b60-4104-ac6f-25c23b175671': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/en/season-26-27/opera/werther',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Albert': {'label': 'Albert', 'rank': 3},
                                                           'Charlotte': {'label': 'Charlotte', 'rank': 2},
                                                           'Sophie': {'label': 'Sophie', 'rank': 4},
                                                           'Werther': {'label': 'Werther', 'rank': 1}}},
 '374a46a9-f717-4e47-b54b-4ee82ff5dd16': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'069f1957-3f08-4c33-bc8a-33898ef1c99a': 3,
                                                         '5ec95cdf-f08e-4dd9-9345-b5f4319d885d': 2,
                                                         'b06bca83-3395-4361-9053-1f43c44d6b05': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroreal.es/en/show/simon-boccanegra',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Amelia Grimaldi': {'label': 'Amelia Grimaldi',
                                                                               'rank': 2},
                                                           'Jacopo Fiesco': {'label': 'Jacopo Fiesco',
                                                                             'rank': 3},
                                                           'Simon Boccanegra': {'label': 'Simon Boccanegra',
                                                                                'rank': 1}}},
 '377ad19d-99be-43ab-8c3d-460f3f1edc75': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'351cd46c-c629-48da-903b-83d0c6943b57': 2,
                                                         'b00b98bc-fcb4-403c-8feb-dd3389513661': 1,
                                                         'bab549f7-68c1-4930-b31a-1404eae8bf27': 3,
                                                         'dc1d82d6-ea1c-483b-9ee1-f7e4b7af67d1': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/salome/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Herodes': {'label': 'Herodes', 'rank': 3},
                                                           'Herodias': {'label': 'Herodias', 'rank': 4},
                                                           'Jochanaan': {'label': 'Jochanaan', 'rank': 2},
                                                           'Salome': {'label': 'Salome', 'rank': 1}}},
 '38ac1e96-7b0d-4601-9338-f69022c0dc0f': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'12647680-9c7f-41b7-820c-b2dace560529': 1,
                                                         '3068610e-efe9-4ac0-90b6-b504eb6877fc': 2,
                                                         '35eeac98-8063-446d-ac95-ada4aa2f36e3': 3,
                                                         'd52613ae-ebfb-4a28-b577-87f67c300bc0': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.lamonnaiedemunt.be/en/program/3934-ariadne-auf-naxos',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Der Komponist': {'label': 'Komponist', 'rank': 4},
                                                           'Komponist': {'label': 'Komponist', 'rank': 4},
                                                           'Primadonna / Ariadne': {'label': 'Primadonna/Ariadne',
                                                                                    'rank': 1},
                                                           'Primadonna/Ariadne': {'label': 'Primadonna/Ariadne',
                                                                                  'rank': 1},
                                                           'Tenor/Bacchus': {'label': 'Tenor/Bacchus',
                                                                             'rank': 2},
                                                           'Zerbinetta': {'label': 'Zerbinetta', 'rank': 3}}},
 '3994ea46-0294-43f0-a30d-c863794b1ff4': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'16ac3599-36ab-4bcd-8641-e628c6bd5db1': 4,
                                                         '4180eba7-aa17-4145-bb5b-20f644f5dfe6': 3,
                                                         'a07f6f91-57bf-40ac-be51-2f72970c28cf': 1,
                                                         'd781b03e-9b29-4445-acc3-4659f17a3822': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-pearl-fishers/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Leila': {'label': 'Leïla', 'rank': 1},
                                                           'Leïla': {'label': 'Leïla', 'rank': 1},
                                                           'Nadir': {'label': 'Nadir', 'rank': 2},
                                                           'Nourabad': {'label': 'Nourabad', 'rank': 4},
                                                           'Zurga': {'label': 'Zurga', 'rank': 3}}},
 '3e854127-e1f0-48e0-848d-45ed3f8d80b9': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'afd1664f-d2d3-41bf-a535-2095c3a29992': 1,
                                                         'dbc6bda0-2fe0-44f8-92d7-33ed18c06d97': 2,
                                                         'e78f8d81-96d6-4ef5-a650-8a33fb8ef9f7': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.opernhaus.ch/en/spielplan/calendar/manon-lescaut/2026-2027/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Chevalier René Des Grieux': {'label': 'Il '
                                                                                                  'cavaliere '
                                                                                                  'Renato '
                                                                                                  'Des '
                                                                                                  'Grieux',
                                                                                         'rank': 2},
                                                           'Il cavaliere Des Grieux': {'label': 'Il '
                                                                                                'cavaliere '
                                                                                                'Renato Des '
                                                                                                'Grieux',
                                                                                       'rank': 2},
                                                           'Il cavaliere Renato Des Grieux': {'label': 'Il '
                                                                                                       'cavaliere '
                                                                                                       'Renato '
                                                                                                       'Des '
                                                                                                       'Grieux',
                                                                                              'rank': 2},
                                                           'Le Chevalier des Grieux': {'label': 'Il '
                                                                                                'cavaliere '
                                                                                                'Renato Des '
                                                                                                'Grieux',
                                                                                       'rank': 2},
                                                           'Manon Lescaut': {'label': 'Manon Lescaut',
                                                                             'rank': 1},
                                                           'Renato Des Grieux': {'label': 'Il cavaliere '
                                                                                          'Renato Des Grieux',
                                                                                 'rank': 2},
                                                           'The Chevalier Renato des Grieux': {'label': 'Il '
                                                                                                        'cavaliere '
                                                                                                        'Renato '
                                                                                                        'Des '
                                                                                                        'Grieux',
                                                                                               'rank': 2}}},
 '3f137f95-0a2f-48a9-87c8-ad8ea4c77918': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/jenufa/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Jenůfa': {'label': 'Jenůfa', 'rank': 1},
                                                           'Kostelnička Buryjovka': {'label': 'Kostelnička',
                                                                                     'rank': 2},
                                                           'Laca Klemen': {'label': 'Laca Klemeň', 'rank': 3},
                                                           'Števa Buryja': {'label': 'Števa Buryja',
                                                                            'rank': 4}}},
 '3f49869d-a77e-4e87-a7e6-d6a469ee51e3': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'6096b6e8-ec55-44ce-943c-ad67f4a7f1f1': 1,
                                                         'fe80bacd-8902-49ad-9e8c-9c532b7ddda9': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://liceubarcelona.cat/en/capuleti-montecchi',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Giulietta': {'label': 'Giulietta', 'rank': 2},
                                                           'Romeo': {'label': 'Romeo', 'rank': 1}}},
 '3ffd90ba-5393-48c8-9fdb-e5c7043d203d': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'23fc550a-1c75-4bd6-b1f2-281919d9191b': 2,
                                                         '26410778-c16e-4c44-b745-bdcb70b016c6': 3,
                                                         '3850f9eb-b33b-4611-b120-db7bbc7fd9c4': 4,
                                                         '8761b4e3-9bd2-476d-bc26-5a8bf53c8e9d': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/saison-26-27/opera/le-trouvere',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Azucena': {'label': 'Azucena', 'rank': 3},
                                                           'Il Conte di Luna': {'label': 'Il conte di Luna',
                                                                                'rank': 4},
                                                           'Il conte di Luna': {'label': 'Il conte di Luna',
                                                                                'rank': 4},
                                                           'Leonora': {'label': 'Leonora', 'rank': 1},
                                                           'Manrico': {'label': 'Manrico', 'rank': 2}}},
 '4004b276-2974-4d28-9307-0b67330d8a84': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'02fa60ad-c665-4bab-b2a4-fc13f10b814a': 4,
                                                         '77b60a90-9b02-4930-bf07-d0449d397aec': 3,
                                                         '9c97a50c-d189-454f-9f12-a5e58e9a281f': 1,
                                                         '9dcbe891-aaaa-4b20-b060-6eb0db5e0bad': 5,
                                                         'a3663c49-0b45-44fd-aa59-262a167b1c70': 6,
                                                         'be7f2e80-1739-44c2-8146-9382123fb509': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/cosi-fan-tutte/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Despina': {'label': 'Despina', 'rank': 5},
                                                           'Don Alfonso': {'label': 'Don Alfonso', 'rank': 6},
                                                           'Dorabella': {'label': 'Dorabella', 'rank': 2},
                                                           'Ferrando': {'label': 'Ferrando', 'rank': 3},
                                                           'Fiordiligi': {'label': 'Fiordiligi', 'rank': 1},
                                                           'Guglielmo': {'label': 'Guglielmo', 'rank': 4}}},
 '414c32ba-9e40-4260-ab4c-c1fb84993ee5': {'basis': 'Synopsis: the Arabella/Mandryka and Zdenka/Matteo '
                                                   'relationships; editorial summary selection, not an '
                                                   'exhaustive ranking.',
                                          'characters': {'4248f680-1b96-4292-a626-537dcce7eb56': 3,
                                                         '74f7bcfc-0b3b-410e-8fbd-e26ef7d27c04': 2,
                                                         'c55729ad-c7f0-4efa-8c2f-d4f810077112': 1,
                                                         'f2025f27-f6ac-4ac3-a470-94293e3abe58': 4},
                                          'event_types': ['opera'],
                                          'evidence': 'https://www.wiener-staatsoper.at/en/calendar/detail/arabella/2027-06-01/',
                                          'reviewed_on': '2026-10-22'},
 '46141d16-fb84-4634-ad82-432ea815566b': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'0b02a99c-8586-4b1d-af26-e10185974749': 1,
                                                         '17c0a7c8-e0de-4d2e-94a8-2c74383128ca': 5,
                                                         '33fc8c2a-ef9f-4b1c-b9dc-1c1ac4a5f6fd': 4,
                                                         '41203eef-f5b0-4773-8717-1d6a673e3623': 3,
                                                         'c2c1f2be-7b6c-4b62-b4f6-eedf9adb3b4c': 6,
                                                         'eb62157d-ca8d-49a5-b8c8-c0af67bb7157': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operasofia.bg/en/repertoire/856',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Brünnhilde': {'label': 'Brünnhilde', 'rank': 1},
                                                           'Gunther': {'label': 'Gunther', 'rank': 4},
                                                           'Gutrune': {'label': 'Gutrune', 'rank': 5},
                                                           'Hagen': {'label': 'Hagen', 'rank': 3},
                                                           'Siegfried': {'label': 'Siegfried', 'rank': 2},
                                                           'Waltraute': {'label': 'Waltraute', 'rank': 6},
                                                           'brunnhilde': {'label': 'Brünnhilde', 'rank': 1},
                                                           'gunther': {'label': 'Gunther', 'rank': 4},
                                                           'gutrune': {'label': 'Gutrune', 'rank': 5},
                                                           'hagen': {'label': 'Hagen', 'rank': 3},
                                                           'siegfried': {'label': 'Siegfried', 'rank': 2},
                                                           'waltraute': {'label': 'Waltraute', 'rank': 6}}},
 '5000bcc2-5f91-4a77-90ef-eb1306910965': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/lucia-di-lammermoor/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Lord Enrico Ashton': {'label': 'Enrico',
                                                                                  'rank': 3},
                                                           'Lucia': {'label': 'Lucia', 'rank': 1},
                                                           'Raimondo Bidebent': {'label': 'Raimondo',
                                                                                 'rank': 4},
                                                           'Sir Edgardo di Ravenswood': {'label': 'Edgardo',
                                                                                         'rank': 2}}},
 '541991e8-774b-439e-87c3-ac19a06cd488': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'2cc2b8b7-3ac6-4807-af78-d9b3bb189394': 3,
                                                         '78db1be9-3f7c-424f-b6a7-dac02f7ef49e': 1,
                                                         'ee13ffcb-ac26-4e7b-bf07-59e82a641e2f': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.glyndebourne.com/opera-archive/explore-our-operas/explore-rinaldo/rinaldo-synopsis/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Almirena': {'label': 'Almirena', 'rank': 2},
                                                           'Armida': {'label': 'Armida', 'rank': 3},
                                                           'Rinaldo': {'label': 'Rinaldo', 'rank': 1}}},
 '549bfd84-3d88-410d-a1ab-0a28a505f5c1': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/rigoletto/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Gilda': {'label': 'Gilda', 'rank': 2},
                                                           'Herzog von Mantua': {'label': 'Il Duca di '
                                                                                          'Mantova',
                                                                                 'rank': 3},
                                                           'Il Duca di Mantova': {'label': 'Il Duca di '
                                                                                           'Mantova',
                                                                                  'rank': 3},
                                                           'Maddalena': {'label': 'Maddalena', 'rank': 5},
                                                           'Rigoletto': {'label': 'Rigoletto', 'rank': 1},
                                                           'Sparafucile': {'label': 'Sparafucile',
                                                                           'rank': 4}}},
 '59101410-97f9-42ad-9b89-f7cab20eaf63': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'3bcb737a-e2f3-49c3-9c83-e2e5cb538eb8': 4,
                                                         '486ea0d3-fca6-4b73-b521-ccc957b26bb1': 6,
                                                         '529a2f83-38e4-4b8d-8e5b-899dbbb4d961': 1,
                                                         '5e37c0a3-4309-4368-9a05-948bba018f8d': 5,
                                                         'afaf7896-e2fc-4f1f-a055-5872cfb15843': 2,
                                                         'e11c0df5-ec86-4f6f-bcd8-aaf2988bcc09': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-valkyrie/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Brünnhilde': {'label': 'Brünnhilde', 'rank': 1},
                                                           'Fricka': {'label': 'Fricka', 'rank': 5},
                                                           'Hunding': {'label': 'Hunding', 'rank': 6},
                                                           'Sieglinde': {'label': 'Sieglinde', 'rank': 3},
                                                           'Siegmund': {'label': 'Siegmund', 'rank': 4},
                                                           'Wotan': {'label': 'Wotan', 'rank': 2},
                                                           'brunnhilde': {'label': 'Brünnhilde', 'rank': 1},
                                                           'fricka': {'label': 'Fricka', 'rank': 5},
                                                           'hunding': {'label': 'Hunding', 'rank': 6},
                                                           'sieglinde': {'label': 'Sieglinde', 'rank': 3},
                                                           'siegmund': {'label': 'Siegmund', 'rank': 4},
                                                           'wotan': {'label': 'Wotan', 'rank': 2}}},
 '5f65922a-184b-4485-9562-37d9bd688bd3': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/saison-26-27/opera/lady-macbeth-de-mzensk',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Boris Timofeevitch Ismaïlov': {'label': 'Boris '
                                                                                                    'Timofeevitch '
                                                                                                    'Ismaïlov',
                                                                                           'rank': 3},
                                                           'Katerina Lvovna Ismaïlova': {'label': 'Katerina '
                                                                                                  'Lvovna '
                                                                                                  'Ismailova',
                                                                                         'rank': 1},
                                                           'Sergueï': {'label': 'Sergueï', 'rank': 2},
                                                           'Zinovy Borisovitch Ismaïlov': {'label': 'Zinovy '
                                                                                                    'Borisovitch '
                                                                                                    'Ismaïlov',
                                                                                           'rank': 4}}},
 '5fc01cf2-8e65-4536-9d94-1fc59fa630e1': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'09a2f452-3551-43bc-aee3-4fa5b0bb6ffb': 4,
                                                         '420c3e44-f0d8-4022-a05a-691e3a36f006': 2,
                                                         '72f1b7e8-30f1-4e98-8102-abe61d938964': 6,
                                                         'c54f33d1-0f47-4372-95c5-fa12a2cbcbed': 5,
                                                         'f6cc3065-7394-470b-a58d-7689fe32d94b': 3,
                                                         'fb8926f5-a6b8-448c-adb7-e8cf403462fc': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/la-boheme/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Colline': {'label': 'Colline', 'rank': 5},
                                                           'Marcello': {'label': 'Marcello', 'rank': 4},
                                                           'Mimì': {'label': 'Mimì', 'rank': 1},
                                                           'Musetta': {'label': 'Musetta', 'rank': 3},
                                                           'Rodolfo': {'label': 'Rodolfo', 'rank': 2},
                                                           'Schaunard': {'label': 'Schaunard', 'rank': 6}}},
 '6b0a1285-f351-4459-aa47-18821fca3551': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'c7c2e0b7-011c-4705-a765-46498cd20203': 1,
                                                         'da22aa63-479e-4083-84f9-8e9da0f6cfc2': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/die-entfuehrung-aus-dem-serail.1383413?event_date=17903222',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Belmonte': {'label': 'Belmonte', 'rank': 2},
                                                           'Konstanze': {'label': 'Konstanze', 'rank': 1}}},
 '6e955d97-e5c2-4583-8851-d534f04a8b73': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'465e26dc-1cf5-42f4-a9f3-475ee807c0ab': 1,
                                                         '50bd0afc-33b4-4259-b129-3e4d5765c364': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/lulu/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Gräfin Geschwitz': {'label': 'Gräfin Geschwitz',
                                                                                'rank': 4},
                                                           'Lulu': {'label': 'Lulu', 'rank': 1}}},
 '7040b2c9-c5fa-4564-955b-bc1f02cfd6aa': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'268b2a78-0ef9-4026-ba08-0e4f3a17f0c0': 4,
                                                         '464c7a7a-c35c-43dc-a7e5-238f71224e3e': 2,
                                                         '4f180505-6200-4834-90c5-0b2d0bfc48e6': 5,
                                                         '61b4c310-0a4e-4409-a70a-593db9b1f11d': 3,
                                                         '7687df09-a175-463f-8494-0d6d3ccc8bf6': 3,
                                                         '7de4e457-7cb2-4cdc-9bc0-ac5090bb15b4': 1,
                                                         'd3a0851a-5134-4612-8dab-8b4f91929739': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-marriage-of-figaro/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Cherubino': {'label': 'Cherubino', 'rank': 5},
                                                           'Chérubin': {'label': 'Cherubino', 'rank': 5},
                                                           'Count Almaviva': {'label': 'Il Conte di Almaviva',
                                                                              'rank': 4},
                                                           'Countess Almaviva': {'label': 'La Contessa di '
                                                                                          'Almaviva',
                                                                                 'rank': 3},
                                                           'Figaro': {'label': 'Figaro', 'rank': 1},
                                                           'Graf Almaviva': {'label': 'Il Conte di Almaviva',
                                                                             'rank': 4},
                                                           'Gräfin Almaviva': {'label': 'La Contessa di '
                                                                                        'Almaviva',
                                                                               'rank': 3},
                                                           'Il Conte di Almaviva': {'label': 'Il Conte di '
                                                                                             'Almaviva',
                                                                                    'rank': 4},
                                                           'Il Conte d’Almaviva': {'label': 'Il Conte di '
                                                                                            'Almaviva',
                                                                                   'rank': 4},
                                                           'La Comtesse Almaviva': {'label': 'La Contessa di '
                                                                                             'Almaviva',
                                                                                    'rank': 3},
                                                           'La Contessa di Almaviva': {'label': 'La Contessa '
                                                                                                'di Almaviva',
                                                                                       'rank': 3},
                                                           'La Contessa d’Almaviva': {'label': 'La Contessa '
                                                                                               'di Almaviva',
                                                                                      'rank': 3},
                                                           'Le Comte Almaviva': {'label': 'Il Conte di '
                                                                                          'Almaviva',
                                                                                 'rank': 4},
                                                           'Susanna': {'label': 'Susanna', 'rank': 2},
                                                           'Suzanne': {'label': 'Susanna', 'rank': 2}}},
 '72413b78-c83c-4131-ac0c-d2452ae71131': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'51b4ec05-858a-470e-a480-ffd5e8446e59': 1,
                                                         '82c6aff4-e42f-4fe8-984f-89115735ea52': 3,
                                                         '98a5e55e-c358-4b34-bc1d-ecd0897ae75d': 2,
                                                         'df9aa74e-98a3-4610-837c-db411daea70b': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-berlin.de/de/veranstaltungen/der-rosenkavalier.7549/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Baron Ochs auf Lerchenau': {'label': 'Baron Ochs '
                                                                                                 'auf '
                                                                                                 'Lerchenau',
                                                                                        'rank': 4},
                                                           'Die Feldmarschallin': {'label': 'Feldmarschallin',
                                                                                   'rank': 1},
                                                           'Feldmarschallin': {'label': 'Feldmarschallin',
                                                                               'rank': 1},
                                                           'Octavian': {'label': 'Octavian', 'rank': 2},
                                                           'Sophie': {'label': 'Sophie', 'rank': 3}}},
 '73e51cd4-2d41-44ea-868a-c0b8fa3dcee1': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'3175f321-1bf7-44d6-a3f7-326965f055b5': 1,
                                                         '4c692125-101e-4a61-827d-27f29dc89bbc': 2,
                                                         'ae4fafa1-5498-4c5a-ad9d-31ab33fc8d62': 3,
                                                         'ee8a16d3-aebb-4ec5-a11a-2b83a0b31dfc': 5,
                                                         'f1aee810-a8bd-4d02-b168-da5680cb44d8': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.rbo.org.uk/production/un-ballo-in-maschera-philipp-stolzl',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Amelia': {'label': 'Amelia', 'rank': 1},
                                                           'Ankarström': {'label': 'Ankarström', 'rank': 3},
                                                           'Count Anckarstroem': {'label': 'Ankarström',
                                                                                  'rank': 3},
                                                           'Gustavo III': {'label': 'Gustavo III.',
                                                                           'rank': 2},
                                                           'Gustavo III.': {'label': 'Gustavo III.',
                                                                            'rank': 2},
                                                           'Il conte di Anckarström': {'label': 'Ankarström',
                                                                                       'rank': 3},
                                                           'Madame Ulrica Arvidson': {'label': 'Ulrica',
                                                                                      'rank': 4},
                                                           'Oscar': {'label': 'Oscar', 'rank': 5},
                                                           'Renato': {'label': 'Ankarström', 'rank': 3},
                                                           'Riccardo': {'label': 'Gustavo III.', 'rank': 2},
                                                           'Ulrica': {'label': 'Ulrica', 'rank': 4}}},
 '76a85b56-256e-4ea4-bff2-569c36a2b591': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'754a06b8-cec3-4be1-84b7-4f10b2c20c0f': 1,
                                                         '7a705eae-c783-4cfa-8070-0a530618baa0': 3,
                                                         'df4d3704-1442-4149-919c-2097756a87b0': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://liceubarcelona.cat/en/clemenza-tito',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Sesto': {'label': 'Sesto', 'rank': 2},
                                                           'Tito': {'label': 'Tito', 'rank': 1},
                                                           'Tito Vespasiano': {'label': 'Tito', 'rank': 1},
                                                           'Vitellia': {'label': 'Vitellia', 'rank': 3}}},
 '7b1d7bb8-59b5-4300-876b-d4a5486f0e7a': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'ad6c9c3a-5176-4de6-9744-f9c03a915378': 3,
                                                         'd7536bdb-f8b0-4e17-99b7-2f961d5f4cd8': 1,
                                                         'eb1107c7-e686-4992-b80c-c987b66d547f': 2,
                                                         'ff4045ee-ba1d-4f85-b196-b02901621234': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/norma/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Adalgisa': {'label': 'Adalgisa', 'rank': 2},
                                                           'Norma': {'label': 'Norma', 'rank': 1},
                                                           'Oroveso': {'label': 'Oroveso', 'rank': 4},
                                                           'Pollione': {'label': 'Pollione', 'rank': 3}}},
 '811833db-6a33-475c-a708-96e5e220b168': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'00afd425-0ee2-4051-9050-af691f2a7905': 5,
                                                         '22f2bc87-3230-4052-bb88-4c882db0893c': 2,
                                                         '2e61446c-92f4-42b5-808d-fd960b0d1376': 3,
                                                         '9b0cdd2a-3416-488f-a27a-50fd548b2e53': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/luisa-miller/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Luisa': {'label': 'Luisa', 'rank': 1},
                                                           'Miller': {'label': 'Miller', 'rank': 3},
                                                           'Rodolfo': {'label': 'Rodolfo', 'rank': 2},
                                                           'Wurm': {'label': 'Wurm', 'rank': 5}}},
 '8896245b-7f37-44c1-b166-1e9c8ce04357': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/aida/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Aida': {'label': 'Aida', 'rank': 1},
                                                           'Amneris': {'label': 'Amneris', 'rank': 3},
                                                           'Amonasro': {'label': 'Amonasro', 'rank': 4},
                                                           'Radamès': {'label': 'Radamès', 'rank': 2}}},
 '8a8d9b81-329e-45c9-9ac7-3665898bd139': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'0b386516-e10b-469d-875c-4e9fdcb2c57d': 2,
                                                         'a2a742be-2919-4a99-b7ee-799dc7ad6c79': 1,
                                                         'b3ffd7f6-61f1-42b7-ba35-8172e2ef59bd': 4,
                                                         'dd22ce00-8e42-44ab-8efb-cfa6a1416f93': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.opernhaus.ch/en/spielplan/calendar/tannhaeuser-1/2026-2027/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Elisabeth': {'label': 'Elisabeth', 'rank': 2},
                                                           'Elisabeth, Nichte des Landgrafen': {'label': 'Elisabeth',
                                                                                                'rank': 2},
                                                           'Tannhäuser': {'label': 'Tannhäuser', 'rank': 1},
                                                           'Venus': {'label': 'Venus', 'rank': 4},
                                                           'Wolfram Von Eschenbach': {'label': 'Wolfram Von '
                                                                                               'Eschenbach',
                                                                                      'rank': 3},
                                                           'Wolfram von Eschenbach': {'label': 'Wolfram Von '
                                                                                               'Eschenbach',
                                                                                      'rank': 3}}},
 '98b6ff5a-9462-4359-9183-6991ed83ef7f': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'57cac02c-b6db-4574-9f7e-f9e4be7a960f': 4,
                                                         '60093225-25c9-4f40-a366-5f59b0a8882f': 2,
                                                         '67f2533c-7957-4caf-b1a6-1a662784b40e': 1,
                                                         '78f83c9e-4323-4089-935d-a4ac4d835718': 3,
                                                         'ac391981-a38f-4179-acbd-5ddcf8d725e4': 3,
                                                         'c22b4142-dae0-43e5-9e10-1f63a3cd00bc': 5},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-barber-of-seville/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Bartolo': {'label': 'Bartolo', 'rank': 4},
                                                           'Basilio': {'label': 'Basilio', 'rank': 5},
                                                           'Conte Almaviva': {'label': 'Il Conte d’Almaviva',
                                                                              'rank': 3},
                                                           'Count Almaviva': {'label': 'Il Conte d’Almaviva',
                                                                              'rank': 3},
                                                           'Don Bartolo': {'label': 'Bartolo', 'rank': 4},
                                                           'Don Basilio': {'label': 'Basilio', 'rank': 5},
                                                           'Figaro': {'label': 'Figaro', 'rank': 1},
                                                           'Graf Almaviva': {'label': 'Il Conte d’Almaviva',
                                                                             'rank': 3},
                                                           "Il Conte d'Almaviva": {'label': 'Il Conte '
                                                                                            'd’Almaviva',
                                                                                   'rank': 3},
                                                           'Le Comte Almaviva': {'label': 'Il Conte '
                                                                                          'd’Almaviva',
                                                                                 'rank': 3},
                                                           'Le comte Almaviva': {'label': 'Il Conte '
                                                                                          'd’Almaviva',
                                                                                 'rank': 3},
                                                           'Rosina': {'label': 'Rosina', 'rank': 2},
                                                           'Rosine': {'label': 'Rosina', 'rank': 2}}},
 'a4333e3e-56c3-46ae-9910-d62f4e838ca1': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'0e1e21fb-0486-4d7c-8ff9-da015ca2cc23': 4,
                                                         '3135f608-c2d6-409b-8b46-4588d989da27': 5,
                                                         '402af53f-2c98-4114-950b-995cf3330c10': 2,
                                                         '496b57e1-12cb-4244-a334-13653d29ca04': 6,
                                                         '7b295a4d-23fd-4f8c-ad25-79859ed1f033': 3,
                                                         '7d610da3-5394-444e-959c-a002228bfcc5': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-magic-flute/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Königin der Nacht': {'label': 'Königin der Nacht',
                                                                                 'rank': 4},
                                                           'Pamina': {'label': 'Pamina', 'rank': 2},
                                                           'Papagena': {'label': 'Papagena', 'rank': 6},
                                                           'Papageno': {'label': 'Papageno', 'rank': 3},
                                                           'Queen of the Night': {'label': 'Königin der '
                                                                                           'Nacht',
                                                                                  'rank': 4},
                                                           'Sarastro': {'label': 'Sarastro', 'rank': 5},
                                                           'Tamino': {'label': 'Tamino', 'rank': 1}}},
 'ac2f36b9-67ea-4d31-a832-cf30f4ba7b3b': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'74c086f4-b76a-4075-9403-0402f8e21515': 1,
                                                         'b54a3c36-3a06-4b56-8b2b-035506fb2cc4': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.wiener-staatsoper.at/en/calendar/detail/lorfeo/2026-10-25/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Euridice': {'label': 'Euridice', 'rank': 2},
                                                           'Orfeo': {'label': 'Orfeo', 'rank': 1}}},
 'ae7c773a-8caf-4854-8a21-49b396647378': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'14c1c627-3054-43b3-9dc9-d305b108010e': 1,
                                                         '9e1a1c1a-3096-4233-a2ec-cc37ed6c2214': 2,
                                                         'b17799ce-6a51-4c23-b715-bf627a3f7670': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/la-traviata/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Alfredo Germont': {'label': 'Alfredo Germont',
                                                                               'rank': 2},
                                                           'Giorgio Germont': {'label': 'Giorgio Germont',
                                                                               'rank': 3},
                                                           'Violetta Valéry': {'label': 'Violetta Valéry',
                                                                               'rank': 1}}},
 'b37e7330-a724-4f70-adc8-6bb25f19f700': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'66a22adb-5802-488e-872b-542395a455d3': 1,
                                                         'a517ea12-e5ab-4073-bf06-df65844d51c2': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/der-fliegende-hollaender.1385827?event_date=17919032',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Der Holländer': {'label': 'Der Holländer',
                                                                             'rank': 1},
                                                           'Senta': {'label': 'Senta', 'rank': 2}}},
 'bad2549f-8283-4665-861f-88854d389ead': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/cinderella-la-cenerentola/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Alidoro': {'label': 'Alidoro', 'rank': 5},
                                                           'Angelina (Cenerentola)': {'label': 'Angelina',
                                                                                      'rank': 1},
                                                           'Dandini': {'label': 'Dandini', 'rank': 3},
                                                           'Don Magnifico': {'label': 'Don Magnifico',
                                                                             'rank': 4},
                                                           'Don Ramiro': {'label': 'Don Ramiro', 'rank': 2}}},
 'bc9d6a6f-6ad0-417a-a64c-d3813c56030e': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'3f4bb3bf-5530-40de-93f6-ba75ec02a117': 4,
                                                         '4bdabe35-b20e-4536-b5be-5ede78aff643': 3,
                                                         '7d3bdc76-39b7-44c9-b409-cdbe9465de5e': 2,
                                                         '8525a508-bd29-4bc9-938f-b506c44fd425': 1,
                                                         'e49e66a8-70df-4538-88e9-bf5e956fb542': 5},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.rbo.org.uk/production/parsifal-evgeny-titov',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Amfortas': {'label': 'Amfortas', 'rank': 3},
                                                           'Gurnemanz': {'label': 'Gurnemanz', 'rank': 4},
                                                           'Klingsor': {'label': 'Klingsor', 'rank': 5},
                                                           'Kundry': {'label': 'Kundry', 'rank': 2},
                                                           'Parsifal': {'label': 'Parsifal', 'rank': 1}}},
 'bcafbec4-3252-4856-a10c-557fef25c529': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'21e891bf-3c3e-48b4-9185-86f39815c3fc': 7,
                                                         '22c64ed3-d918-4bc7-b4c8-d08304f458fd': 5,
                                                         '340d762b-b71f-42f8-9be4-4337192820d3': 4,
                                                         '3663c3b9-f565-402f-b1d6-8c1d3cce70bc': 3,
                                                         '54f0d7e1-9ad8-4be9-8e54-5e3ba34e30a7': 6,
                                                         '62a26a89-144c-4b08-9248-86c58fe417ee': 8,
                                                         '6bc3d631-ea3b-4381-b4d9-96e09a2160ab': 1,
                                                         'b8610c65-9303-437b-bb2e-cf02cdc154ab': 2,
                                                         'dd038d66-6829-4428-bb12-f41c52e57c23': 8},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/don-giovanni/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Commendatore': {'label': 'Il Commendatore',
                                                                            'rank': 8},
                                                           'Der Komtur': {'label': 'Il Commendatore',
                                                                          'rank': 8},
                                                           'Don Giovanni': {'label': 'Don Giovanni',
                                                                            'rank': 1},
                                                           'Don Ottavio': {'label': 'Don Ottavio', 'rank': 5},
                                                           'Donna Anna': {'label': 'Donna Anna', 'rank': 3},
                                                           'Donna Elvira': {'label': 'Donna Elvira',
                                                                            'rank': 4},
                                                           'Il Commendatore': {'label': 'Il Commendatore',
                                                                               'rank': 8},
                                                           'Komtur': {'label': 'Il Commendatore', 'rank': 8},
                                                           'Le Commandeur': {'label': 'Il Commendatore',
                                                                             'rank': 8},
                                                           'Leporello': {'label': 'Leporello', 'rank': 2},
                                                           'Masetto': {'label': 'Masetto', 'rank': 7},
                                                           'The Commendatore': {'label': 'Il Commendatore',
                                                                                'rank': 8},
                                                           'Zerlina': {'label': 'Zerlina', 'rank': 6}}},
 'bd5a5d7a-2cf0-46d5-9bef-cba832820604': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'b9d3e772-cc4e-48d4-bb78-c9787cd992cc': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-dead-city/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Paul': {'label': 'Paul', 'rank': 1}}},
 'c2bab1a9-16e2-421e-8ef4-b312a2accb57': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'150eed5a-d4cb-4324-8af2-596315b69a32': 2,
                                                         '19ae9590-d97c-4622-afa1-1b85d66637b1': 4,
                                                         '85e246d6-243e-4e2a-96aa-ca464c7c18f6': 7,
                                                         '90fbcc2b-b223-4f84-8127-139a00eb1ad4': 8,
                                                         'c2097bd3-c821-4cd4-a936-83cc6b4f282b': 1,
                                                         'd9beae8b-3100-4a8b-967e-012c97c97425': 3,
                                                         'f610d8d9-d5cc-4f6a-bb5e-3279dcdcfcf8': 5,
                                                         'faadd8b2-bf96-450e-a97d-42f5e518380d': 6},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-rhinegold/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Alberich': {'label': 'Alberich', 'rank': 2},
                                                           'Erda': {'label': 'Erda', 'rank': 8},
                                                           'Fafner': {'label': 'Fafner', 'rank': 6},
                                                           'Fasolt': {'label': 'Fasolt', 'rank': 5},
                                                           'Freia': {'label': 'Freia', 'rank': 7},
                                                           'Fricka': {'label': 'Fricka', 'rank': 4},
                                                           'Loge': {'label': 'Loge', 'rank': 3},
                                                           'Wotan': {'label': 'Wotan', 'rank': 1},
                                                           'alberich': {'label': 'Alberich', 'rank': 2},
                                                           'erda': {'label': 'Erda', 'rank': 8},
                                                           'fafner': {'label': 'Fafner', 'rank': 6},
                                                           'fasolt': {'label': 'Fasolt', 'rank': 5},
                                                           'freia': {'label': 'Freia', 'rank': 7},
                                                           'fricka': {'label': 'Fricka', 'rank': 4},
                                                           'loge': {'label': 'Loge', 'rank': 3},
                                                           'wotan': {'label': 'Wotan', 'rank': 1}}},
 'c4551c69-40aa-41d6-8d8b-8f4caa9b372f': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'230928c2-f04f-46e7-bb19-e801082f367b': 2,
                                                         '63fedb7f-6bdf-4480-a258-0a2a7048b587': 1,
                                                         '7d356908-26b0-4288-ae59-c63e87877dc2': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/tosca/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Baron Scarpia': {'label': 'Baron Scarpia',
                                                                             'rank': 3},
                                                           'Floria Tosca': {'label': 'Floria Tosca',
                                                                            'rank': 1},
                                                           'Mario Cavaradossi': {'label': 'Mario Cavaradossi',
                                                                                 'rank': 2}}},
 'c7b6cef4-fe70-48a8-a7a2-710058c2861f': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'4c64c1fe-be34-4244-9954-5ec7cc420e9f': 3,
                                                         'ad389765-8e67-4609-9dca-40fae8e707ad': 4,
                                                         'caf95312-5487-4a73-a51f-0ee558740cd7': 1,
                                                         'dd55788e-3568-4e5d-b353-b8029a18f156': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.opera.lv/en/production/siegfried/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Brünnhilde': {'label': 'Brünnhilde', 'rank': 2},
                                                           'Der Wanderer': {'label': 'Wotan', 'rank': 4},
                                                           'Le Voyageur': {'label': 'Wotan', 'rank': 4},
                                                           'Mime': {'label': 'Mime', 'rank': 3},
                                                           'Siegfried': {'label': 'Siegfried', 'rank': 1},
                                                           'brunnhilde': {'label': 'Brünnhilde', 'rank': 2},
                                                           'mime': {'label': 'Mime', 'rank': 3},
                                                           'siegfried': {'label': 'Siegfried', 'rank': 1}}},
 'cf0b1949-88d9-52bf-8068-f61fd8308bb4': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/rusalka/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Die fremde Fürstin': {'label': 'Die fremde '
                                                                                           'Fürstin',
                                                                                  'rank': 5}}},
 'd388a4fb-5bb6-4a8f-bc2f-3b5c201e7de2': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/porgy-and-bess/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Bess': {'label': 'Bess', 'rank': 2},
                                                           'Crown': {'label': 'Crown', 'rank': 3},
                                                           'Porgy': {'label': 'Porgy', 'rank': 1},
                                                           "Sportin' Life": {'label': "Sportin' Life",
                                                                             'rank': 4}}},
 'd4cf1544-ad65-46ad-a302-9dca09b8a552': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'5a9c48b1-db12-4c99-b320-7f712696dc6a': 1,
                                                         '886267e2-8483-4c20-b4ca-d2c3740c210f': 3,
                                                         'cd63fe0b-90ef-400b-8a2c-6763ed74c47a': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/turandot/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Calaf': {'label': 'Calaf', 'rank': 2},
                                                           'Liù': {'label': 'Liù', 'rank': 3},
                                                           'Timur': {'label': 'Timur', 'rank': 4},
                                                           'Turandot': {'label': 'Turandot', 'rank': 1}}},
 'dee18b4d-7021-54c2-9286-c2cde627b96a': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/orpheus-and-eurydice/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Amore': {'label': 'Amore', 'rank': 3},
                                                           'Euridice': {'label': 'Euridice', 'rank': 2},
                                                           'Orfeo': {'label': 'Orfeo', 'rank': 1}}},
 'e7484cde-f5e2-4718-985d-ccf5bc5d0428': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'0edd686a-1dc6-41c4-885a-f09268fc13d3': 4,
                                                         '35c07c59-43a1-4977-82d7-7f088eeccc7a': 2,
                                                         '67dcb7d0-de9d-4d40-b47b-1be0018a7dc1': 3,
                                                         '83ea504f-830c-4920-882c-3b72da39a913': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/carmen/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Carmen': {'label': 'Carmen', 'rank': 1},
                                                           'Don José': {'label': 'Don José', 'rank': 2},
                                                           'Escamillo': {'label': 'Escamillo', 'rank': 3},
                                                           'Escamillo, Toreador': {'label': 'Escamillo',
                                                                                   'rank': 3},
                                                           'Micaëla': {'label': 'Micaëla', 'rank': 4}}},
 'ef92b402-6305-4b37-9e3f-afa72f451ca7': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'3f311a33-ac40-4a31-83be-9f5b00950551': 2,
                                                         '4fea94ba-f958-447e-81f7-c68e16a07cf2': 3,
                                                         'd9edfded-d270-4612-be1b-8fb3ab8beabc': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/donizetti-la-fille-du-regiment-2026-2027/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Marie': {'label': 'Marie', 'rank': 1},
                                                           'Marie, junge Marketenderin': {'label': 'Marie',
                                                                                          'rank': 1},
                                                           'Sulpice': {'label': 'Sulpice', 'rank': 3},
                                                           'Sulpice, Sergeant': {'label': 'Sulpice',
                                                                                 'rank': 3},
                                                           'Tonio': {'label': 'Tonio', 'rank': 2},
                                                           'Tonio, junger Bauer': {'label': 'Tonio',
                                                                                   'rank': 2}}},
 'f5ea6d04-fb33-435a-9b4b-125dba1866b7': {'basis': 'Editorial short-schedule selection from official '
                                                   'story/presentation; only named central characters are '
                                                   'selected. Other roles remain unclassified. Exact source '
                                                   'spellings classify display only, never canonical '
                                                   'identity.',
                                          'characters': {'25bda5e1-07b7-4ffb-aaac-09a07b682e82': 2,
                                                         '51f2072f-2a0b-4925-b755-73348aa4ea06': 1,
                                                         'd3600f61-2a96-4f9f-9f9d-1c2bbc5747e5': 3,
                                                         'ea43d621-c561-4355-ba36-9c7c08568814': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/otello.1385835?event_date=17919066',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Desdemona': {'label': 'Desdemona', 'rank': 2},
                                                           'Iago': {'label': 'Jago', 'rank': 3},
                                                           'Jago': {'label': 'Jago', 'rank': 3},
                                                           'Otello': {'label': 'Otello', 'rank': 1}}},
 'fa281687-2e16-4e10-958b-9f6de14d61bc': {'basis': 'Editorial synopsis selection; unlisted roles remain '
                                                   'unclassified. Priority is for a short schedule, not a '
                                                   'universal supporting-role label. Source spellings are '
                                                   'display-only classification and never create/assign '
                                                   'canonical identity.',
                                          'characters': {'0a83208a-70f4-42b7-a752-a5a8d092c0c3': 5,
                                                         '236b0519-f761-4ceb-9d3a-dcb4b03cb97d': 1,
                                                         '3a6127e5-c8b3-4d68-ac37-35c41f959c07': 3,
                                                         '93c157e7-10c2-43fe-9dbc-083f5ea1e977': 4,
                                                         'f869c663-2d78-432c-85fd-fd9d0f5ebd1c': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/don-carlos/',
                                          'reviewed_on': '2026-10-22',
                                          'source_roles': {'Don Carlos': {'label': 'Don Carlos', 'rank': 1},
                                                           'Eboli': {'label': 'La princesse Eboli',
                                                                     'rank': 5},
                                                           'Elisabeth de Valois': {'label': 'Élisabeth de '
                                                                                            'Valois',
                                                                                   'rank': 2},
                                                           'Philippe II.': {'label': 'Philippe II',
                                                                            'rank': 3},
                                                           'Rodrigue': {'label': 'Rodrigue', 'rank': 4}}}}


# Reviewed against official stories and cast on 2026-10-29. Existing policies
# are preserved; these Work policies apply to every venue and performance.
WORK_CAST_POLICIES.update({'0d6b0faf-e33f-4e4e-bd13-028bff881cd0': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'ba130f7d-d7fd-5591-b0a7-c17e62aac7fc': 2,
                                                         'f3fb97bf-1a71-5434-9425-6743bfeb647f': 1,
                                                         'f99b6af3-517b-591d-aa14-e820415b44ac': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/haensel-und-gretel.1385736?event_date=17918235',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Die Knusperhexe': {'label': 'Die '
                                                                                        'Knusperhexe',
                                                                               'rank': 3},
                                                           'Gretel': {'label': 'Gretel', 'rank': 2},
                                                           'Hänsel': {'label': 'Hänsel', 'rank': 1}}},
 '10f5309c-7ec8-48d7-8350-9f27f39a6d73': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'0f376227-d716-40ad-b74f-bc3b482ed3f9': 1,
                                                         '424a993a-4321-44fc-b9a7-0d15c5d16baa': 4,
                                                         'a7c3033e-86e5-42d7-8bc9-1816e792fd71': 2,
                                                         'd53d1149-4786-4152-b518-f71c47446f5a': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.lesarts.com/es/programacion/c/1290-adriana-lecouvreur.html',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Adriana Lecouvreur': {'label': 'Adriana '
                                                                                           'Lecouvreur',
                                                                                  'rank': 1},
                                                           'La Principessa di Bouillon': {'label': 'La '
                                                                                                   'Principessa '
                                                                                                   'di '
                                                                                                   'Bouillon',
                                                                                          'rank': 3},
                                                           'Maurizio': {'label': 'Maurizio', 'rank': 2},
                                                           'Maurizio, Conte di Sassonia': {'label': 'Maurizio, '
                                                                                                    'Conte '
                                                                                                    'di '
                                                                                                    'Sassonia',
                                                                                           'rank': 2},
                                                           'Michonnet': {'label': 'Michonnet',
                                                                         'rank': 4},
                                                           'Princesa de Bouillon': {'label': 'Princesa '
                                                                                             'de '
                                                                                             'Bouillon',
                                                                                    'rank': 3}}},
 '34614acb-087a-4603-a4e2-8b57ae786a32': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'8a6271bc-3192-4736-b9be-48820ed12306': 2,
                                                         '8d623494-7dac-40d1-90b0-6391716a6c29': 5,
                                                         'b1839688-08f3-4e62-a264-f56d2f17833f': 1,
                                                         'cdbe4bf1-912a-46b9-a24e-d30dbbddf553': 4,
                                                         'cf455475-e4d2-4783-826e-ea455e09d0c4': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/saison-26-27/opera/katia-kabanova',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Boris': {'label': 'Boris', 'rank': 2},
                                                           'Kabanicha': {'label': 'Kabanicha',
                                                                         'rank': 3},
                                                           'Katia': {'label': 'Katia', 'rank': 1},
                                                           'Tichon': {'label': 'Tichon', 'rank': 4},
                                                           'Varvara': {'label': 'Varvara', 'rank': 5}}},
 '3d3bd914-7a54-4e98-bcb4-a1955127c2eb': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'4075ab0c-3d79-57aa-91b8-4c0a4489a67b': 1,
                                                         '777af374-f0a1-5925-b503-526a43e8feb5': 4,
                                                         'c21411de-b323-57d5-8b62-1497a1cf73fa': 3,
                                                         'cc90e9b1-04c3-5241-b88d-7d663c7ba449': 5,
                                                         'e8466704-7a7d-54ba-ad00-1bd2435e75aa': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/nabucco.1385815?event_date=17919011',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Abigaille': {'label': 'Abigaille',
                                                                         'rank': 2},
                                                           'Fenena': {'label': 'Fenena', 'rank': 4},
                                                           'Ismaele': {'label': 'Ismaele', 'rank': 5},
                                                           'Nabucco': {'label': 'Nabucco', 'rank': 1},
                                                           'Zaccaria': {'label': 'Zaccaria',
                                                                        'rank': 3}}},
 '4e0a910d-406d-50f7-b2f4-fe51cb8b763c': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-stuttgart.de/spielplan/kalender/der-miesepups/9680/',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Kucks': {'label': 'Kucks', 'rank': 2},
                                                           'Miesepups': {'label': 'Miesepups',
                                                                         'rank': 1}}},
 '4f51f3ac-3f0c-4591-9191-5c6735c33e9e': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper.de/stuecke/katja-kabanova/2027-01-30-1900-16200',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Boris': {'label': 'Boris', 'rank': 2},
                                                           'Kabanicha': {'label': 'Kabanicha',
                                                                         'rank': 3},
                                                           'Káťa': {'label': 'Káťa', 'rank': 1},
                                                           'Tichon': {'label': 'Tichon', 'rank': 4},
                                                           'Varvara': {'label': 'Varvara', 'rank': 5}}},
 '5f5d66e8-8e3f-47ae-a68c-bc1ee2338a73': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'1249f10b-af97-434b-b05c-ba7ba632fde9': 3,
                                                         '273457d2-06fb-4a2b-8421-fb39ec547bb0': 1,
                                                         'af4b2ceb-b23b-4354-8480-6e426df5465e': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper.de/stuecke/maria-stuarda/2026-12-23-1800-16171',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Elisabetta': {'label': 'Elisabetta',
                                                                          'rank': 2},
                                                           'Leicester': {'label': 'Leicester',
                                                                         'rank': 3},
                                                           'Maria Stuarda': {'label': 'Maria Stuarda',
                                                                             'rank': 1},
                                                           'Roberto, Graf Leicester': {'label': 'Roberto, '
                                                                                                'Graf '
                                                                                                'Leicester',
                                                                                       'rank': 3}}},
 '69e72a89-ecca-4725-b8d1-936adfe1a024': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'62e9960a-1deb-4b9b-abdb-f9e7e6605dfd': 1,
                                                         '6a242db1-7e16-4534-a0ea-6813047090a0': 1,
                                                         'b6377cdd-8340-4917-94c2-86671c33ecf1': 2,
                                                         'ef615ff6-cca0-41bf-8d45-214c6807e298': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.rbo.org.uk/production/duke-bluebeards-castle-the-rite-of-spring-in-concert',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Barbe-Bleue': {'label': 'Barbe-Bleue',
                                                                           'rank': 1},
                                                           'Bluebeard': {'label': 'Bluebeard',
                                                                         'rank': 1},
                                                           'Duke Bluebeard': {'label': 'Duke Bluebeard',
                                                                              'rank': 1},
                                                           'Judit': {'label': 'Judit', 'rank': 2},
                                                           'Judith': {'label': 'Judith', 'rank': 2}}},
 'b6fb8e68-537c-4d69-bfd7-550fde3df04c': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'35a18bfa-8484-53e5-8a35-76d44fb31fd2': 3,
                                                         '3a8ee500-28f4-5693-ae5f-a7b33e00d422': 1,
                                                         'a1b4e224-8da8-57ce-8aae-07f6ac438eaa': 4,
                                                         'ef88d5d5-d7c2-52f9-a4c0-a1904af4f012': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/pagliacci/',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Canio': {'label': 'Canio', 'rank': 1},
                                                           'Nedda': {'label': 'Nedda', 'rank': 2},
                                                           'Silvio': {'label': 'Silvio', 'rank': 4},
                                                           'Tonio': {'label': 'Tonio', 'rank': 3}}},
 'cbae154e-1883-4150-a99f-598bfd921ea0': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'0cd7350d-2951-5437-b594-d2d83d684979': 2,
                                                         '0fba69f6-20cd-5e3c-a25c-447213f810b7': 3,
                                                         '28071204-e488-5618-969e-f47c61fe82a6': 4,
                                                         'a1084a84-ed69-55d8-a004-6a8b12a203a2': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/lohengrin.1385795?event_date=17918958',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Elsa von Brabant': {'label': 'Elsa von '
                                                                                         'Brabant',
                                                                                'rank': 2},
                                                           'Friedrich von Telramund': {'label': 'Friedrich '
                                                                                                'von '
                                                                                                'Telramund',
                                                                                       'rank': 4},
                                                           'Lohengrin': {'label': 'Lohengrin',
                                                                         'rank': 1},
                                                           'Ortrud': {'label': 'Ortrud', 'rank': 3}}},
 'd2744f32-d954-5472-a2d9-2f0c4d2b7906': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'46778b09-423e-5115-92ce-05fa0968d55c': 2,
                                                         '4a13c653-4012-5128-83b6-e7052303ab2c': 3,
                                                         '5bf1e8fb-a8d3-5030-a47b-7aa6d16dd8b9': 1,
                                                         '8fb1e97a-55c2-50e0-b12e-bbb9fdb403c0': 6,
                                                         'bb208c1e-d582-50e3-a112-5ed8bf1a347a': 5,
                                                         'f0226cc1-b4da-5d01-91ce-63c49859a69c': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/nixon-in-china.1385484?event_date=17916157',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Chiang Chi’ing': {'label': 'Chiang Chi’ing',
                                                                              'rank': 5},
                                                           'Henry Kissinger': {'label': 'Henry '
                                                                                        'Kissinger',
                                                                               'rank': 6},
                                                           'Mao Zedong': {'label': 'Mao Zedong',
                                                                          'rank': 3},
                                                           'Pat Nixon': {'label': 'Pat Nixon',
                                                                         'rank': 2},
                                                           'Richard Nixon': {'label': 'Richard Nixon',
                                                                             'rank': 1},
                                                           'Zhou Enlai': {'label': 'Zhou Enlai',
                                                                          'rank': 4}}},
 'de5772af-254e-59e5-aa8a-09c907cd4124': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-cunning-little-vixen/',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Fuchs': {'label': 'Fuchs', 'rank': 3},
                                                           'Förster': {'label': 'Förster', 'rank': 2},
                                                           'Füchsin': {'label': 'Füchsin', 'rank': 1}}},
 'e7f4848e-6560-5708-8dd4-054627334e6a': {'basis': 'Reviewed editorial selection of central dramatic '
                                                   'roles from the official synopsis and cast. Shared '
                                                   'across venues; unlisted roles remain unclassified. '
                                                   'Source spellings classify display only, never '
                                                   'canonical identity or performer assignments.',
                                          'characters': {'09b3b40e-07c6-5288-ad6e-32b15bf71479': 2,
                                                         '30f13a47-660a-583f-861e-3264db3bb8e8': 3,
                                                         '8adcc6bf-9ec4-506a-8dc5-5e8f5cc48d34': 1,
                                                         'fdaa1fe9-6b35-5718-92e0-8326310af606': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.eno.org/operas/the-merry-widow/',
                                          'reviewed_on': '2026-10-29',
                                          'source_roles': {'Camille de Rosillon': {'label': 'Camille '
                                                                                            'de '
                                                                                            'Rosillon',
                                                                                   'rank': 4},
                                                           'Graf Danilo Danilowitsch': {'label': 'Graf '
                                                                                                 'Danilo '
                                                                                                 'Danilowitsch',
                                                                                        'rank': 2},
                                                           'Hanna Glawari': {'label': 'Hanna Glawari',
                                                                             'rank': 1},
                                                           'Valencienne': {'label': 'Valencienne',
                                                                           'rank': 3}}}})


# 2026-10-30 Scala: Work-level roles, independent of venue and date.
WORK_CAST_POLICIES.update({'475053d9-8d32-451e-baed-a7d950ebca2c': {'basis': 'Reviewed central dramatic roles from official production '
                                                   'synopsis and cast; source labels classify display only '
                                                   'and never assign identities or performers.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroallascala.org/en/season/2026-2027/opera/don-quichotte.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Don Quichotte': {'label': 'Don Quichotte',
                                                                             'rank': 1},
                                                           'Dulcinée': {'label': 'Dulcinée', 'rank': 2},
                                                           'Sancho Pança': {'label': 'Sancho Pança',
                                                                            'rank': 3}}},
 '8482965a-c819-47aa-808d-8407c86a8d31': {'basis': 'Reviewed central dramatic roles from official production '
                                                   'synopsis and cast; source labels classify display only '
                                                   'and never assign identities or performers.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroallascala.org/en/season/2026-2027/opera/the-rake-s-progress.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Anne Trulove': {'label': 'Anne Trulove',
                                                                            'rank': 2},
                                                           'Baba la Turca': {'label': 'Baba la Turca',
                                                                             'rank': 4},
                                                           'Nick Shadow': {'label': 'Nick Shadow', 'rank': 3},
                                                           'Tom Rakewell': {'label': 'Tom Rakewell',
                                                                            'rank': 1}}},
 'a2657822-cdaf-4750-bfbf-f3daa762244e': {'basis': 'Reviewed central dramatic roles from official production '
                                                   'synopsis and cast; source labels classify display only '
                                                   'and never assign identities or performers.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroallascala.org/en/season/2026-2027/opera/anna-bolena.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Anna Bolena': {'label': 'Anna Bolena', 'rank': 1},
                                                           'Enrico VIII': {'label': 'Enrico VIII', 'rank': 2},
                                                           'Giovanna Seymour': {'label': 'Giovanna Seymour',
                                                                                'rank': 4},
                                                           'Lord Percy': {'label': 'Lord Percy', 'rank': 3}}},
 'e2661dab-fa7d-42bb-92b5-e3ca9dae0ea9': {'basis': 'Reviewed central dramatic roles from official production '
                                                   'synopsis and cast; source labels classify display only '
                                                   'and never assign identities or performers.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroallascala.org/en/season/2026-2027/opera/i-puritani.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Arturo': {'label': 'Arturo', 'rank': 2},
                                                           'Elvira': {'label': 'Elvira', 'rank': 1},
                                                           'Giorgio': {'label': 'Giorgio', 'rank': 4},
                                                           'Riccardo': {'label': 'Riccardo', 'rank': 3}}}})

# 2026-10-30 cross-venue: reviewed existing Work-role slots.
WORK_CAST_POLICIES.update({'146036ca-40eb-48d7-b8f8-b61322c77989': {'basis': 'Reviewed main dramatic roles from official synopsis and '
                                                   'current global Work-role slots; source labels classify '
                                                   'display only.',
                                          'characters': {'511a351f-4587-45c4-8fb9-1e32a4f34d91': 1,
                                                         '695e09c4-52b6-40cd-bf36-81ab77330864': 3,
                                                         'ad2d9ea4-f5c3-4bc5-8a5c-5ab9b0633d10': 4,
                                                         'd9d567ef-8cc7-4620-9e0f-0783414b9172': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroma.it/spettacoli/la-rondine/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Lisette': {'label': 'Lisette', 'rank': 3},
                                                           'Magda': {'label': 'Magda', 'rank': 1},
                                                           'Prunier': {'label': 'Prunier', 'rank': 4},
                                                           'Ruggero': {'label': 'Ruggero', 'rank': 2}}},
 '7f552f18-d0bf-4ad7-bb2c-812ae1e05821': {'basis': 'Reviewed main dramatic roles from official synopsis and '
                                                   'current global Work-role slots; source labels classify '
                                                   'display only.',
                                          'characters': {'21a197ed-eaa8-4a9a-9bc3-23cedfaecf61': 2,
                                                         '3dbdb6c3-eea1-4e8a-8e8c-cd1c6fde6193': 3,
                                                         '641fd3f5-d90c-42ff-9ad3-63579db878fb': 1,
                                                         'c63b9002-bda1-4a05-8a76-ff7c8f595c26': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.metopera.org/user-information/synopses-archive/Macbeth',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Banco': {'label': 'Banco', 'rank': 4},
                                                           'Banquo': {'label': 'Banquo', 'rank': 4},
                                                           'Lady Macbeth': {'label': 'Lady Macbeth',
                                                                            'rank': 2},
                                                           'Macbeth': {'label': 'Macbeth', 'rank': 1},
                                                           'Macduff': {'label': 'Macduff', 'rank': 3}}},
 '93072805-d1ae-472c-a7c9-3a2237962b97': {'basis': 'Reviewed main dramatic roles from official synopsis and '
                                                   'current global Work-role slots; source labels classify '
                                                   'display only.',
                                          'characters': {'99e60842-5f16-46c7-81c9-3e5fb61fefb5': 3,
                                                         'b55dd05a-1f72-401b-a0f9-a7659f26c6e6': 2,
                                                         'cd8ae26d-1d7c-4b03-89ff-1fd69e206222': 4,
                                                         'df76c0f8-9e29-417e-8742-5c870c72c313': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.opernhaus.ch/spielplan/kalendarium/die-fledermaus-1/2026-2027',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Adele': {'label': 'Adele', 'rank': 3},
                                                           'Gabriel von Eisenstein': {'label': 'Gabriel von '
                                                                                               'Eisenstein',
                                                                                      'rank': 2},
                                                           'Prinz Orlofsky': {'label': 'Prinz Orlofsky',
                                                                              'rank': 4},
                                                           'Rosalinde': {'label': 'Rosalinde', 'rank': 1}}},
 'f7dad73d-91fe-4e8c-8e7f-86615b286900': {'basis': 'Reviewed main dramatic roles from official synopsis and '
                                                   'current global Work-role slots; source labels classify '
                                                   'display only.',
                                          'characters': {'4c16623a-da4c-4323-ba93-cc166c3cf4b1': 1,
                                                         'b7d2efff-4fd1-48f7-9170-9b46a29130b4': 3,
                                                         'c177032c-2274-466b-af2f-fc89497faf03': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://upstream.wiener-staatsoper.at/en/calendar/detail/andrea-chenier/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Andrea Chénier': {'label': 'Andrea Chénier',
                                                                              'rank': 1},
                                                           'Carlo Gérard': {'label': 'Carlo Gérard',
                                                                            'rank': 3},
                                                           'Maddalena di Coigny': {'label': 'Maddalena di '
                                                                                            'Coigny',
                                                                                   'rank': 2}}}})

# 2026-10-30: further reviewed global works.
WORK_CAST_POLICIES.update({'1a063e71-a8ab-4d4d-b45d-55f07897849c': {'basis': 'Reviewed principal roles against official synopsis and '
                                                   'existing global work role slots. Source labels classify '
                                                   'display only.',
                                          'characters': {'051d1f8e-edfc-4315-9dd5-089d4907c667': 1,
                                                         '5c2b5d88-6493-4a9e-90ee-2ae0954c23af': 3,
                                                         '9c946593-0eea-4e26-82c2-c2e39323f059': 2,
                                                         'a507acc6-9f26-4aef-a30e-f321fe7dcd6d': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.metopera.org/user-information/old-seasons/2021-22-season/die-meistersinger-von-nurnberg/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Eva, Pogners Tochter': {'label': 'Eva, Pogners '
                                                                                             'Tochter',
                                                                                    'rank': 3},
                                                           'Hans Sachs, Schuster': {'label': 'Hans Sachs, '
                                                                                             'Schuster',
                                                                                    'rank': 1},
                                                           'Sixtus Beckmesser, Schreiber': {'label': 'Sixtus '
                                                                                                     'Beckmesser, '
                                                                                                     'Schreiber',
                                                                                            'rank': 4},
                                                           'Walther von Stolzing, ein junger Ritter aus Franken': {'label': 'Walther '
                                                                                                                            'von '
                                                                                                                            'Stolzing, '
                                                                                                                            'ein '
                                                                                                                            'junger '
                                                                                                                            'Ritter '
                                                                                                                            'aus '
                                                                                                                            'Franken',
                                                                                                                   'rank': 2}}},
 '242085af-163c-42de-a7a5-7da206bf2835': {'basis': 'Reviewed principal roles against official synopsis and '
                                                   'existing global work role slots. Source labels classify '
                                                   'display only.',
                                          'characters': {'38b0da68-29a6-5740-aee7-5091814cdd73': 2,
                                                         'e811ef64-1087-5183-8f66-114c1adabc88': 3,
                                                         'e8a4430b-99b3-5cef-a347-6fe308a0270e': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://teatrodelazarzuela.inaem.gob.es/es/proyectos-didacticos/proyecto-zarza/historia-de-la-verbena',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Don Hilarión': {'label': 'Don Hilarión',
                                                                            'rank': 3},
                                                           'Julián': {'label': 'Julián', 'rank': 1},
                                                           'Susana': {'label': 'Susana', 'rank': 2}}},
 '852d9462-99a5-48a3-95e1-7914a1540031': {'basis': 'Reviewed principal roles against official synopsis and '
                                                   'existing global work role slots. Source labels classify '
                                                   'display only.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/en/season-26-27/opera/idomeneo',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Elettra': {'label': 'Elettra', 'rank': 4},
                                                           'Idamante': {'label': 'Idamante', 'rank': 2},
                                                           'Idomeneo': {'label': 'Idomeneo', 'rank': 1},
                                                           'Ilia': {'label': 'Ilia', 'rank': 3}}},
 'fb7c48b8-209f-4bac-91c6-f70e6d25435c': {'basis': 'Reviewed principal roles against official synopsis and '
                                                   'existing global work role slots. Source labels classify '
                                                   'display only.',
                                          'characters': {'38b9c245-683a-508f-b1ca-fb398fe869dc': 4,
                                                         '4574961c-baab-54be-a657-c66b6a5ab809': 2,
                                                         'dfdf8bf9-1f61-5868-827b-f7c189f3d84a': 1,
                                                         'fcaa0b15-8cde-5e64-8c36-5cff2324e80d': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.metopera.org/user-information/synopses-archive/cav-pag',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Alfio': {'label': 'Alfio', 'rank': 3},
                                                           'Lola': {'label': 'Lola', 'rank': 4},
                                                           'Santuzza': {'label': 'Santuzza', 'rank': 1},
                                                           'Turiddu': {'label': 'Turiddu', 'rank': 2}}}})
