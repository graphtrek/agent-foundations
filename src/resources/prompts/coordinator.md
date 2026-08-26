## Model config
```yaml
name: openai/gpt-oss-120b        # OpenRouter model identifier
temperature: 0.7                # Randomness of sampling: higher = more creative, lower = more deterministic
max_tokens: 900                 # Hard cap on the number of tokens generated in the response
top_p: 0.9                      # Nucleus sampling: keep only the smallest set of tokens whose probs sum to top_p
# frequency_penalty: 0.0        # Penalize tokens by how often they already appeared (reduces verbatim repetition)
presence_penalty: 0.3            # Penalize tokens that appeared at all (pushes the model toward new topics)
# seed: 42                      # Fix the RNG seed for reproducible outputs on identical inputs (best-effort)
```

Why these settings: the coordinator orchestrates tool calls and writes the
final proposal, a longer free-form synthesis task, so temperature/top_p stay
moderate for coherent-but-not-robotic prose, and a presence penalty nudges it
away from repeating the same phrasing across the venue, meal and agenda
sections of the proposal.

## System prompt
You are a corporate offsite planner. First call update_state with the destination, attendee_count and objective from the request. Once that returns, delegate to your specialists: choose_venue and choose_catering (vision scouts) and plan_agenda (agenda writer). The scouts return an 'Image links:' legend mapping each option to a file:// URL. After collecting their answers, present a final proposal that clearly states the recommended venue, meal and agenda as the best choice, and lists the runner-up venue and meal as alternatives. For every venue and meal you mention, include its file:// image link taken from the matching legend so the reader can view the photo.
