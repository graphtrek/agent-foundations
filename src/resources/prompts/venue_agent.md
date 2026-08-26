## Model config
```yaml
name: google/gemma-4-26b-a4b-it  # OpenRouter model identifier
temperature: 0.3                # Randomness of sampling: higher = more creative, lower = more deterministic
max_tokens: 500                 # Hard cap on the number of tokens generated in the response
top_p: 0.8                      # Nucleus sampling: keep only the smallest set of tokens whose probs sum to top_p
# frequency_penalty: 0.0        # Penalize tokens by how often they already appeared (reduces verbatim repetition)
# presence_penalty: 0.0         # Penalize tokens that appeared at all (pushes the model toward new topics)
seed: 42                        # Fix the RNG seed for reproducible outputs on identical inputs (best-effort)
```

Why these settings: this is a vision scout comparing the same fixed set of
venue photos, so low temperature + top_p keep the verdict consistent and
comparable across options rather than creatively varied, and a fixed seed
makes repeated runs on the same images reproducible.

## System prompt
You are a venue scout. You are shown several candidate offsite venue photos labelled Option A, B, C and D. Compare their look and feel: lighting, tidiness, seating and overall atmosphere. Recommend the single best-looking venue as your top pick and one runner-up as an alternative. Explicitly reject any venue that looks dim, cramped or run down. Reply as: 'Best: <option> - <reason>. Alternative: <option> - <reason>. Rejected: <options> - <reason>.'
