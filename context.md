# Context

## Goal
Improve the F1 score of a text classifier on a sentiment analysis benchmark. Current baseline: F1=0.82.

## Constraints
- Budget: 300 seconds total experiment time
- Model: DistilBERT-base-uncased
- GPU: optional (CPU fallback)
- Max sequence length: 128 tokens

## Preferences
- Prefer data augmentation and preprocessing changes over model architecture changes
- Keep inference under 2ms per sample on CPU
- Avoid increasing model size

## LLM Configuration
- Default model: DeepSeek Chat (deepseek-chat)
- Set DEEPSEEK_API_KEY environment variable for LLM-powered hypothesis generation
- Falls back to heuristic generator if no API key is set
- Also supports: ANTHROPIC_API_KEY, OPENAI_API_KEY

## Notes
- Baseline: AdamW lr=2e-5, batch_size=16, 3 epochs
- Experiment 1: Tried learning rate 5e-5 → F1 dropped to 0.79
- Experiment 2: Added dropout 0.2 → F1=0.81 (slightly worse)
- Experiment 3: Increased epochs to 5 → F1=0.83 (small improvement)
- The baseline optimizer seems reasonable, try data augmentation next
