from agentic_bias_lens.cli import main


def test_cli_dry_run_creates_report(tmp_path):
    out = tmp_path / "run1"
    rc = main(["--dry-run", "--out", str(out), "--models", "gpt-image-1"])
    assert rc == 0
    assert (out / "report.md").exists()
    assert (out / "prompts.json").exists()


def test_cli_report_only_rebuilds(tmp_path):
    out = tmp_path / "run2"
    main(["--dry-run", "--out", str(out), "--models", "gpt-image-1"])
    (out / "report.md").unlink()
    rc = main(["--report-only", "--out", str(out)])
    assert rc == 0
    assert (out / "report.md").exists()
