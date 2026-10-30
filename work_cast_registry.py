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

# 2026-10-30 remaining global inventory: reviewed source-backed principal roles.
WORK_CAST_POLICIES.update({'03789442-bc3d-5651-bbfd-1afa3be8c521': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'07cbef83-30db-5ddb-ad52-a444d0b08cc0': 3,
                                                         '4e753d50-ebdc-5d5c-872d-bd6615efc3ae': 2,
                                                         'ef26ab41-0e61-56b4-bbcd-2baff7986411': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/le-postillon-de-lonjumeau_2/?id_datum=4965',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Chapelou': {'label': 'Chapelou', 'rank': 1},
                                                           'Madeleine': {'label': 'Madeleine', 'rank': 2},
                                                           'Marquis de Corcy': {'label': 'Marquis de Corcy',
                                                                                'rank': 3}}},
 '0c6fadd4-2189-45af-8f76-29f885fde07f': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'0dc27356-d56d-5bc8-af62-77edce2321fd': 3,
                                                         '13ffcdca-0957-5238-9b59-c32fc41baa7b': 4,
                                                         'df0f60d6-0206-5b9d-b9c4-094b3bc4f294': 1,
                                                         'ef1ee9cb-67e2-5cf9-a886-897ee8a5ec5b': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/mazeppa/?id_datum=4795',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Andrej': {'label': 'Andrej', 'rank': 3},
                                                           'Kotschubej': {'label': 'Kotschubej', 'rank': 4},
                                                           'Maria': {'label': 'Maria', 'rank': 2},
                                                           'Mazeppa': {'label': 'Mazeppa', 'rank': 1}}},
 '12935dde-8f56-5127-bb55-c28ea18e1103': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'b21b93dd-30c8-5290-b384-63f140945e56': 1,
                                                         'd1d33e06-5e0d-5e27-8e5d-f340998aeaf5': 2,
                                                         'eb36b8c3-1068-5f36-a029-b907f054bb4e': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/skaterherz/?id_datum=4895',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Boyd Bruckmann': {'label': 'Boyd Bruckmann',
                                                                              'rank': 2},
                                                           'Elias Heuziger': {'label': 'Elias Heuziger',
                                                                              'rank': 1},
                                                           'Mathilde Heuziger': {'label': 'Mathilde Heuziger',
                                                                                 'rank': 3}}},
 '17a06497-38c5-5d90-aee4-e5172485a500': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'fe082094-f7c2-5974-980c-00be143e7ec2': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.br-musica-viva.de/konzerte/brso-mit-sir-simon-rattle/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Woman': {'label': 'Woman', 'rank': 1},
                                                           'Zabelle': {'label': 'Zabelle', 'rank': 2}}},
 '1bb70185-77cb-561b-8fc8-045c036f082c': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'2692c145-f0f9-5bb9-b220-c8d27de33618': 1,
                                                         '6dc4e3f3-728e-582d-92a3-58554e5c54e1': 5,
                                                         'a002e666-38b8-54db-9c6f-3f08eb1c6c5b': 3,
                                                         'bacd276b-496d-5ad3-8f76-18cf7b5c8620': 4,
                                                         'f547c601-7716-5239-bbdd-75543689a910': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/dialogues-des-carmelites_2/?id_datum=4984',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Blanche de la Force': {'label': 'Blanche de la Force',
                                                                                   'rank': 1},
                                                           'Madame Lidoine': {'label': 'Madame Lidoine',
                                                                              'rank': 3},
                                                           'Madame de Croissy': {'label': 'Madame de Croissy',
                                                                                 'rank': 2},
                                                           'Mère Marie de l’incarnation': {'label': 'Mère Marie '
                                                                                                    'de '
                                                                                                    'l’incarnation',
                                                                                           'rank': 4},
                                                           'Sœur Constance de St. Denis': {'label': 'Sœur '
                                                                                                    'Constance de '
                                                                                                    'St. Denis',
                                                                                           'rank': 5}}},
 '21821df6-ebd5-4be4-8abe-8a6865f055dd': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://teatrodelazarzuela.inaem.gob.es/es/temporada/lirica-2026-2027/los-gavilanes',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Adriana': {'label': 'Adriana', 'rank': 2},
                                                           'Gustavo': {'label': 'Gustavo', 'rank': 4},
                                                           'Juan': {'label': 'Juan', 'rank': 1},
                                                           'Rosaura': {'label': 'Rosaura', 'rank': 3}}},
 '222c330a-8151-4996-95bb-6b34a7bf2cf6': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.opernhaus.ch/en/spielplan/calendar/ascanio-in-alba/2026-2027/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Aceste': {'label': 'Aceste', 'rank': 4},
                                                           'Ascanio': {'label': 'Ascanio', 'rank': 1},
                                                           'Silvia': {'label': 'Silvia', 'rank': 2},
                                                           'Venere': {'label': 'Venere', 'rank': 3}}},
 '23079899-ba70-418c-919c-c503a6cba28f': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.elbphilharmonie.de/de/programm/ndr-elbphilharmonie-orchester-mdr-rundfunkchor-alan-gilbert/27858',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Iokaste': {'label': 'Iokaste', 'rank': 2},
                                                           'Kreon': {'label': 'Kreon', 'rank': 3},
                                                           'Oedipus': {'label': 'Oedipus', 'rank': 1},
                                                           'Teiresias': {'label': 'Teiresias', 'rank': 4}}},
 '23564414-ad2b-5b29-91c9-af7fb349f92b': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/porsile-spartacus/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Gianisbe': {'label': 'Gianisbe', 'rank': 3},
                                                           'Licinio': {'label': 'Licinio', 'rank': 4},
                                                           'Spartacus': {'label': 'Spartacus', 'rank': 1},
                                                           'Vetturia': {'label': 'Vetturia', 'rank': 2}}},
 '2531c8e4-a707-58bf-adb7-9d481cf651a6': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'031dfe81-6d95-57b7-a818-7bdcef9f9023': 3,
                                                         'bded8430-606e-570c-8b45-0fa4458d8a63': 2,
                                                         'c875a2f4-173d-501e-a625-37183c090884': 4,
                                                         'dfad6774-018c-5137-90e2-40dac0920e7a': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/warten-auf-heute_2/?id_datum=4803',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Ehefrau': {'label': 'Ehefrau', 'rank': 1},
                                                           'Ehemann': {'label': 'Ehemann', 'rank': 2},
                                                           'Freundin': {'label': 'Freundin', 'rank': 3},
                                                           'Sänger': {'label': 'Sänger', 'rank': 4}}},
 '26fcfc15-deb6-5171-b717-dde07388c323': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/hasse-marc-antoine-et-cleopatre/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Cléopâtre': {'label': 'Cléopâtre', 'rank': 2},
                                                           'Marc-Antoine': {'label': 'Marc-Antoine', 'rank': 1}}},
 '27c95ae0-c9c6-4ef6-ba7a-39cfdc7c9e58': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'00dcebb0-c048-42cb-8cef-7c8623e077f9': 4,
                                                         '263895e3-d7ed-4869-b0e4-5422981a524e': 1,
                                                         'ddb023db-695d-4d7f-afeb-b5300ad9d055': 3,
                                                         'fb578a42-4b0e-4264-b1fd-11ffbfa997fd': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroreal.es/en/show/gioconda',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Barnaba': {'label': 'Barnaba', 'rank': 4},
                                                           'Enzo Grimaldo': {'label': 'Enzo Grimaldo', 'rank': 2},
                                                           'La Gioconda': {'label': 'La Gioconda', 'rank': 1},
                                                           'Laura Adorno': {'label': 'Laura Adorno', 'rank': 3}}},
 '284d1a25-2ab1-583f-866b-72adc6fb5037': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'8acc6082-297e-5b7b-85da-67a72edd092a': 4,
                                                         'c407278d-cf6f-5b3e-baed-9a135ede50e3': 1,
                                                         'c810206c-15b7-570e-9202-4e7427423b37': 3,
                                                         'd23bbd62-129a-5d9d-8abc-df305c90b2d5': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.semperoper.de/spielplan/stuecke/stid/florentiner-hut/62710.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Anaide': {'label': 'Anaide', 'rank': 3},
                                                           'Beaupertuis': {'label': 'Beaupertuis', 'rank': 4},
                                                           'Elena': {'label': 'Elena', 'rank': 2},
                                                           'Fadinard': {'label': 'Fadinard', 'rank': 1}}},
 '2dc9de26-6060-5c26-9b9e-f6386c70a2e2': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'75e79fe1-7463-5660-9c28-e72898434b1b': 1,
                                                         '967d4cb8-ef12-556e-bcc1-645ae91924ae': 2,
                                                         'c3b5d1b0-9da8-56dc-a73c-7db0696e7b01': 4,
                                                         'fc31abd6-260c-5ce9-bbe5-4d58f053b737': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/ottone/?id_datum=4815',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Adelberto': {'label': 'Adelberto', 'rank': 4},
                                                           'Gismonda': {'label': 'Gismonda', 'rank': 3},
                                                           'Ottone': {'label': 'Ottone', 'rank': 1},
                                                           'Teofane': {'label': 'Teofane', 'rank': 2}}},
 '31ee6859-53a9-51b0-95a1-e8b4b97ff51c': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'12d05eb6-9c0f-5279-80e3-9cb129d79e6e': 1,
                                                         '32b49856-aa95-52c2-a441-effa9b14c5fe': 3,
                                                         '95570652-b4cb-5915-b94b-c80bf701c422': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.brso.de/konzerte/sir-simon-rattle-pelleas-et-melisande/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Arkel': {'label': 'Arkel', 'rank': 4},
                                                           'Golaud': {'label': 'Golaud', 'rank': 3},
                                                           'Mélisande': {'label': 'Mélisande', 'rank': 2},
                                                           'Pelléas': {'label': 'Pelléas', 'rank': 1}}},
 '4141ea8b-e7be-5578-a6f3-3cf9cfec88e3': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'56eb5f79-8a8d-597c-a59a-b365b5c4f65f': 1,
                                                         'e76dad6d-75af-5f5c-9aba-5dfc1072ca35': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.semperoper.de/spielplan/stuecke/stid/schneewitte/60824.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Schneewitte': {'label': 'Schneewitte', 'rank': 1},
                                                           'Stiefmutter': {'label': 'Stiefmutter', 'rank': 2}}},
 '425292f8-66ea-56c3-8816-c9d1821554d8': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'0149c01b-85d3-549c-bca6-df7b850ef02c': 2,
                                                         '76b96d32-a34a-5e5a-81cc-569095d342ae': 3,
                                                         'e41ee7a1-3c7d-53e2-b1c0-587c125c2d90': 4,
                                                         'fe389302-bb3e-527d-aff3-95079bf054e5': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.semperoper.de/spielplan/stuecke/stid/rienzi/62907.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Adriano': {'label': 'Adriano', 'rank': 3},
                                                           'Irene': {'label': 'Irene', 'rank': 2},
                                                           'Rienzi': {'label': 'Rienzi', 'rank': 1},
                                                           'Steffano Colonna': {'label': 'Steffano Colonna',
                                                                                'rank': 4}}},
 '42f5cb1e-83a4-4635-9e33-e5fad59777f7': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'24ecbc82-8b31-492d-9821-43321f60d80e': 1,
                                                         '76f91069-9f95-48f3-9751-8a051699c22e': 3,
                                                         '99b97823-a7d8-435c-b2dd-39379d3ee6b7': 4,
                                                         'e2720712-c020-47a8-8e03-db9731705778': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroreal.es/en/show/richard-first-king-england',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Costanza': {'label': 'Costanza', 'rank': 2},
                                                           'Isacio': {'label': 'Isacio', 'rank': 4},
                                                           'Pulcheria': {'label': 'Pulcheria', 'rank': 3},
                                                           'Riccardo': {'label': 'Riccardo', 'rank': 1}}},
 '481e2d19-7f7d-4f9e-a4c7-3cc8bba63895': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://teatrodelazarzuela.inaem.gob.es/es/temporada/lirica-2026-2027/la-bruja',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Blanca': {'label': 'Blanca', 'rank': 1},
                                                           'Leonardo': {'label': 'Leonardo', 'rank': 2},
                                                           'Rosalía': {'label': 'Rosalía', 'rank': 3},
                                                           'Tomillo': {'label': 'Tomillo', 'rank': 4}}},
 '4aa00908-1beb-50aa-83c3-36c35099fed6': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'295fa005-0661-5af2-b266-f80f3f7b89dc': 4,
                                                         '5adf8111-4ee8-5f6b-97fa-46632871ec79': 1,
                                                         '6d363315-1fb3-588c-b03a-8d8055ca04e6': 3,
                                                         'abe82217-53cd-5d36-8f03-66c0e6fc5eba': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/la-fiamma/?id_datum=4938',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Basilio': {'label': 'Basilio', 'rank': 3},
                                                           'Donello': {'label': 'Donello', 'rank': 2},
                                                           'Eudossia': {'label': 'Eudossia', 'rank': 4},
                                                           'Silvana': {'label': 'Silvana', 'rank': 1}}},
 '4b245901-dd06-4e24-8bf6-0a58b882c794': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'00a03a86-ec0b-4872-bd50-defca07d7e58': 1,
                                                         '61263022-56c3-4101-b824-7a3069f33a3f': 4,
                                                         'd4f28e1f-9da7-4623-b3a4-7304a7197fd8': 3,
                                                         'dda24c25-024a-4fad-aeec-e214bd3e3ba4': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.wiener-staatsoper.at/en/calendar/detail/pique-dame/2027-03-12/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Gräfin': {'label': 'Gräfin', 'rank': 3},
                                                           'Hermann': {'label': 'Hermann', 'rank': 1},
                                                           'Jeletzki': {'label': 'Jeletzki', 'rank': 4},
                                                           'Lisa': {'label': 'Lisa', 'rank': 2}}},
 '4f7c7b2e-928b-4b18-b628-1f6d4a7adf22': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/la-forza-del-destino.1385519?event_date=17916330',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Alvaro': {'label': 'Don Alvaro', 'rank': 2},
                                                           'Don Alvaro': {'label': 'Don Alvaro', 'rank': 2},
                                                           'Don Carlo': {'label': 'Don Carlos di Vargas',
                                                                         'rank': 3},
                                                           'Don Carlos di Vargas': {'label': 'Don Carlos di '
                                                                                             'Vargas',
                                                                                    'rank': 3},
                                                           'Donna Leonora': {'label': 'Donna Leonora', 'rank': 1},
                                                           'Leonora': {'label': 'Donna Leonora', 'rank': 1},
                                                           'Preziosilla': {'label': 'Preziosilla', 'rank': 4}}},
 '50edbad5-9e58-4b01-b0a6-e1c760973d3e': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'1798067c-dd33-4188-90dd-cfedad76a7ef': 2,
                                                         '1f59e4f2-85fb-4ccf-be35-f3424047eb0e': 3,
                                                         '3363df7d-e1d4-4f39-aab6-1fbf79ca5ba9': 4,
                                                         '6ac0889d-dc96-481c-9456-25d9b6669052': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.palaumusica.cat/es/dido-y-eneas-de-purcell_1623828',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Belinda': {'label': 'Belinda', 'rank': 3},
                                                           'Dido': {'label': 'Dido', 'rank': 1},
                                                           'Enees': {'label': 'Aeneas', 'rank': 2},
                                                           'Hechicera': {'label': 'Sorceress', 'rank': 4}}},
 '5159aa2c-f32e-5739-86bb-7c2d8b34ba56': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'c0e414a5-2746-59f9-83f7-666b59243400': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.semperoper.de/spielplan/stuecke/stid/gold/62711.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Jacob': {'label': 'Jacob', 'rank': 1}}},
 '51a41546-6a5a-4646-bc0a-aea226e4856d': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'2981cfe5-3e91-4cf8-af94-ec7bf8f04884': 3,
                                                         'cd6d8dc6-f026-489a-a98a-88ca97c59270': 1,
                                                         'dbfa3626-f998-4357-8ed0-04c89e44abb5': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.barbican.org.uk/whats-on/2027/event/hector-berliozs-the-damnation-of-faust',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Faust': {'label': 'Faust', 'rank': 1},
                                                           'Marguerite': {'label': 'Marguerite', 'rank': 2},
                                                           'Mephistopheles': {'label': 'Méphistophélès',
                                                                              'rank': 3},
                                                           'Méphistophélès': {'label': 'Méphistophélès',
                                                                              'rank': 3}}},
 '52a938d2-16b6-4428-9c57-923af252cda2': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'6ee11e5f-d47d-47a2-aa8b-e7f927544658': 4,
                                                         '7162fed3-af7b-45e0-8a62-074cc9a633ac': 2,
                                                         '89a98dd3-e9b9-4964-8445-c8736d14618e': 1,
                                                         'e8208ce7-241f-4299-b83b-3385ff3d706d': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://philharmoniedeparis.fr/fr/activite/opera-en-concert/29321-jean-philippe-rameau-hippolyte-et-aricie?itemId=145780',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Aricie': {'label': 'Aricie', 'rank': 2},
                                                           'Hippolyte': {'label': 'Hippolyte', 'rank': 1},
                                                           'Phèdre': {'label': 'Phèdre', 'rank': 3},
                                                           'Thésée': {'label': 'Thésée', 'rank': 4}}},
 '56ac40ee-15dc-5d5a-9cf4-9ce6958f68d7': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'82f8e2d4-73d4-56d0-bce8-59ff6658036b': 2,
                                                         'ead3854e-5ceb-56bd-8114-e3ac3c1f6810': 3,
                                                         'ff4760ef-0978-5772-a52d-fd29d6dc3d81': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.brso.de/konzerte/sir-simon-rattle-brso-akademie-3/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Don Quijote': {'label': 'Don Quijote', 'rank': 3},
                                                           'Maese Pedro': {'label': 'Maese Pedro', 'rank': 2},
                                                           'Trujamán': {'label': 'Trujamán', 'rank': 1}}},
 '5a0800d5-a998-514f-80f4-78865ee17c32': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-stuttgart.de/spielplan/kalender/alceste/9543/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Admete': {'label': 'Admète', 'rank': 2},
                                                           'Admète': {'label': 'Admète', 'rank': 2},
                                                           'Alceste': {'label': 'Alceste', 'rank': 1}}},
 '6039838c-42a0-517c-8089-3dcc15bee305': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'03222702-e38e-5bec-a1a6-5076d76a6455': 1,
                                                         '4812b1eb-0b56-593b-bbea-5457236352da': 2,
                                                         '9277f651-f1dd-527a-b896-41849cb5e65b': 4,
                                                         'ca4f81cd-6752-56c5-8bfb-a72ed95f52fe': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.semperoper.de/spielplan/stuecke/stid/wildschuetz/60553.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Baculus': {'label': 'Baculus', 'rank': 1},
                                                           'Baron Kronthal': {'label': 'Baron Kronthal',
                                                                              'rank': 4},
                                                           'Baronin Freimann': {'label': 'Baronin Freimann',
                                                                                'rank': 3},
                                                           'Gretchen': {'label': 'Gretchen', 'rank': 2}}},
 '6062d013-247a-5c05-ab99-86c0c953c975': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.komische-oper-berlin.de/spielplan/kalender/2027-03/der-goldene-hahn/1291/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Astrologe': {'label': 'Der Astrologe', 'rank': 3},
                                                           'Der Astrologe': {'label': 'Der Astrologe', 'rank': 3},
                                                           'Die Königin von Schemacha': {'label': 'Die Königin '
                                                                                                  'von Schemacha',
                                                                                         'rank': 2},
                                                           'Dodon': {'label': 'Dodon', 'rank': 1},
                                                           'Königin von Schemacha': {'label': 'Die Königin von '
                                                                                              'Schemacha',
                                                                                     'rank': 2}}},
 '6102804a-7c9b-418a-b804-e48bc54b4860': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.concertgebouw.nl/concerten/43714214-cecilia-bartoli-celestial-harmonies---music-from-heaven-and-earth',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Ino': {'label': 'Ino', 'rank': 4},
                                                           'Juno': {'label': 'Juno', 'rank': 3},
                                                           'Jupiter': {'label': 'Jupiter', 'rank': 2},
                                                           'Semele': {'label': 'Semele', 'rank': 1}}},
 '62792d47-7e4c-4b8d-8e59-1d8dfa51f6ed': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'148023bb-493b-4f45-95f3-ba40b69a797d': 2,
                                                         '2e995dad-ec3d-4b90-a02b-53f1b83a8c9b': 3,
                                                         'a0bd00b5-30f3-41b5-a174-993951570f6d': 1,
                                                         'ea01de73-e10d-4a66-aec9-db9d2b7993df': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroreal.es/en/show/mitridate',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Farnace': {'label': 'Farnace', 'rank': 3},
                                                           'Laodice': {'label': 'Laodice', 'rank': 2},
                                                           'Mitridate': {'label': 'Mitridate', 'rank': 1},
                                                           'Tigrane': {'label': 'Tigrane', 'rank': 4}}},
 '69dbb351-1792-45a5-9e28-4005f8be6050': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'273befc0-d549-54fe-922b-b89f8d65789d': 1,
                                                         '3fdbf608-3271-5da6-9a5e-d2b14134f284': 4,
                                                         '47e555ee-08c3-5786-b09d-a8af92fbe94f': 2,
                                                         '488695ae-6dcb-52fe-b056-6394703ec229': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/alcina_2/?id_datum=4889',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Alcina': {'label': 'Alcina', 'rank': 1},
                                                           'Bradamante': {'label': 'Bradamante', 'rank': 3},
                                                           'Morgana': {'label': 'Morgana', 'rank': 4},
                                                           'Ruggiero': {'label': 'Ruggiero', 'rank': 2}}},
 '6dec4141-6680-53c5-b308-00aae6066dd8': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'bf7997e1-52f1-5ed3-b040-2c8d35e3dc73': 2,
                                                         'f0d543af-63de-5b63-bddf-42d559befdff': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/battaglia-die-frauen-von-palermo/?id_datum=4977',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Eine junge Frau, Letizias Alter Ego': {'label': 'Eine '
                                                                                                            'junge '
                                                                                                            'Frau, '
                                                                                                            'Letizias '
                                                                                                            'Alter '
                                                                                                            'Ego',
                                                                                                   'rank': 2},
                                                           'Letizia Battaglia': {'label': 'Letizia Battaglia',
                                                                                 'rank': 1}}},
 '7462644c-2cb5-429b-85a2-c2ea9735f48d': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'13afa7b6-861e-4779-81e0-b1a30325cf5c': 2,
                                                         '1b23d64d-1e9d-49c6-8a02-71d4bd9a30d9': 3,
                                                         'c7d23051-34f9-4db5-aab8-ce9bc8fe01af': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroreal.es/en/show/blood-wedding',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Bride': {'label': 'Bride', 'rank': 1},
                                                           'Groom': {'label': 'Groom', 'rank': 2},
                                                           'Leonardo': {'label': 'Leonardo', 'rank': 3}}},
 '7b3158f8-a80f-57d6-81f6-954fb36b42b8': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/salieri-tarare/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Altamort': {'label': 'Altamort', 'rank': 4},
                                                           'Astasie': {'label': 'Astasie', 'rank': 2},
                                                           'Atar': {'label': 'Atar', 'rank': 3},
                                                           'Tarare': {'label': 'Tarare', 'rank': 1}}},
 '7badf1e3-d71e-582b-a117-7bde542f459b': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'339692cd-8d8e-5cbd-ac22-8b02d4c84a39': 1,
                                                         '6d39adbd-8f7f-5aaa-98c3-99d4b36e4746': 2,
                                                         'e9942460-d959-5f02-af80-5a196c51f972': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/tancredi_2/?id_datum=4823',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Amenaide': {'label': 'Amenaide', 'rank': 2},
                                                           'Argirio': {'label': 'Argirio', 'rank': 3},
                                                           'Tancredi': {'label': 'Tancredi', 'rank': 1}}},
 '800bff67-f1ed-4d4c-87a5-c14b9e82323c': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.lamonnaiedemunt.be/en/program/3930-romeo-et-juliette',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Frère Laurent': {'label': 'Frère Laurent', 'rank': 3},
                                                           'Juliette': {'label': 'Juliette', 'rank': 2},
                                                           'Mercutio': {'label': 'Mercutio', 'rank': 4},
                                                           'Romeo': {'label': 'Roméo', 'rank': 1},
                                                           'Roméo': {'label': 'Roméo', 'rank': 1}}},
 '85558edc-9ca9-5bd6-9f91-73597938fa4c': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'0f619581-0c83-5761-a971-cd443baa431c': 3,
                                                         '4b9fc2c5-8533-522c-a4bc-ff94408141f5': 1,
                                                         '8095995d-9132-5dee-b814-7d8a09220ae0': 2,
                                                         'cc605bd8-d6d6-53ab-8ce9-177d3c790455': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.semperoper.de/spielplan/stuecke/stid/leonora/62892.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Don Fernando': {'label': 'Don Fernando', 'rank': 3},
                                                           'Florestano': {'label': 'Florestano', 'rank': 2},
                                                           'Leonora': {'label': 'Leonora', 'rank': 1},
                                                           'Rocco': {'label': 'Rocco', 'rank': 4}}},
 '891ae003-0cc5-59e2-a1f0-185dca860123': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-stuttgart.de/spielplan/kalender/der-spieler/9735/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Alexej': {'label': 'Alexej', 'rank': 1},
                                                           'Babulenka': {'label': 'Babulenka', 'rank': 4},
                                                           'Der General': {'label': 'Der General', 'rank': 3},
                                                           'General': {'label': 'Der General', 'rank': 3},
                                                           'Polina': {'label': 'Polina', 'rank': 2}}},
 '8b5f4313-9a07-49ff-a188-7c06e688517c': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.wiener-staatsoper.at/en/calendar/detail/eine-florentinische-tragoedie-herzog-blaubarts-burg/2026-09-30/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Bianca': {'label': 'Bianca', 'rank': 2},
                                                           'Guido': {'label': 'Guido Bardi', 'rank': 3},
                                                           'Guido Bardi': {'label': 'Guido Bardi', 'rank': 3},
                                                           'Simone': {'label': 'Simone', 'rank': 1}}},
 '8b994ce5-e556-47fd-a373-f62ebe882b35': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'0eb7a1da-36c1-40f8-85ce-9070c9e4b8fe': 3,
                                                         '7750a219-6006-4b6b-a33a-089972a84b61': 2,
                                                         'cbde5a90-1cba-4f11-8e9e-032d1903afd2': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroreal.es/en/show/saint-john-baptist',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Herodes': {'label': 'Herodes', 'rank': 2},
                                                           'Hija de Herodías': {'label': 'Hija de Herodías',
                                                                                'rank': 3},
                                                           'Salome': {'label': 'Hija de Herodías', 'rank': 3},
                                                           'San Giovanni Battista': {'label': 'San Juan Bautista',
                                                                                     'rank': 1},
                                                           'San Juan Bautista': {'label': 'San Juan Bautista',
                                                                                 'rank': 1}}},
 '8c21d4ce-09c5-43fe-bf37-533b6681ae67': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'4cd04852-52a1-5cde-9b49-80af4e428b4d': 4,
                                                         '56b1c77a-f2fd-58cb-b84a-c812a7829843': 1,
                                                         'f05d8b64-5b9c-552a-b20f-f0a38a85694d': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.lesarts.com/es/programacion/c/1285-riccardo-primo.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Costanza': {'label': 'Costanza', 'rank': 2},
                                                           'Isacio': {'label': 'Isacio', 'rank': 4},
                                                           'Pulcheria': {'label': 'Pulcheria', 'rank': 3},
                                                           'Riccardo': {'label': 'Riccardo', 'rank': 1}}},
 '8c9e50f8-bffc-4e90-964c-509c298af60f': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/saison-26-27/opera/hamlet',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Claudius': {'label': 'Claudius', 'rank': 4},
                                                           'Gertrude': {'label': 'Gertrude', 'rank': 3},
                                                           'Hamlet': {'label': 'Hamlet', 'rank': 1},
                                                           'Ophélie': {'label': 'Ophélie', 'rank': 2}}},
 '8d762448-8b1e-4415-b0d5-8d2ce809fafd': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'55553ef2-1205-5763-b3d4-fbb76c82260c': 2,
                                                         '7445ae02-3735-5473-a9e4-7c095d92af41': 4,
                                                         'bc015b09-f03a-5875-be10-c98693bd66b8': 1,
                                                         'fbda65fc-6c09-5e88-96a7-8d3968f1dc71': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/die-liebe-zu-den-drei-orangen/?id_datum=4881',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Fata Morgana': {'label': 'Fata Morgana', 'rank': 4},
                                                           'Ninetta': {'label': 'Ninetta', 'rank': 3},
                                                           'Prinz': {'label': 'Prinz', 'rank': 1},
                                                           'Truffaldino': {'label': 'Truffaldino', 'rank': 2}}},
 '8e2a4c82-ec3b-5cbe-a4f1-6fec5018c10d': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'083038c8-484b-5ed0-961c-2033644ac30f': 3,
                                                         '3e111113-b5d8-5568-8f03-282209cca15a': 4,
                                                         '5e7eccf8-c218-57ca-b9ee-200b7424202b': 1,
                                                         'cf14c826-5a54-59f3-b44e-c6d8fc32eef4': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/flavio/?id_datum=4860',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Emilia': {'label': 'Emilia', 'rank': 3},
                                                           'Flavio': {'label': 'Flavio', 'rank': 1},
                                                           'Guido': {'label': 'Guido', 'rank': 2},
                                                           'Teodata': {'label': 'Teodata', 'rank': 4}}},
 '9115c5ee-8d2d-4fdc-af23-0c743d15b336': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/pique-dame.1385561?event_date=17916551',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Fürst Jeletzki': {'label': 'Fürst Jeletzki',
                                                                              'rank': 4},
                                                           'Gräfin': {'label': 'Gräfin', 'rank': 3},
                                                           'Hermann': {'label': 'Hermann', 'rank': 1},
                                                           'Jeletzki': {'label': 'Fürst Jeletzki', 'rank': 4},
                                                           'Lisa': {'label': 'Lisa', 'rank': 2}}},
 '98019d57-67ef-43b0-8e2a-c1de4bf21ee9': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'2fa15f50-5a2c-4daa-99a8-0648a035d163': 3,
                                                         '3c7de0af-3b68-4341-8e78-c71676190aaf': 1,
                                                         'c69bb60e-a196-46a1-b7cc-61db8b343268': 2,
                                                         'ec4239fa-83e1-4ebc-9e2c-9ab332797f82': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.teatroreal.es/en/show/fedora',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Count Loris Ipanoff': {'label': 'Count Loris Ipanoff',
                                                                                   'rank': 2},
                                                           'Countess Olga Sharev': {'label': 'Countess Olga '
                                                                                             'Sharev',
                                                                                    'rank': 3},
                                                           'De Siriex': {'label': 'De Siriex', 'rank': 4},
                                                           'Fedora': {'label': 'Princess Fedora', 'rank': 1},
                                                           'Loris Ipanoff': {'label': 'Count Loris Ipanoff',
                                                                             'rank': 2},
                                                           'Olga': {'label': 'Countess Olga Sharev', 'rank': 3},
                                                           'Princess Fedora': {'label': 'Princess Fedora',
                                                                               'rank': 1}}},
 '98b42ce0-6563-44b2-b52b-5d86071b9ae6': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/saison-26-27/opera/don-pasquale',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Docteur Malatesta': {'label': 'Malatesta', 'rank': 4},
                                                           'Don Pasquale': {'label': 'Don Pasquale', 'rank': 1},
                                                           'Ernesto': {'label': 'Ernesto', 'rank': 3},
                                                           'Malatesta': {'label': 'Malatesta', 'rank': 4},
                                                           'Norina': {'label': 'Norina', 'rank': 2}}},
 '9ea85708-76c0-4d64-a69f-c6f84f039157': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'031afc40-62e9-4dfa-a603-9da34d361609': 3,
                                                         '033cabe9-e1b8-40bb-b81c-c14d7f651d83': 2,
                                                         'a21af210-c7d4-4440-b806-dfd9b778d46a': 1,
                                                         'f66dbd85-eca1-4c66-b506-c241b76b2737': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.wiener-staatsoper.at/en/calendar/detail/the-bartered-bride/2027-01-08/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Jeník': {'label': 'Jeník', 'rank': 2},
                                                           'Kecal': {'label': 'Kecal', 'rank': 3},
                                                           'Mařenka': {'label': 'Mařenka', 'rank': 1},
                                                           'Vašek': {'label': 'Vašek', 'rank': 4}}},
 'a27e0e30-1741-50ac-820b-939f0d8e25f4': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'535db7ef-7009-54f4-af33-72630caaf7c4': 4,
                                                         '9288cba4-08e1-5f3d-bf42-6aad8d5da192': 3,
                                                         'a30a412a-a1c8-5603-ac4c-b8718feea2e7': 2,
                                                         'a447a399-482b-5beb-909d-670c8b50b019': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/zaide/?id_datum=4807',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Allazim': {'label': 'Allazim', 'rank': 4},
                                                           'Gomatz': {'label': 'Gomatz', 'rank': 2},
                                                           'Soliman': {'label': 'Soliman', 'rank': 3},
                                                           'Zaide': {'label': 'Zaide', 'rank': 1}}},
 'a3a7935a-1e43-4d48-931a-a92fc53533c7': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.opernhaus.ch/en/spielplan/calendar/doctor-atomic/2026-2027/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Edward Teller': {'label': 'Edward Teller', 'rank': 3},
                                                           'J. Robert Oppenheimer': {'label': 'J. Robert '
                                                                                              'Oppenheimer',
                                                                                     'rank': 1},
                                                           'Kitty Oppenheimer': {'label': 'Kitty Oppenheimer',
                                                                                 'rank': 2},
                                                           'Robert Oppenheimer': {'label': 'J. Robert Oppenheimer',
                                                                                  'rank': 1},
                                                           'Robert R. Wilson': {'label': 'Robert R. Wilson',
                                                                                'rank': 4},
                                                           'Robert Wilson': {'label': 'Robert R. Wilson',
                                                                             'rank': 4}}},
 'af21deb5-5726-5cf7-babc-61be6ffc5f53': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/gretry-la-caravane-du-caire/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Husca': {'label': 'Husca', 'rank': 3},
                                                           'Saint-Phar': {'label': 'Saint-Phar', 'rank': 2},
                                                           'Zélime': {'label': 'Zélime', 'rank': 1}}},
 'b8151f32-aaaf-409e-86c8-f4d08fdeaaf0': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://auditorionacional.inaem.gob.es/es/programacion/cndm-les-accents-2',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Agrippina': {'label': 'Agrippina', 'rank': 1},
                                                           'Nerone': {'label': 'Nerone', 'rank': 2},
                                                           'Ottone': {'label': 'Ottone', 'rank': 4},
                                                           'Poppea': {'label': 'Poppea', 'rank': 3}}},
 'b91d88a5-3e48-4017-bc95-f7e3386acb19': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/elektra.1385724?event_date=17917082',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Chrysothemis': {'label': 'Chrysothemis', 'rank': 2},
                                                           'Elektra': {'label': 'Elektra', 'rank': 1},
                                                           'Klytämnestra': {'label': 'Klytämnestra', 'rank': 3},
                                                           'Orest': {'label': 'Orest', 'rank': 4}}},
 'bec7040a-51b1-5fed-8ba0-25810c16eef4': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/haendel-jules-cesar-en-egypte/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Cléopâtre': {'label': 'Cléopâtre', 'rank': 2},
                                                           'Cornelia': {'label': 'Cornelia', 'rank': 3},
                                                           'Jules César': {'label': 'Jules César', 'rank': 1},
                                                           'Sextus': {'label': 'Sextus', 'rank': 4}}},
 'bf62ec6e-c057-4c4b-9207-9087cf169e64': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.komische-oper-berlin.de/spielplan/kalender/2026-10/jewgeni-onegin/1252/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Jewgeni Onegin': {'label': 'Jewgeni Onegin',
                                                                              'rank': 1},
                                                           'Lenski': {'label': 'Lenski', 'rank': 3},
                                                           'Olga': {'label': 'Olga', 'rank': 4},
                                                           'Onegin': {'label': 'Jewgeni Onegin', 'rank': 1},
                                                           'Tatjana': {'label': 'Tatjana', 'rank': 2}}},
 'c1bf7819-2c85-483a-b69e-aef2dc1eb2c6': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://liceubarcelona.cat/en/fanciulla-del-west',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Dick Johnson': {'label': 'Dick Johnson', 'rank': 2},
                                                           'Jack Rance': {'label': 'Jack Rance', 'rank': 3},
                                                           'Minnie': {'label': 'Minnie', 'rank': 1}}},
 'c37b88dd-d620-4e92-afe5-eae0ad6d09cc': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'423cb682-d8aa-4b5c-891a-10e959937c88': 4,
                                                         'b46a5c13-e658-4078-b97e-62f4ffd6586d': 1,
                                                         'b8411891-2082-4812-ab64-d8fe64573be7': 2,
                                                         'd086008a-f5b5-4d1a-942d-de9abc0cd477': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-berlin.de/en/veranstaltungen/la-vestale.27273/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Cinna': {'label': 'Cinna', 'rank': 4},
                                                           'Julia': {'label': 'Julia', 'rank': 1},
                                                           'La Grande Vestale': {'label': 'La Grande Vestale',
                                                                                 'rank': 3},
                                                           'Licinius': {'label': 'Licinius', 'rank': 2}}},
 'c527a34e-a7b0-40da-ad7d-6a4af5d58fd1': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'275f6d3b-43ea-58c5-82e9-3f5b5618c827': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/warten-auf-heute_2/?id_datum=4803',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Eine Frau': {'label': 'Eine Frau', 'rank': 1}}},
 'c7183ebe-358f-575e-98da-582c93f9ab6d': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.komische-oper-berlin.de/spielplan/kalender/2026-09/lear/1353/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Cordelia': {'label': 'Cordelia', 'rank': 4},
                                                           'Goneril': {'label': 'Goneril', 'rank': 2},
                                                           'Lear': {'label': 'Lear', 'rank': 1},
                                                           'Regan': {'label': 'Regan', 'rank': 3}}},
 'c7fca9db-9c25-5bcb-a928-30872575133b': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/vivaldi-juditha-triumphans/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Holofernes': {'label': 'Holofernes', 'rank': 2},
                                                           'Juditha': {'label': 'Juditha', 'rank': 1},
                                                           'Vagaus': {'label': 'Vagaus', 'rank': 3}}},
 'cb7fb035-b4ed-4a18-8841-3aaf82d34c28': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.barbican.org.uk/whats-on/2026/event/monteverdi-lincoronazione-di-poppea',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Nerone': {'label': 'Nerone', 'rank': 2},
                                                           'Ottavia': {'label': 'Ottavia', 'rank': 3},
                                                           'Ottone': {'label': 'Ottone', 'rank': 4},
                                                           'Poppea': {'label': 'Poppea', 'rank': 1}}},
 'd61ee9e6-c0ed-5a37-8957-f92b08a0f920': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'849642fa-73fa-59ee-ae98-f8d377762701': 2,
                                                         'f78b116e-caec-5633-b9e8-6d8f7929a364': 3,
                                                         'f7f6a835-98d7-5f9d-8e4a-7b08d8181b05': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/le-roi-arthus/?id_datum=4828',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Arthus': {'label': 'Arthus', 'rank': 1},
                                                           'Genièvre': {'label': 'Genièvre', 'rank': 2},
                                                           'Lancelot': {'label': 'Lancelot', 'rank': 3}}},
 'd80d8d7a-2f58-46ac-8c33-589fee285647': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'4dadda21-0b6c-4ce7-a42f-fd653af488ad': 2,
                                                         '8d39f8dd-9f6d-4c51-9971-23bd4bd00041': 1,
                                                         'cdf14ef7-79f4-4536-88fb-54fc4a964d74': 3,
                                                         'e8ebd8dd-f557-4605-b169-ac8beb55ad03': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-berlin.de/en/veranstaltungen/la-calisto.27274/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Calisto': {'label': 'Calisto', 'rank': 1},
                                                           'Diana': {'label': 'Diana', 'rank': 2},
                                                           'Endimione': {'label': 'Endimione', 'rank': 3},
                                                           'Giove': {'label': 'Giove', 'rank': 4}}},
 'dc200d09-5674-42b8-a5e4-970ce5c7753a': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'24b9d0ec-0cc8-4741-9623-0052bad9165a': 3,
                                                         '2fb26d20-96ca-48a6-83b7-44a73e0a3ec0': 4,
                                                         '648e270f-37f4-48c2-b484-d38cf5edb63f': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://auditorionacional.inaem.gob.es/es/programacion/cndm-le-concert-de-la-loge',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Costanza': {'label': 'Costanza', 'rank': 3},
                                                           'Griselda': {'label': 'Griselda', 'rank': 1},
                                                           'Gualtiero': {'label': 'Gualtiero', 'rank': 2},
                                                           'Roberto': {'label': 'Roberto', 'rank': 4}}},
 'e09a5a07-9788-4cae-9d6a-a84cad9eb625': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://teatrodelazarzuela.inaem.gob.es/es/temporada/lirica-2026-2027/las-trece-rosas-rojas',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Blanca': {'label': 'Blanca', 'rank': 4},
                                                           'Joaquina': {'label': 'Joaquina', 'rank': 3},
                                                           'Julia': {'label': 'Julia', 'rank': 1},
                                                           'Virtudes': {'label': 'Virtudes', 'rank': 2}}},
 'e1fab70f-dd1d-5bd5-9494-32e8690e029d': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/rameau-pygmalion-gluck-le-cadi-dupe/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Cadi': {'label': 'Le Cadi', 'rank': 1},
                                                           'Fatime': {'label': 'Fatime', 'rank': 3},
                                                           'Le Cadi': {'label': 'Le Cadi', 'rank': 1},
                                                           'Zelmire': {'label': 'Zelmire', 'rank': 2}}},
 'e5357cde-7d7b-5531-b792-f5d239b87412': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'06a83e82-e35d-5f0e-8077-1059f8103b69': 1,
                                                         '6e794d33-b828-54aa-9e47-6e05267da0b3': 2,
                                                         '8fcf2aff-15f4-57e9-9287-cc8de68b3c7e': 3,
                                                         'ce687b76-d308-5ee4-8ed6-ebbd1beac65a': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/the-greek-passion/?id_datum=4957',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Fotis': {'label': 'Priester Fotis', 'rank': 4},
                                                           'Grigoris': {'label': 'Priester Grigoris', 'rank': 3},
                                                           'Katerina': {'label': 'Witwe Katerina', 'rank': 2},
                                                           'Manolios': {'label': 'Manolios', 'rank': 1},
                                                           'Priester Fotis': {'label': 'Priester Fotis',
                                                                              'rank': 4},
                                                           'Priester Grigoris': {'label': 'Priester Grigoris',
                                                                                 'rank': 3}}},
 'e98a3519-dc32-5cbd-baea-e3ee73b0227c': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/rameau-pygmalion-gluck-le-cadi-dupe/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Amour': {'label': 'L’Amour', 'rank': 3},
                                                           'Céphise': {'label': 'Céphise', 'rank': 2},
                                                           'L’Amour': {'label': 'L’Amour', 'rank': 3},
                                                           'Pygmalion': {'label': 'Pygmalion', 'rank': 1}}},
 'eba10ae3-2db3-5d66-a969-eee504ca117e': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'439f9466-07df-590b-8f91-e1d39eb24d13': 3,
                                                         '4f7227f6-7a3a-50a7-8b1a-dea6f58d8f6d': 4,
                                                         'ab59046c-1602-5ae0-98d7-9e0742a4c2e1': 1,
                                                         'cfb12507-d1b1-52d6-8478-993abf3dd429': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.semperoper.de/spielplan/stuecke/stid/pech-marie/62903.html',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Frau Holle': {'label': 'Frau Holle', 'rank': 3},
                                                           'Marie': {'label': 'Marie', 'rank': 1},
                                                           'Mary': {'label': 'Mary', 'rank': 2},
                                                           'Mutter': {'label': 'Mutter', 'rank': 4}}},
 'f9b30d34-1fb2-4ee7-8de1-08353ff6f1a9': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'84f2de9b-7f76-55b8-81c9-bcae5fa0c4fb': 2,
                                                         'e878df17-6385-5f54-917a-225afb673b4f': 1,
                                                         'ff89e4e3-4cd1-5aeb-8eb9-53d2f2482ced': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://teatrodelazarzuela.inaem.gob.es/es/temporada/lirica-2026-2027/venus-y-adonis',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Adonis': {'label': 'Adonis', 'rank': 2},
                                                           'Marte': {'label': 'Marte', 'rank': 3},
                                                           'Venus': {'label': 'Venus', 'rank': 1}}},
 'ff44b983-f973-4e00-8e48-f4bd71f50ac8': {'basis': 'Principal dramatic roles reviewed against official work '
                                                   'synopsis and cast. Shared display classification only; '
                                                   'performers remain performance specific.',
                                          'characters': {'167d2987-50f9-5781-a1cb-b730318468fd': 3,
                                                         '3cedb2e3-3aa3-56d1-b207-a03c515ec77b': 1,
                                                         '496e5efd-cfac-5ba8-baec-ced70f7b16fd': 2,
                                                         'd555f9e3-c8d6-56ab-89e6-520ad2031ed9': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/de/spielplan/die-nacht-vor-weihnachten_4/?id_datum=4854',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Oksana': {'label': 'Oksana', 'rank': 2},
                                                           'Solocha': {'label': 'Solocha', 'rank': 3},
                                                           'Teufel': {'label': 'Teufel', 'rank': 4},
                                                           'Wakula': {'label': 'Wakula', 'rank': 1}}}})

