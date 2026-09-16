"""Run the whole thing, in order. Stages 3,5,6 are deterministic - no model, no key.

    python agent/run_pipeline.py            # verification stages only (no key needed)
    python agent/run_pipeline.py --full     # re-run research + blind verify too

Order matters: merge rebuilds apps.json from data/raw/, so corrections and
adjudications must be re-applied after it.
"""
import argparse, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
RESEARCH = ["research_agent.py", "verify_blind.py"]
DETERMINISTIC = ["merge.py", "check_links.py", "recheck_dead.py", "check_mcp.py",
                 "apply_corrections.py", "score.py", "apply_adjudications.py", "analyze.py"]

def run(script):
    print(f"\n=== {script} " + "=" * (58 - len(script)))
    r = subprocess.run([sys.executable, str(HERE / script)], cwd=HERE.parent)
    if r.returncode != 0:
        sys.exit(f"{script} failed with {r.returncode}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="also re-run the model-backed stages (needs ANTHROPIC_API_KEY)")
    args = ap.parse_args()
    stages = (RESEARCH if args.full else []) + DETERMINISTIC
    for s in stages:
        run(s)
    print("\ndone. dataset: data/apps.json   accuracy: data/verify/accuracy.json")
