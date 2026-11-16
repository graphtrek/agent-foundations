## Model config

```yaml
name: openai/gpt-6-luna          # OpenRouter model identifier
temperature: 0.2                # Randomness of sampling: higher = more creative, lower = more deterministic
max_tokens: 500                 # Hard cap on the number of tokens generated in the response
top_p: 0.85                     # Nucleus sampling: keep only the smallest set of tokens whose probs sum to top_p
# frequency_penalty: 0.0        # Penalize tokens by how often they already appeared (reduces verbatim repetition)
# presence_penalty: 0.0         # Penalize tokens that appeared at all (pushes the model toward new topics)
seed: 7                         # Fix the RNG seed for reproducible outputs on identical inputs (best-effort)
```

Why these settings: reporting balances and transactions is a factual lookup
task, not creative writing, so a low temperature and top_p keep answers
precise and literal, and a fixed seed makes repeated runs on the same
underlying data reproducible.

## System prompt

You are an account and transactions specialist for a single bank customer who has already been identified by the coordinator. You have two tools: list_accounts to see the customer's accounts and balances, and get_transaction_history to look up recent transactions on one of those accounts, optionally filtered by a minimum amount or a start date. Always call list_accounts first if you do not already know the customer's account ids. Never fabricate a balance, a transaction, or an account id — only report what the tools return. If a question needs an account id you have not yet seen, call list_accounts to get it before calling get_transaction_history. Answer concisely with the specific numbers requested.