# Source recovery reviewed 2026-10-30; global work policies only.
WORK_CAST_POLICIES.update({'03d676c5-df6a-4b27-a2ca-c18d4ef02fba': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://liceubarcelona.cat/en/exterminating-angel',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Doctor Carlos Conde': {'label': 'Doctor Carlos Conde',
                                                                                   'rank': 4},
                                                           'Edmundo de Nobile': {'label': 'Edmundo de Nobile',
                                                                                 'rank': 2},
                                                           'Leticia Meynar': {'label': 'Leticia Meynar',
                                                                              'rank': 1},
                                                           'Lucia de Nobile': {'label': 'Lucia de Nobile',
                                                                               'rank': 3}}},
 '0b302bbd-813a-56b2-9c43-5cdcef7ba46a': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-stuttgart.de/spielplan/kalender/atatuerk/10143/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Mustafa Kemal, später Atatürk': {'label': 'Mustafa '
                                                                                                      'Kemal, '
                                                                                                      'später '
                                                                                                      'Atatürk',
                                                                                             'rank': 1}}},
 '695df17a-91fd-5fc8-85f8-df97ff8e51d9': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.theater-basel.ch/de/herakles',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Amphitryon': {'label': 'Amphitryon', 'rank': 3},
                                                           'H of H (Herakles)': {'label': 'H of H (Herakles)',
                                                                                 'rank': 1},
                                                           'Lykos': {'label': 'Lykos', 'rank': 4},
                                                           'Megara': {'label': 'Megara', 'rank': 2}}},
 '73003312-7de6-42a0-9e21-327bb0a9a40c': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://archive.bolshoi.ru/entity/PERFORMANC/435637?index=22',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Farlaf': {'label': 'Фарлаф', 'rank': 4},
                                                           'Ludmila': {'label': 'Людмила', 'rank': 2},
                                                           'Lyudmila': {'label': 'Людмила', 'rank': 2},
                                                           'Ratmir': {'label': 'Ратмир', 'rank': 3},
                                                           'Ruslan': {'label': 'Руслан', 'rank': 1},
                                                           'Людмила': {'label': 'Людмила', 'rank': 2},
                                                           'Ратмир': {'label': 'Ратмир', 'rank': 3},
                                                           'Руслан': {'label': 'Руслан', 'rank': 1},
                                                           'Фарлаф': {'label': 'Фарлаф', 'rank': 4}}},
 '7859b3da-0ffa-52e8-8b11-313d1b612859': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaballet.nl/en/dutch-national-opera/2026-2027/iolanta',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Ibn-Hakia': {'label': 'Ibn-Hakia', 'rank': 4},
                                                           'Iolanta': {'label': 'Iolanta', 'rank': 1},
                                                           'René': {'label': 'René', 'rank': 3},
                                                           'Vaudémont': {'label': 'Vaudémont', 'rank': 2}}},
 '825e1f24-5b95-4e9a-9050-2e64e9395df6': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper.de/en/productions/lucrezia-borgia/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Alfonso': {'label': 'Don Alfonso', 'rank': 3},
                                                           'Don Alfonso': {'label': 'Don Alfonso', 'rank': 3},
                                                           'Gennaro': {'label': 'Gennaro', 'rank': 2},
                                                           'Lucrezia Borgia': {'label': 'Lucrezia Borgia',
                                                                               'rank': 1},
                                                           'Maffio Orsini': {'label': 'Maffio Orsini', 'rank': 4},
                                                           'Orsini': {'label': 'Maffio Orsini', 'rank': 4}}},
 '8b042d52-2d23-4b7b-bcdb-524d10e992cb': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/saison-23-24/opera/medee',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Créon': {'label': 'Créon', 'rank': 4},
                                                           'Créuse': {'label': 'Créuse', 'rank': 3},
                                                           'Jason': {'label': 'Jason', 'rank': 2},
                                                           'Médée': {'label': 'Médée', 'rank': 1}}},
 '8ee0f793-8378-5980-be23-6e8978575af2': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaballet.nl/en/dutch-national-opera/2026-2027/hedda-gabler',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Ejlert Løvborg': {'label': 'Ejlert Løvborg',
                                                                              'rank': 2},
                                                           'Hedda Gabler': {'label': 'Hedda Gabler', 'rank': 1},
                                                           'Judge Brack': {'label': 'Judge Brack', 'rank': 3},
                                                           'Jørgen Tesman': {'label': 'Jørgen Tesman',
                                                                             'rank': 4}}},
 '9a110ca2-d4b5-40c7-b6d0-56bf55909301': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://archives.metopera.org/MetOperaSearch/record.jsp?dockey=0358447',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Arnold': {'label': 'Arnold', 'rank': 2},
                                                           'Guillaume Tell': {'label': 'Guillaume Tell',
                                                                              'rank': 1},
                                                           'Mathilde': {'label': 'Mathilde', 'rank': 3},
                                                           'Walter': {'label': 'Walter', 'rank': 4},
                                                           'William Tell': {'label': 'Guillaume Tell',
                                                                            'rank': 1}}},
 '9cbb09b4-d8cc-45a1-a56d-6d1887e1ac91': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/saison-26-27/opera/miroir-de-nos-peines',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Désiré': {'label': 'Désiré', 'rank': 2},
                                                           'Gabriel': {'label': 'Gabriel', 'rank': 4},
                                                           'Louise': {'label': 'Louise', 'rank': 1},
                                                           'Raoul': {'label': 'Raoul', 'rank': 3}}},
 'b22b4b2b-37b3-4f80-91c3-25aceeee7c79': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {'5d595bf2-578f-40ad-857d-d01a9adb4688': 3,
                                                         '8e9e550d-6bc9-4b4c-b822-fd45c12aa632': 4,
                                                         'aee5d821-249f-4bfe-83da-ccf468f314e1': 2,
                                                         'feb9d539-fe61-4ba6-b6e9-6c87d69b3a8d': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.metopera.org/learn/education/learning-library/educator-guide-pages/faust/plot-and-characters/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Faust': {'label': 'Faust', 'rank': 1},
                                                           'Marguerite': {'label': 'Marguerite', 'rank': 2},
                                                           'Méphistophélès': {'label': 'Méphistophélès',
                                                                              'rank': 3},
                                                           'Valentin': {'label': 'Valentin', 'rank': 4}}},
 'b32c8817-e7b8-5927-8a0c-86735c08849d': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/campra-le-carnaval-de-venise/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Isabelle': {'label': 'Isabelle', 'rank': 3},
                                                           'Léandre': {'label': 'Léandre', 'rank': 1},
                                                           'Léonore, Eurydice': {'label': 'Léonore, Eurydice',
                                                                                 'rank': 2}}},
 'b9e1674f-c290-56b3-978c-de9ed6b90450': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaballet.nl/en/dutch-national-opera/2026-2027/lennox',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Aya': {'label': 'Aya', 'rank': 2},
                                                           'Glimmerik': {'label': 'Glimmerik', 'rank': 3},
                                                           'Lennox': {'label': 'Lennox', 'rank': 1}}},
 'c01ef840-80e5-534f-8ee7-619d5e896f20': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.theater-basel.ch/de/mosesundaron',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Aron': {'label': 'Aron', 'rank': 2},
                                                           'Moses': {'label': 'Moses', 'rank': 1}}},
 'cf6b91b8-045c-58cb-b36b-935630737658': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-stuttgart.de/spielplan/kalender/die-drei-fragezeichen-und-das-spiegelkabinett/9595/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Bob Andrews': {'label': 'Bob Andrews', 'rank': 3},
                                                           'Justus Jonas': {'label': 'Justus Jonas', 'rank': 1},
                                                           'Peter Shaw': {'label': 'Peter Shaw', 'rank': 2}}},
 'd15d726c-0e7c-463b-a272-b38780b56a25': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {'31057567-8745-563c-8060-79bf87378957': 2,
                                                         '79bb35c8-8e2b-516c-bd2e-f37ded80872f': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.leonardbernstein.com/works/view/32/trouble-in-tahiti',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Dinah': {'label': 'Dinah', 'rank': 1},
                                                           'Sam': {'label': 'Sam', 'rank': 2}}},
 'd7835c88-7d1d-5036-a2da-a848c2f7b0c9': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/heggie-scheer-le-jugement-de-paris/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Bacchus': {'label': 'Bacchus', 'rank': 4},
                                                           'Patricia Gallagher': {'label': 'Patricia Gallagher',
                                                                                  'rank': 2},
                                                           'Steven Spurrier': {'label': 'Steven Spurrier',
                                                                               'rank': 1},
                                                           'Vénus': {'label': 'Vénus', 'rank': 3}}},
 'f623f325-fefc-5df2-b19a-444bac473d98': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaballet.nl/en/dutch-national-opera/2026-2027/cherry-town',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Boris': {'label': 'Boris', 'rank': 1},
                                                           'Lidion': {'label': 'Lidion', 'rank': 2},
                                                           'Masha': {'label': 'Masha', 'rank': 4},
                                                           'Sasha': {'label': 'Sasha', 'rank': 3}}},
 'fbf1e422-bec4-59ec-9e02-1c3046f67f03': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaballet.nl/en/dutch-national-opera/2026-2027/uprising',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Angela Green': {'label': 'Angela Green', 'rank': 2},
                                                           'Lola Green': {'label': 'Lola Green', 'rank': 1}}},
 'ff19a877-a11c-5c7c-873f-4846afcb261a': {'basis': 'Principal dramatic roles reviewed from official synopsis and '
                                                   'cast; no performer assignment or canonical identity mutation.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://deutscheoperberlin.de/de_DE/production/sunville.1386002?event_date=17920011',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Der Boxer im Ruhestand': {'label': 'Der Boxer im '
                                                                                               'Ruhestand',
                                                                                      'rank': 3},
                                                           'Die Frau mit den langen Zöpfen': {'label': 'Die Frau '
                                                                                                       'mit den '
                                                                                                       'langen '
                                                                                                       'Zöpfen',
                                                                                              'rank': 2},
                                                           'Die furchtlose Ex-Königin': {'label': 'Die furchtlose '
                                                                                                  'Ex-Königin',
                                                                                         'rank': 1}}}})

