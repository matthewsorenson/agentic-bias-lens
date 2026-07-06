# examples/mock-run

This is a committed run produced by `--dry-run` (fake providers, no API keys, `--k-img 1`). It lets a
reviewer read a full report end to end without running anything.

The report, manifest, prompts, and scores are real artifacts from the run. The images under
`images/` have been **replaced with REDACTED placeholder tiles**: this project never commits
generated images, even synthetic ones from a mock run, so the example models the same policy a real
run must follow. See [`../ETHICS.md`](../ETHICS.md).

Regenerate locally with:

```
python -m agentic_bias_lens --dry-run --out examples/mock-run --k-img 1
```
