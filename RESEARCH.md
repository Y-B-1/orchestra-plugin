# Model selection evidence — 2026-09-30

The Codex matrix prioritizes gpt-6.1-sol. Only red team and checked builder repair use Astra, capped at medium. Luna performs bounded read-only discovery and hygiene at high. The main client retains control of its own model.

## Primary sources

- [GPT-6 Luna model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna): supports high and xhigh. Standard short-context API rates are $0.10 input and $0.50 output per million tokens. These rates are not Codex subscription allowance measurements.
- [Reasoning guide](https://developers.openai.com/api/docs/guides/reasoning): higher effort can increase reasoning, latency and token usage. Reasoning tokens are billed as output tokens. A fixed token rate does not imply a fixed task cost.
- [GPT-6 Sol and Luna evaluations](https://openai.com/index/introducing-gpt-6-sol-and-luna/): Luna high improves AutomationBench by 5.4 percentage points over its predecessor at 58% lower estimated task cost. Luna max scores 66.6% on DeepSWE. These are different benchmarks and settings; neither comparison establishes a high-versus-xhigh optimum for Orchestra's read-only roles. Provider evaluations can differ from production prompts and tools.

## Selection and limits

Luna high follows the user's quality preference while preserving bounded responsibilities. Sol handles architecture, external research, builds, approval, gates and release. Astra is a narrow independent challenge/repair valve. This is a reasoned default, not a measured winner on private project tasks. Test representative source-finding and cleanup scenarios before broadening Luna's role. Refresh this evidence when the host catalog, pricing or assignment changes.

The current desktop catalog supports Luna high/xhigh, Sol high and Astra medium. Host support does not establish availability for a separate CLI/account. No model benchmark or price changes role authority, ownership or evidence requirements.
