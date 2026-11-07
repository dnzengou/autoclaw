# Evolve a phone-number regex

## MISSION
Find a Python regex (`re` module syntax) that matches every phone number in
`data.jsonl` and nothing else. The data mixes US formats (parenthesised area
code, hyphens, dots, spaces, country code `+1`), one UK number, one French
number, and a toll-free US number. Negatives include dates, SKUs, credit
cards, IPv6 addresses, dotted version numbers, and plain lists of integers.

## PARAMETERS
`train.py` accepts `--pattern <regex>` and an optional `--flags <letters>`
where letters are any of `i`, `m`, `s`, `x`. Each hypothesis MUST include a
`"pattern"` key; `"flags"` is optional.

## CONSTRAINTS
- Pure Python `re` (no `regex` module); no lookbehinds wider than 255 chars.
- A single match per string over 10 ms counts as a failure (catastrophic
  backtracking is not a win).
- The goal is F1 = 1.0. Primary metric is `f1`.

## HYPOTHESES
- `\d{3}[-. ]?\d{3}[-. ]?\d{4}` catches most US formats but also credit cards
  and dates.
- Use word boundaries (`\b`), negative lookahead for digit continuation
  (`(?!\d)`), and a leading country code group (`(?:\+?\d{1,3}[ .-]?)?`).

## LEARNINGS
(empty — this is the first run)
