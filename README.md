# Vibenix - AI assistant for nix packaging

Vibenix is an AI agent that automatically produces hermetic Nix expressions for real-world projects, using two key techniques: a log-driven loop that incrementally fixes build failures, and a post-build evaluator–optimizer process that improves correctness and package quality. Additionally, Vibenix can also perform maintenance on pre-existing packages, ensuring long-term project support. 

Vibenix uses a large language model (LLM) to iteratively refine recipes through a rule-guided build-repair feedback loop. On 466 packaging tasks from our new NixBench dataset, Vibenix produced buildable packages in 95.3% of cases using Claude Haiku 4.5, compared with 5.6% for a state-of-the-art LLM-based single-shot packaging tool. Manual validation of 100 packages revealed that 47% of the buildable packages were initially functionally correct; a post-build refinement process based on the evaluator-optimizer pattern increased functional correctness by 35 percentage points. On our new NixBench-Repair dataset of package maintenance tasks, Vibenix achieved an 87.6% success rate.

To run vibenix with the default terminal UI:
```
nix develop -c python -m vibenix
```

You will be asked to pick a model and also provide an API key if required.

**Note:** There is also a `--textual` flag for a Textual-based UI, but it is currently unmaintained and not recommended for use.
