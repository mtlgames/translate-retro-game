"""Run one read-only review with the project's review agent, for harnesses without subagents (e.g. an Orca worker).

    python review_agent.py SPEC --out FILE [--image PNG ..] < prompt.md

SPEC is agent[:model[:effort]] (the review agent in docs/decisions.md), agent one of:
  claude    claude:claude-opus-5-5:high      claude -p, only Read/Grep/Glob allowed
  codex     codex:gpt-5.5:high               codex exec -s read-only
  opencode  opencode:opencode-go/kimi-k3.1-pro  opencode run --agent plan (no effort)
The prompt comes on stdin: Windows .cmd shims cut arguments at newlines. The reviewer's last message is written to
--out, which is deleted first so a failed run never leaves the last run's verdicts behind. Exit 1 if it is empty.
The reviewer can't start processes or write files: put the brief, batch and terms in the prompt.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

AGENTS = ("claude", "codex", "opencode")


def command(spec: str, out: Path, images: list) -> list:
    agent, model, effort = (spec.split(":", 2) + ["", ""])[:3]
    if agent == "claude":
        return (["claude", "-p", "--permission-mode", "dontAsk", "--allowedTools", "Read", "Grep", "Glob"]
                + (["--model", model] if model else []) + (["--effort", effort] if effort else []))
    if agent == "codex":
        return (["codex", "exec", "-s", "read-only", "--skip-git-repo-check", "-o", str(out)]
                + (["-m", model] if model else []) + (["-c", f"model_reasoning_effort={effort}"] if effort else [])
                + [a for i in images for a in ("-i", i)] + ["-"])
    if agent == "opencode":
        return (["opencode", "run", "--agent", "plan", "--format", "json"] + (["-m", model] if model else [])
                + [a for i in images for a in ("-f", i)])
    raise SystemExit(f"bad spec {spec!r}: want agent[:model[:effort]], agent one of {', '.join(AGENTS)}")


def opencode_text(stdout: str) -> str:
    """Text of opencode's last step: earlier steps are tool calls with commentary."""
    text = []
    for line in stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "step_start":
            text = []
        elif e.get("type") == "text":
            text.append(e["part"]["text"])
    return "".join(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--image", action="append", default=[])
    a = ap.parse_args()
    cmd = command(a.spec, a.out, a.image)
    prompt = sys.stdin.buffer.read().decode("utf-8")
    if a.image and cmd[0] == "claude":  # claude -p has no image flag; its Read tool opens them
        prompt += "\n\nImages to read:\n" + "\n".join(a.image)
    exe = shutil.which(cmd[0]) or sys.exit(f"{cmd[0]} not on PATH")
    a.out.unlink(missing_ok=True)
    r = subprocess.run([exe, *cmd[1:]], input=prompt.encode("utf-8"), stdout=subprocess.PIPE)
    if cmd[0] != "codex":
        out = r.stdout.decode("utf-8", "replace")
        a.out.write_text(opencode_text(out) if cmd[0] == "opencode" else out, encoding="utf-8")
    if r.returncode or not a.out.exists() or not a.out.read_text(encoding="utf-8").strip():
        sys.exit(f"{a.spec}: no review written (exit {r.returncode})")


if __name__ == "__main__":
    main()
