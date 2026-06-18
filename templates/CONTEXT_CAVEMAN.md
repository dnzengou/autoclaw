# AUTOCALW

## MISSION
Self-improving loop. Human: context. AI: code. Repeat.

## CONSTRAINTS
- Budget: 300s
- Metric: val_bpb ↓
- Target: train.py
- Branch: autoclaw-*

## STATE
- Best: N/A
- Iter: 0
- Runtime: 0s

## HYPOTHESES
1. lr 0.001→0.003
2. dropout 0.1
3. batch 32→64
4. AdamW vs Adam
5. grad_clip 1.0

## LEARNINGS
<!-- AI adds -->

## AVOID
- Multi-param changes
- Ignore OOM
- Skip validation

## TOOLS
- file R/W
- shell
- git
- metrics

## WIN
- val_bpb < 2.0
- 10 iter no crash
- >5000 tok/s
