"""Texts for the documents the tool writes: brief, analysis, quality report, disclosure.

Console output is English. The documents are for people — translators, maintainers,
the upstream project — so they come in several languages. To add one, copy the
"en" block, translate the values and keep the {placeholders}. Missing keys fall back
to English, so a partial translation works.
"""

MESSAGES = {}

MESSAGES['en'] = {
    # -- batch files --------------------------------------------------------
    'batch_about': (
        'Batch {n} of {total}, units {first} to {last}. Files: {files}. '
        'Fill in "target" for every unit; plural units take a list of {nplurals} forms. '
        'Leave "source" unchanged — it is the check against shifted numbers. '
        'Add "note" where a decision needs explaining.'),

    # -- brief --------------------------------------------------------------
    'brief_title': '# Brief: {project} into {language}',
    'brief_summary': (
        '**{units} untranslated units** in {batches} batches, {help} of them help '
        'texts and {plural} with plural forms.'),
    'brief_previous': (
        'For {n} units an earlier translation exists; it is in `work/scaffold.json` under '
        '`previous`, together with the source it was made for.'),
    'brief_how_heading': '## How to work',
    'brief_one_form': (
        'This language has a single plural form. For a plural unit, translate the '
        'plural source (`source_plural`, with its `%d`): the one form is shown for every '
        'number, 1 included.'),
    'brief_how': (
        '1. Each file in `work/batches/` lists its units with `source` and an empty '
        '`target`. Fill in `target`. Plural units take a list of {nplurals} forms.\n'
        '2. Leave `source` as it is. It lets the tool notice shifted numbers.\n'
        '3. Where a decision is not self-explanatory, add `"note": "..."` to the unit.\n'
        '4. `work/scaffold.json` has more per unit: earlier translation, field label, '
        'glossary hits, examples from the same file.\n'
        '5. Run `{check}` after every batch and fix every error.\n'
        '6. Later fixes go into a new file in `work/corrections/` (same format); those may '
        'overwrite earlier entries.\n\n'
        'The numbers follow **the same order as Weblate** under the filter '
        '`state:empty`.'),
    'brief_guidelines': '## Guidelines',
    'brief_working': '## Working method',
    'brief_glossary': '## Glossary',
    'english': 'English',
    'brief_checks_heading': '## What is checked',
    'brief_checks': (
        '`check` reports as **errors**: missing or reordered placeholders, a different '
        'HTML tag sequence, missing numbers, changed URLs and code identifiers, a wrong '
        'number of plural forms, empty entries, and source texts that do not match the '
        'scaffold.\n\n'
        'As **notes**: leading/trailing whitespace (restored on build anyway), text '
        'copied unchanged from the source, lost sentences, terms deviating from the '
        'prevailing version in the existing translations, unwanted forms from the '
        'profile, and craft issues such as doubled words or unbalanced brackets.'),

    'brief_blocking': (
        'This profile makes these notes **block the build**: {kinds}. Fix each one, '
        'or, where the translation is right as it is, explain why in the unit\'s '
        '`"note"`. A unit with a note is not blocked; the reviewer reads the note.'),

    # -- disclosure in the PO header ----------------------------------------
    'disclosure': (
        'Drafts for the units of this component that were empty in the export\n'
        'of {exported} (latest revision in it: {revision}).\n'
        'Units that were already translated are not included.\n'
        '\n'
        'Prepared with a language model and checked by machine: placeholders,\n'
        'HTML structure and terminology against the existing translations.\n'
        'Meant to be imported as suggestions, not as finished translations.'),

    # -- shared -------------------------------------------------------------
    'none': 'None.',
    'and_more': '… and {n} more',
    'and_more_json': '… and {n} more. Complete in the JSON output.',
    'wanted': 'wanted',
    'unwanted': 'unwanted',
    'error_vs_note': (
        'An error means: the source prescribes something the translation does not '
        'keep. A note means: have a look.'),

    # -- analysis -----------------------------------------------------------
    'analysis_title': '# Corpus analysis — {language}',
    'analysis_basis': 'Export: `{export}`',
    'analysis_profile': 'Profile: `{profile}`',
    'analysis_counts': (
        '{units} units, {translated} translated and {untranslated} untranslated. '
        'Counted: the {counted} translated singular units.'),
    'analysis_table_head': '| Finding | Errors | Notes |',
    'analysis_row_inconsistent': 'source texts with more than one translation',
    'analysis_row_collisions': 'translations standing for several source texts',
    'analysis_inconsistent_heading': '## 1. Inconsistent translations',
    'analysis_inconsistent_text': (
        'The same source text, several translations. Short texts first — those are '
        'the labels where it shows on screen.'),
    'analysis_inconsistent_head': '| Source | Translations |',
    'analysis_collisions_heading': '## 2. Collisions',
    'analysis_collisions_text': (
        'One translation for several source texts. A distinction the source makes '
        'disappears here — the more serious of the two findings.'),
    'analysis_collisions_head': '| Translation | stands for |',
    'analysis_defects_heading': '## 3. Formal defects in the existing translations',
    'analysis_forms_heading': '## 4. Forms',
    'analysis_forms_text': 'Raw counts. A hit is not yet an error — the list is for review.',
    'analysis_forms_head': '| ID | Form | Units | Occurrences | Profile |',
    'analysis_house_heading': '## 5. House terms',
    'analysis_house_text': (
        'What a term is called in this pack is decided by the existing translations. '
        'The most frequent variant counts as the house form; new drafts are checked '
        'against it.'),
    'analysis_house_head': '| Variant | Units | Examples |',
    'other_variant': 'none of these',
    'house_form': 'House form',
    'analysis_new_translated': 'how the translated units with "{term}" read so far',
    'analysis_new_heading': '## 6. New terms',
    'analysis_new_text': (
        'Source words that are frequent in the untranslated units and rare in the '
        'translated ones. Some are new product terms or words that replace older ones, '
        'others are ordinary words. Each product term needs a decision before the round.'),
    'analysis_new_head': '| ID | Word | untranslated units | translated units | Examples |',

    # -- quality report -----------------------------------------------------
    'report_title': '# Quality report — `{file}`',
    'report_basis': (
        'As of {today}. Based on the export `{export}` of {exported} (latest revision '
        'in it: {revision}), profile `{profile}`.'),
    'report_contents': '## Contents',
    'report_contents_text': (
        '{translated} of {units} untranslated units have a draft, {plural} of them '
        'with plural forms. Units that were already translated are not in the file: '
        'the build aborts as soon as it meets one.'),
    'report_missing': '{n} units are still missing, first: {first}.',
    'report_origin': (
        'The drafts were written with a language model and checked by machine. They '
        'are meant as suggestions, not as finished translations.'),
    'report_formal': '## Formal checks on the file',
    'report_not_built': 'The suggestion PO has not been built yet (run `build`).',
    'report_stale': 'The file no longer matches export and batches: {reason}. Rebuild it.',
    'report_no_msgfmt': 'not installed — this check was skipped',
    'exit_code': 'exit code {code}',
    'row_round_trip': 'Round trip (read back, compared character by character)',
    'mismatches': '{n} mismatches',
    'row_overlap': 'Overlap with units already translated',
    'row_coverage': 'Units in the file / in the batches',
    'row_edges': 'Units with leading/trailing whitespace, preserved',
    'report_content': '## Content checks',
    'report_where': 'The places are listed below; `work/findings.json` holds all of them.',
    'report_table_head': '| Check | Errors | Notes |',
    'report_no_findings': 'No findings.',
    'report_places': '## Findings, place by place',
    'report_places_text': (
        'Everything from the table above that is worth reading one by one, with the '
        'source and the translation. Identical placeholders and whitespace at the '
        'edges are only counted.'),
    'and_more_findings': '… and {n} more in `work/findings.json`',
    'error': 'error',
    'translation': 'Translation',
    'report_collisions': '## Collisions',
    'report_collisions_text': (
        'One target word for several source terms — a distinction the source makes '
        'may be lost. Look at each line: lists naming both terms are false alarms.'),
    'report_corrections': '## Corrections',
    'report_notes': '## Notes from the batches',
    'report_notes_text': (
        'What was flagged as uncertain or needing explanation while translating. '
        'These places should be checked in the running interface.'),
    'report_notes_head': '| No | Key | Note |',
    'report_limits': '## What is not checked',
    'limit_placeholders': (
        '**The order of identical placeholders.** {n} units contain `%s` or `%d` more '
        'than once. They bind by position and look alike; reordering the sentence '
        'swaps the values, and no check can see it. Only a human can verify this.'),
    'limit_spelling': '**Spelling.** There is no dictionary check.',
    'limit_review': (
        '**Review.** The tool cannot know whether a second person has read the drafts. '
        'Without that they remain suggestions.'),
    'limit_interface': (
        '**The interface.** No draft has been looked at next to the element it '
        'belongs to.'),
    'report_current': '## Whether the file is still current',
    'report_current_text': (
        'If the component has been worked on since the export, rebuild the file '
        'against a fresh export — otherwise it contains suggestions for units someone '
        'has since translated. The build aborts on its own in that case.'),
}

