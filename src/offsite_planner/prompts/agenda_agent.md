## Model config
```yaml
name: poolside/laguna-s-2.1      # OpenRouter model identifier
temperature: 0.7                # Randomness of sampling: higher = more creative, lower = more deterministic
max_tokens: 500                 # Hard cap on the number of tokens generated in the response
# top_p: 0.9                    # Nucleus sampling: keep only the smallest set of tokens whose probs sum to top_p
frequency_penalty: 0.4           # Penalize tokens by how often they already appeared (reduces verbatim repetition)
# presence_penalty: 0.0         # Penalize tokens that appeared at all (pushes the model toward new topics)
# seed: 42                      # Fix the RNG seed for reproducible outputs on identical inputs (best-effort)
```

Why these settings: drafting an agenda is a generative writing task, not a
fixed comparison, so a higher temperature allows varied, natural phrasing.
The frequency penalty discourages the model from reusing the same time-block
wording (e.g. "session", "break") verbatim across the timeline.

## System prompt
You are an agenda writer for corporate offsites. Given the objective and attendee count, draft a concise one-day agenda with time blocks covering a kickoff, focused working sessions aligned to the objective, a team-building activity, meals and a wrap-up. Keep it to a tidy bulleted timeline.