# Final source recovery reviewed 2026-10-30; principal selection only.
WORK_CAST_POLICIES.update({'140a1d6f-2944-44a2-8cca-925b58053404': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {'037aeb37-7c91-584b-a957-d5cb7166436a': 3,
                                                         '414365ad-44ae-50ec-b231-f9f77fffa7e9': 1,
                                                         '8fcd9aa6-ed01-5fdc-bd41-f47af82af674': 4,
                                                         'f8576d6d-3fef-5cdc-8d1d-0c1b26c8f281': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://bru-zane.com/en/evento/roma-jules-massenet/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Fabius': {'label': 'Fabius Maximus', 'rank': 4},
                                                           'Fabius Maximus': {'label': 'Fabius Maximus',
                                                                              'rank': 4},
                                                           'Fausta': {'label': 'Fausta', 'rank': 1},
                                                           'Lentulus': {'label': 'Lentulus', 'rank': 2},
                                                           'Posthumia': {'label': 'Posthumia', 'rank': 3}}},
 '2c1209b8-5e60-42b2-9b08-3bb4c08571dc': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {'5781061e-1363-4952-9d3f-ade8c90c9ffd': 1,
                                                         'ad82154b-5d00-4ab5-a18b-837c5dc920e0': 3,
                                                         'e113168d-3dd4-49af-afc6-d05cbf527cf5': 2,
                                                         'f180c5ed-9130-4f22-b95e-23dac3627056': 4},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-berlin.de/en/veranstaltungen/hippolyte-et-aricie.2749/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Aricie': {'label': 'Aricie', 'rank': 2},
                                                           'Hippolyte': {'label': 'Hippolyte', 'rank': 1},
                                                           'Phèdre': {'label': 'Phèdre', 'rank': 3},
                                                           'Thésée': {'label': 'Thésée', 'rank': 4}}},
 '3a49b72f-918c-46d6-9984-78479d53fcdd': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.die-hamburgische-staatsoper.de/de/programm/oper/529-il-turco-in-italia',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Don Geronio': {'label': 'Don Geronio', 'rank': 3},
                                                           'Don Narciso': {'label': 'Don Narciso', 'rank': 4},
                                                           'Donna Fiorilla': {'label': 'Donna Fiorilla',
                                                                              'rank': 2},
                                                           'Fiorilla': {'label': 'Donna Fiorilla', 'rank': 2},
                                                           'Selim': {'label': 'Selim', 'rank': 1}}},
 '41bf570d-75c0-5401-9415-cf47ed6189c3': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://oper-frankfurt.de/media/pdf/Krl_Roger_King_Roger.pdf',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Der Hirt': {'label': 'Hirt', 'rank': 3},
                                                           'Edrisi': {'label': 'Edrisi', 'rank': 4},
                                                           'Hirt': {'label': 'Hirt', 'rank': 3},
                                                           'King Roger': {'label': 'Roger', 'rank': 1},
                                                           'Roger': {'label': 'Roger', 'rank': 1},
                                                           'Roxana': {'label': 'Roxana', 'rank': 2},
                                                           'Sheperd': {'label': 'Hirt', 'rank': 3},
                                                           'Shepherd': {'label': 'Hirt', 'rank': 3}}},
 '440df241-66d5-4778-b354-4cc44deb36d6': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {'17439791-95a8-47b8-b29d-6d1406ae68b6': 2,
                                                         'a53231ce-e327-457a-b53c-b201131c3ae7': 1,
                                                         'b6e3aedd-cbf9-4421-a1d1-f3bccc9ae75a': 4,
                                                         'c211053b-011a-42aa-be5e-48df838fa682': 3},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/rameau-platee-2024/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Junon': {'label': 'Junon', 'rank': 3},
                                                           'Jupiter': {'label': 'Jupiter', 'rank': 2},
                                                           'La Folie': {'label': 'La Folie', 'rank': 4},
                                                           'Platée': {'label': 'Platée', 'rank': 1},
                                                           'la Folie': {'label': 'La Folie', 'rank': 4}}},
 '6d222672-ec92-4aa4-82c1-13711b5e43a2': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {'9202f3a6-b6d9-4cd9-b46a-75136d7ee669': 1,
                                                         'a5f10e1f-07b7-46ab-821d-ad6b0f1960f0': 2},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.theatrechampselysees.fr/saison-2026-27/opera-en-concert/romeo-et-juliette-5',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Juliette': {'label': 'Juliette', 'rank': 2},
                                                           'Roméo': {'label': 'Roméo', 'rank': 1}}},
 '7e809a3f-a6b0-47b7-bf22-8ac23265b562': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper.de/en/productions/of-one-blood',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Elizabeth Tudor': {'label': 'Elizabeth Tudor, Queen '
                                                                                        'of England',
                                                                               'rank': 2},
                                                           'Elizabeth Tudor, Queen of England': {'label': 'Elizabeth '
                                                                                                          'Tudor, '
                                                                                                          'Queen '
                                                                                                          'of '
                                                                                                          'England',
                                                                                                 'rank': 2},
                                                           'Mary Stuart': {'label': 'Mary Stuart, Queen of Scots',
                                                                           'rank': 1},
                                                           'Mary Stuart, Queen of Scots': {'label': 'Mary Stuart, '
                                                                                                    'Queen of '
                                                                                                    'Scots',
                                                                                           'rank': 1}}},
 '81d99864-489b-4ba1-bbee-7f453c7966b2': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operadeparis.fr/saison-23-24/opera/ma-mere-loye-lenfant-et-les-sortileges',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {"L'Enfant": {'label': 'L’Enfant', 'rank': 1},
                                                           'L’Enfant': {'label': 'L’Enfant', 'rank': 1}}},
 'a97c6f9b-7f9f-50be-91c0-253f97fe9c2c': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/scarlatti-oratorio-per-la-passione-di-nostro-signore-gesu-cristo/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Il Pentimento': {'label': 'Il Pentimento', 'rank': 2},
                                                           'La Colpa': {'label': 'La Colpa', 'rank': 1},
                                                           'La Grazia': {'label': 'La Grazia', 'rank': 3}}},
 'b83d6335-5e37-42fd-9b31-cc07a57fbc56': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.opernhaus.ch/spielplan/kalendarium/samson-et-dalila/2026-2027/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Abimelech': {'label': 'Abimelech', 'rank': 4},
                                                           'Abimélech': {'label': 'Abimelech', 'rank': 4},
                                                           'Dalila': {'label': 'Dalila', 'rank': 2},
                                                           'Oberpriester des Dagon': {'label': 'Oberpriester des '
                                                                                               'Dagon',
                                                                                      'rank': 3},
                                                           'Samson': {'label': 'Samson', 'rank': 1}}},
 'c3664983-2719-54d1-9ce6-31cbd75b8462': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.operaroyal-versailles.fr/evenement/zingarelli-romeo-et-juliette/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Giulietta': {'label': 'Juliette', 'rank': 2},
                                                           'Juliette': {'label': 'Juliette', 'rank': 2},
                                                           'Romeo': {'label': 'Roméo', 'rank': 1},
                                                           'Roméo': {'label': 'Roméo', 'rank': 1}}},
 'c946cf3f-8b7d-4b0a-ba16-671a92141512': {'basis': 'Principal dramatic roles reviewed from official plot and '
                                                   'cast; historical sources establish roles only, never current '
                                                   'performer assignments.',
                                          'characters': {'10026eb5-f907-43ba-a0d7-e4da1aa027b1': 3,
                                                         '56d98de5-bfb8-450d-aacd-3cf4c0798927': 4,
                                                         '776653b0-d8e3-4007-947b-bccf5620169f': 2,
                                                         'a1fbd69a-1f75-4842-9eda-b72b94d25804': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper.de/en/productions/mitridate-re-di-ponto',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Aspasia': {'label': 'Aspasia', 'rank': 2},
                                                           'Farnace': {'label': 'Farnace', 'rank': 4},
                                                           'Mitridate': {'label': 'Mitridate', 'rank': 1},
                                                           'Sifare': {'label': 'Sifare', 'rank': 3}}}})