MESSAGES['de'] = {
    'batch_about': (
        'Stapel {n} von {total}, Einheiten {first} bis {last}. Dateien: {files}. '
        'Bei jeder Einheit "target" ausfüllen; Plural-Einheiten bekommen eine Liste mit '
        '{nplurals} Formen. "source" nicht ändern — daran erkennt das Werkzeug '
        'verrutschte Nummern. Wo eine Entscheidung eine Begründung braucht, "note" '
        'ergänzen.'),

    'brief_title': '# Auftrag: {project} nach {language}',
    'brief_summary': (
        '**{units} offene Einheiten** in {batches} Stapeln, davon {help} Hilfetexte '
        'und {plural} mit Pluralformen.'),
    'brief_previous': (
        'Für {n} Einheiten liegt eine frühere Fassung vor; sie steht in `work/scaffold.json` '
        'unter `previous`, zusammen mit dem damaligen Original.'),
    'brief_how_heading': '## So arbeitest du',
    'brief_one_form': (
        'Diese Sprache hat nur eine Pluralform. Bei Plural-Einheiten übersetzt du das '
        'Plural-Original (`source_plural`, mit seinem `%d`): Die eine Form erscheint '
        'bei jeder Zahl, auch bei 1.'),
    'brief_how': (
        '1. Jede Datei in `work/batches/` listet ihre Einheiten mit `source` und leerem '
        '`target`. Trag die Übersetzung in `target` ein. Plural-Einheiten bekommen eine '
        'Liste mit {nplurals} Formen.\n'
        '2. `source` bleibt, wie es ist. Daran erkennt das Werkzeug verrutschte Nummern.\n'
        '3. Wo eine Entscheidung nicht selbsterklärend ist, schreib `"note": "..."` dazu.\n'
        '4. `work/scaffold.json` enthält je Einheit mehr: frühere Fassung, Feldbeschriftung, '
        'Glossartreffer, Beispiele aus derselben Datei.\n'
        '5. Nach jedem Stapel `{check}` laufen lassen und jeden Fehler beheben.\n'
        '6. Spätere Korrekturen kommen als neue Datei nach `work/corrections/` (gleiches '
        'Format); die dürfen frühere Einträge überschreiben.\n\n'
        'Die Nummern stehen in **derselben Reihenfolge wie in Weblate** unter dem '
        'Filter `state:empty`.'),
    'brief_guidelines': '## Richtlinien',
    'brief_working': '## Arbeitsweise',
    'brief_glossary': '## Glossar',
    'english': 'Englisch',
    'brief_checks_heading': '## Was geprüft wird',
    'brief_checks': (
        '`check` meldet als **Fehler**: fehlende oder umgestellte Platzhalter, '
        'abweichende HTML-Tagfolge, fehlende Zahlen, veränderte URLs und '
        'Codebezeichner, falsche Anzahl Pluralformen, leere Einträge und Originaltexte, '
        'die nicht zum Gerüst passen.\n\n'
        'Als **Hinweis**: Randzeichen (werden beim Bauen ohnehin angeglichen), '
        'wortgleich übernommene Originale, verlorene Sätze, Begriffe, die von der im '
        'Bestand vorherrschenden Fassung abweichen, unerwünschte Formen aus dem Profil '
        'und Handwerkliches wie doppelte Wörter oder unpaarige Klammern.'),

    'brief_blocking': (
        'Dieses Profil lässt diese Hinweise **das Bauen blockieren**: {kinds}. Beheb '
        'jeden davon oder begründe in der `"note"` der Einheit, warum die Übersetzung '
        'so richtig ist. Eine Einheit mit Anmerkung blockiert nicht; die Anmerkung liest '
        'dann, wer gegenliest.'),

    'disclosure': (
        'Entwürfe für die Einheiten dieser Komponente, die im Export vom {exported}\n'
        'leer waren (letzte Revision darin: {revision}).\n'
        'Bereits übersetzte Einheiten sind nicht enthalten.\n'
        '\n'
        'Vorbereitet mit einem Sprachmodell und maschinell geprüft: Platzhalter,\n'
        'HTML-Struktur und Terminologie gegen den vorhandenen Bestand.\n'
        'Gedacht zum Einspielen als Vorschläge, nicht als fertige Übersetzungen.'),

    'none': 'Keine.',
    'and_more': '… und {n} weitere',
    'and_more_json': '… und {n} weitere. Vollständig in der JSON-Ausgabe.',
    'wanted': 'erwünscht',
    'unwanted': 'unerwünscht',
    'error_vs_note': (
        'Fehler heißt: das Original gibt etwas vor, was die Übersetzung nicht einhält. '
        'Hinweis heißt: sieh es dir an.'),

    'analysis_title': '# Bestandsanalyse — {language}',
    'analysis_basis': 'Export: `{export}`',
    'analysis_profile': 'Profil: `{profile}`',
    'analysis_counts': (
        '{units} Einheiten, davon {translated} übersetzt und {untranslated} offen. '
        'Ausgezählt wurden die {counted} übersetzten Singular-Einheiten.'),
    'analysis_table_head': '| Befund | Fehler | Hinweise |',
    'analysis_row_inconsistent': 'englische Texte mit mehr als einer Übersetzung',
    'analysis_row_collisions': 'Übersetzungen, die für mehrere englische Texte stehen',
    'analysis_inconsistent_heading': '## 1. Uneinheitlich übersetzt',
    'analysis_inconsistent_text': (
        'Derselbe englische Text, mehrere Übersetzungen. Kurze Texte zuerst — das sind '
        'die Beschriftungen, bei denen es auf dem Bildschirm auffällt.'),
    'analysis_inconsistent_head': '| Englisch | Übersetzungen |',
    'analysis_collisions_heading': '## 2. Kollisionen',
    'analysis_collisions_text': (
        'Eine Übersetzung für mehrere englische Texte. Hier verschwindet eine '
        'Unterscheidung, die das Original macht — der ernstere der beiden Befunde.'),
    'analysis_collisions_head': '| Übersetzung | steht für |',
    'analysis_defects_heading': '## 3. Formale Mängel im Bestand',
    'analysis_forms_heading': '## 4. Formen',
    'analysis_forms_text': 'Roh gezählt. Ein Treffer ist noch kein Fehler — die Liste ist zum Durchsehen da.',
    'analysis_forms_head': '| ID | Form | Einheiten | Vorkommen | im Profil |',
    'analysis_house_heading': '## 5. Hausbegriffe',
    'analysis_house_text': (
        'Was ein Begriff in diesem Paket heißt, entscheidet der Bestand. Die häufigste '
        'Variante gilt als Hausform; neue Entwürfe werden dagegen geprüft.'),
    'analysis_house_head': '| Variante | Einheiten | Beispiele |',
    'other_variant': 'keine davon',
    'house_form': 'Hausform',
    'analysis_new_translated': 'so lauten die übersetzten Einheiten mit „{term}“ bisher',
    'analysis_new_heading': '## 6. Neue Begriffe',
    'analysis_new_text': (
        'Wörter des Originals, die in den offenen Einheiten häufig und in den übersetzten '
        'selten sind. Manche sind neue Produktbegriffe oder ersetzen ältere Wörter, '
        'andere sind gewöhnliche Wörter. Jeder Produktbegriff braucht vor der Runde eine '
        'Entscheidung.'),
    'analysis_new_head': '| ID | Wort | offene Einheiten | übersetzte Einheiten | Beispiele |',

    'report_title': '# Qualitätsbericht — `{file}`',
    'report_basis': (
        'Stand: {today}. Grundlage ist der Export `{export}` vom {exported} (letzte '
        'Revision darin: {revision}), Profil `{profile}`.'),
    'report_contents': '## Inhalt',
    'report_contents_text': (
        '{translated} von {units} offenen Einheiten sind übersetzt, davon {plural} mit '
        'Pluralformen. Bereits übersetzte Einheiten kommen in der Datei nicht vor: das '
        'Bauen bricht ab, sobald eine davon auftaucht.'),
    'report_missing': 'Es fehlen noch {n} Einheiten, zuerst: {first}.',
    'report_origin': (
        'Die Entwürfe sind mit einem Sprachmodell entstanden und maschinell geprüft. '
        'Sie sind als Vorschläge gedacht, nicht als fertige Übersetzungen.'),
    'report_formal': '## Formale Prüfung der Datei',
    'report_not_built': 'Die Vorschlags-PO ist noch nicht gebaut (`build` laufen lassen).',
    'report_stale': 'Die Datei passt nicht mehr zu Export und Stapeln: {reason}. Neu bauen.',
    'report_no_msgfmt': 'nicht installiert — Gegencheck entfällt',
    'exit_code': 'Rückgabewert {code}',
    'row_round_trip': 'Rundlauf (zurückgelesen, zeichenweise verglichen)',
    'mismatches': '{n} Abweichungen',
    'row_overlap': 'Schnittmenge mit bereits übersetzten Einheiten',
    'row_coverage': 'Einheiten in der Datei / in den Stapeln',
    'row_edges': 'Einheiten mit Leerzeichen oder Umbruch am Rand, erhalten',
    'report_content': '## Inhaltliche Prüfung',
    'report_where': 'Die Stellen stehen weiter unten; `work/findings.json` enthält alle.',
    'report_table_head': '| Prüfung | Fehler | Hinweise |',
    'report_no_findings': 'Keine Befunde.',
    'report_places': '## Befunde im Einzelnen',
    'report_places_text': (
        'Alles aus der Tabelle oben, was sich einzeln anzusehen lohnt, mit Original und '
        'Übersetzung. Gleichartige Platzhalter und Randzeichen werden nur gezählt.'),
    'and_more_findings': '… und {n} weitere in `work/findings.json`',
    'error': 'Fehler',
    'translation': 'Übersetzung',
    'report_collisions': '## Kollisionen',
    'report_collisions_text': (
        'Ein Zielwort für mehrere englische Begriffe — hier kann eine Unterscheidung '
        'des Originals verloren gehen. Jede Zeile ansehen: Aufzählungen, die beide '
        'Begriffe nennen, sind Fehlalarme.'),
    'report_corrections': '## Korrekturen',
    'report_notes': '## Anmerkungen aus den Stapeln',
    'report_notes_text': (
        'Was beim Übersetzen als unsicher oder begründungsbedürftig vermerkt wurde. '
        'Diese Stellen gehören an der Oberfläche geprüft.'),
    'report_notes_head': '| Nr | Schlüssel | Anmerkung |',
    'report_limits': '## Was nicht geprüft ist',
    'limit_placeholders': (
        '**Die Reihenfolge gleichartiger Platzhalter.** {n} Einheiten enthalten `%s` '
        'oder `%d` mehr als einmal. Sie binden über ihre Stellung im Satz und sehen '
        'gleich aus; wer den Satz umstellt, vertauscht die Werte, und keine Prüfung '
        'sieht das. Nur von Hand prüfbar.'),
    'limit_spelling': '**Rechtschreibung.** Es gibt keine Wörterbuchprüfung.',
    'limit_review': (
        '**Gegenlesen.** Ob ein zweiter Mensch die Entwürfe gesehen hat, weiß das '
        'Werkzeug nicht. Ohne das sind sie Vorschläge.'),
    'limit_interface': (
        '**Die Oberfläche.** Kein Entwurf ist neben dem Element betrachtet worden, zu '
        'dem er gehört.'),
    'report_current': '## Ob die Datei noch passt',
    'report_current_text': (
        'Ist in der Komponente seit dem Export weitergearbeitet worden, die Datei gegen '
        'einen frischen Export neu bauen — sonst enthält sie Vorschläge für Einheiten, '
        'die inzwischen jemand übersetzt hat. Das Bauen bricht in dem Fall von sich aus ab.'),
}

