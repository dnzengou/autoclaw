# Evolve a spam-classifier system prompt

## MISSION
Write a system prompt that makes the model classify each message in
`data.jsonl` as `spam` or `ham`. The data mixes obvious spam (prize scams,
phishing, miracle pills) with ham that looks spammy on the surface
(transactional emails that say "FREE trial", legitimate messages with
"CLICK here" or "unsubscribe"). The hard cases are the ones that use
spam-shaped vocabulary in a legitimate context.

## PARAMETERS
`train.py` takes `--prompt <text>` (required), and optional `--model` and
`--temperature`. Each hypothesis MUST include a `"prompt"` key. Keep
prompts under ~600 tokens.

## CONSTRAINTS
- The model's reply must contain `spam` or `ham` as a whole word.
  Everything else counts as `unknown` and is scored wrong.
- The baseline (`"You are a spam detector. Reply spam or ham."`) scores
  around F1 = 0.75 on this set. The target is F1 ≥ 0.95.

## HYPOTHESES
- Ask the model to ignore spam-shaped vocabulary that appears in
  transactional contexts (order numbers, delivery notices, calendar).
- Give a few in-prompt examples, especially of the ham-with-spam-words cases.
- Have the model reason internally about intent (is this unsolicited bulk
  commercial mail?) before answering — but still reply with one word.

## LEARNINGS
(empty — this is the first run)