# Official role sources reviewed 2026-10-30.
WORK_CAST_POLICIES.update({'96940e9a-4956-49f8-81e6-270df6e53570': {'basis': 'Principal dramatic roles reviewed from official cast and '
                                                   'plot, independently of performance-specific casting.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://www.staatsoper-berlin.de/de/veranstaltungen/die-zarenbraut.27712/',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Grjasnoj': {'label': 'Grjasnoj', 'rank': 3},
                                                           'Ljubascha': {'label': 'Ljubascha', 'rank': 2},
                                                           'Lykow': {'label': 'Lykow', 'rank': 4},
                                                           'Marfa': {'label': 'Marfa', 'rank': 1}}},
 'b597e357-f28b-49a9-8743-85a65d9d7bae': {'basis': 'Principal dramatic roles reviewed from official cast and '
                                                   'plot, independently of performance-specific casting.',
                                          'characters': {'7b49d3f2-770c-4104-a7bd-bc1690e64ea4': 3,
                                                         'aec4201b-4172-4c2b-927b-14cc61e3e22d': 4,
                                                         'e7f44698-7d12-403e-bbf9-bb7ad14539f7': 2,
                                                         'fbbc37f1-4ba9-4e92-be7d-632051310b24': 1},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://nps.ba/predstave/attila/270',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Attila': {'label': 'Attila', 'rank': 1},
                                                           'Ezio': {'label': 'Ezio', 'rank': 4},
                                                           'Foresto': {'label': 'Foresto', 'rank': 3},
                                                           'Odabella': {'label': 'Odabella', 'rank': 2}}},
 'd6079dc4-b0e2-43f7-b42d-79db98ef2843': {'basis': 'Principal dramatic roles reviewed from official cast and '
                                                   'plot, independently of performance-specific casting.',
                                          'characters': {},
                                          'event_types': ['opera', 'operetta'],
                                          'evidence': 'https://teatrodelazarzuela.inaem.gob.es/es/temporada-2021-2022/lirica-2021-2022/el-barberillo-de-lavapies-2021-2022',
                                          'reviewed_on': '2026-10-30',
                                          'source_roles': {'Don Luis': {'label': 'Don Luis', 'rank': 4},
                                                           'La Marquesita': {'label': 'Marquesita del Bierzo',
                                                                             'rank': 3},
                                                           'Lamparilla': {'label': 'Lamparilla', 'rank': 1},
                                                           'Marquesita del Bierzo': {'label': 'Marquesita del '
                                                                                              'Bierzo',
                                                                                     'rank': 3},
                                                           'Paloma': {'label': 'Paloma', 'rank': 2}}}})