KINDS = {
    'en': {
        'placeholder': 'Placeholders',
        'html': 'HTML tag sequence',
        'numbers': 'Numbers from the source',
        'literal': 'URLs, paths, code identifiers',
        'plural': 'Plural forms',
        'empty': 'Empty',
        'unknown': 'Number not in the scaffold',
        'batch': 'Broken or shifted batch entries',
        'unchanged': 'Identical to the source',
        'sentences': 'Sentences lost',
        'edges': 'Leading/trailing whitespace',
        'term': 'Terms against existing translations',
        'form': 'Forms from the profile',
        'craft': 'Doubled words, brackets, spaces',
        'title_material': 'Help title differs from field label',
        'title_cosmetic': 'Help title, spelling only',
    },
    'de': {
        'placeholder': 'Platzhalter',
        'html': 'HTML-Tagfolge',
        'numbers': 'Zahlen aus dem Original',
        'literal': 'URLs, Pfade, Codebezeichner',
        'plural': 'Pluralformen',
        'empty': 'leer',
        'unknown': 'Nummer nicht im Gerüst',
        'batch': 'kaputte oder verrutschte Stapeleinträge',
        'unchanged': 'wortgleich mit dem Original',
        'sentences': 'Sätze verloren',
        'edges': 'Randzeichen',
        'term': 'Begriffe gegen den Bestand',
        'form': 'Formen aus dem Profil',
        'craft': 'Doppelwörter, Klammern, Leerzeichen',
        'title_material': 'Hilfetitel weicht von Feldbeschriftung ab',
        'title_cosmetic': 'Hilfetitel, nur Schreibweise',
    },
}

LANGUAGES = sorted(MESSAGES)


def text(lang, key, **values):
    catalog = MESSAGES.get(lang, MESSAGES['en'])
    template = catalog.get(key, MESSAGES['en'][key])
    return template.format(**values) if values else template


def kind_label(lang, kind):
    return KINDS.get(lang, KINDS['en']).get(kind) or KINDS['en'].get(kind, kind)
