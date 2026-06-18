# AUTOCALW CONTEXT

## MISSION
Build self-improving automation. Human edits this file. AI edits code. Loop forever.

## CONSTRAINTS
- Time budget: 300s per experiment
- Metric: lower validation loss = better  
- Single file target: train.py
- Git branch: autoclaw-*
- Max iterations: 1000

## CURRENT STATE
- Best score: N/A
- Iterations: 0
- Last hypothesis: N/A
- Runtime: 0s

## HYPOTHESIS QUEUE
1. Increase learning rate 0.001 → 0.003 for faster convergence
2. Add dropout 0.1 for regularization
3. Tune batch size 32 → 64 for memory efficiency
4. Try AdamW instead of Adam
5. Add gradient clipping max_norm=1.0

## LEARNINGS
<!-- AI appends here -->

## ANTI-PATTERNS
- Don't change multiple hyperparams at once
- Don't ignore OOM errors
- Don't skip validation

## TOOLS
- File read/write
- Shell exec  
- Git ops
- Metrics collect
- Web search

## SUCCESS CRITERIA
- val_bpb < 2.0
- No crashes for 10 iterations
- Training speed > 5000 tok/s