# Reviewed vocal works: show published voice credits without inventing dramatic roles.
VOCAL_WORK_POLICIES = {'85e7522d-05ba-5158-af8f-d7f5b5bd1b00': {'basis': 'Contemporary vocal music theatre; official artists are billed '
                                                   'as singers, without fixed named characters.',
                                          'evidence': 'https://www.theater-basel.ch/de/ifidonotreturn'},
 'b9f4662d-4f24-47d0-8684-39833a840b0e': {'basis': 'Official distribution lists Chant and instrumental functions, '
                                                   'not a Josephine Baker dramatic role.',
                                          'evidence': 'https://www.operadeparis.fr/saison-26-27/opera/perle-noire-meditations-pour-josephine'},
 'db328ab4-47dc-566d-9f2f-8b46e2425f00': {'basis': 'Official cast lists soprano, mezzo-soprano and bass by voice, '
                                                   'separately from speaker and child.',
                                          'evidence': 'https://www.semperoper.de/spielplan/stuecke/stid/wunderjahre/62915.html'}}

# Official Bavarian State Opera label for Gounod's title character.
WORK_CAST_POLICIES['b22b4b2b-37b3-4f80-91c3-25aceeee7c79']['source_roles']['Le docteur Faust'] = {'label': 'Faust', 'rank': 1}
WORK_CAST_POLICIES['b22b4b2b-37b3-4f80-91c3-25aceeee7c79']['source_evidence'] = ['https://www.staatsoper.de/stuecke/faust']

# Explicit source functions in reviewed vocal works, independent of venue.
VOCAL_WORK_POLICIES['b9f4662d-4f24-47d0-8684-39833a840b0e']['source_functions'] = {
    'Chant': 'singer', 'Piano et percussions': 'piano_percussion', 'Flûte': 'flute',
    'Saxophone': 'saxophone', 'Basson': 'bassoon', 'Violon': 'violin', 'Guitare électrique': 'electric_guitar',
}
VOCAL_WORK_POLICIES['db328ab4-47dc-566d-9f2f-8b46e2425f00']['source_functions'] = {
    'Sopran': 'soprano', 'Mezzosopran': 'mezzo_soprano', 'Bass': 'bass', 'Sprecherin': 'speaker',
}
