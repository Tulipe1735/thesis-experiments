"""Calibrate Qwen as a top-down fact annotator, never as the success oracle."""

import argparse
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from experiments.t0_agent_v1.common import read, relative, sha, write_new

AUDIT = ROOT / "experiments/grow_up_harness_v2/runs/t01_evaluator_audit_20261106_001"
URL = "http://192.168.31.203:11434/api/generate"
MODEL = "qwen3.5:4b"
CASES = {
    "success_control": {"official": True, "support": True, "inside_1mm": True, "upright": True,
                        "hand": False, "other": False},
    "program_success": {"official": True, "support": True, "inside_1mm": True, "upright": True,
                        "hand": False, "other": False},
    "margin_0p747mm": {"official": False, "support": True, "inside_1mm": False, "upright": True,
                       "hand": False, "other": False},
    "rim_lean": {"official": False, "support": True, "inside_1mm": False, "upright": True,
                 "hand": False, "other": True},
    "negative_wait": {"official": False, "support": False, "inside_1mm": False, "upright": True,
                      "hand": False, "other": False},
}
PROMPT = """You are a diagnostic image annotator for a robot tabletop task.
The image is a top-down view. The blue rectangular object is the tray.
The white cup may be on the table, on the tray, or touching the tray rim.

Report only visible facts. Do not output an overall success verdict.
If the cup base is occluded or the base/rim relation is within a few pixels, use "unknown".
Return strict JSON with exactly these keys:
{
  "cup_present": true|false|"unknown",
  "cup_base_visible": true|false|"unknown",
  "cup_base_on_tray_floor": true|false|"unknown",
  "cup_base_inside_tray_rim": true|false|"unknown",
  "cup_upright": true|false|"unknown",
  "hand_touching_cup": true|false|"unknown",
  "other_objects_touching_cup": true|false|"unknown",
  "confidence": 0.0,
  "visible_evidence": "short text"
}
The base is the circular bottom of the cup, not the cup opening or handle.
"""


def ask(image: Path) -> tuple[dict, float, str]:
    payload = {
        "model": MODEL, "prompt": PROMPT, "stream": False, "format": "json",
        "options": {"temperature": 0},
        "images": [base64.b64encode(image.read_bytes()).decode("ascii")],
    }
    request = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = json.loads(response.read().decode())
    text = raw["response"]
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = {"parse_error": text[:500]}
    return parsed, time.monotonic() - started, text


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    model_info = {"name": MODEL, "server": URL, "temperature": 0,
                  "prompt_sha256": sha(Path(__file__))}
    write_new(output / "registration.json", {
        "date": "2026-11-06", "kind": "qwen_topdown_triage_calibration",
        "status": "registered_before_requests", "boundary": "existing rendered images only; no physics",
        "images": "top-down 720x720 from t01_evaluator_audit_20261106_001",
        "cases": list(CASES), "model": model_info, "prompt": PROMPT,
        "prediction": "top-down view may fix gross table/tray confusion but cannot resolve 1 mm; known positives may still be false negatives",
        "falsification": "if Qwen labels a sub-mm case as fully inside with high confidence, the prompt is overclaiming; if it fails a known positive, it remains diagnostic only",
        "official_verdict_unchanged": True,
    })
    rows = []
    raw_dir = output / "raw"
    raw_dir.mkdir()
    for label, truth in CASES.items():
        image = AUDIT / "images/top" / f"{label}_top.png"
        if not image.is_file():
            raise FileNotFoundError(image)
        parsed, wall, raw = ask(image)
        (raw_dir / f"{label}.json").write_text(json.dumps(parsed, indent=2) + "\n")
        (raw_dir / f"{label}.txt").write_text(raw + "\n")
        facts = {key: parsed.get(key) for key in
                 ("cup_present", "cup_base_visible", "cup_base_on_tray_floor",
                  "cup_base_inside_tray_rim", "cup_upright", "hand_touching_cup",
                  "other_objects_touching_cup", "confidence")}
        response_ok = all(facts[key] is not None for key in
                          ("cup_present", "cup_base_visible", "cup_base_on_tray_floor",
                           "cup_base_inside_tray_rim", "cup_upright", "hand_touching_cup",
                           "other_objects_touching_cup", "confidence"))
        rows.append({
            "label": label, "image": relative(image), "wall_s": wall,
            "parsed": parsed, "truth": truth, "response_ok": response_ok, "facts": facts,
        })
    fields = ("cup_base_on_tray_floor", "cup_base_inside_tray_rim", "cup_upright",
              "hand_touching_cup", "other_objects_touching_cup")
    truth_key = {"cup_base_on_tray_floor": "support", "cup_base_inside_tray_rim": "inside_1mm",
                 "cup_upright": "upright", "hand_touching_cup": "hand",
                 "other_objects_touching_cup": "other"}
    responded = [row for row in rows if row["response_ok"]]
    summary = {}
    for field in fields:
        key = truth_key[field]
        agree = sum(row["facts"].get(field) is row["truth"][key] for row in responded)
        summary[field] = {"agree": agree, "n": len(responded),
                          "unknown": sum(row["facts"].get(field) == "unknown" for row in responded)}
    summary["official_agreement"] = sum(
        (row["facts"].get("cup_base_inside_tray_rim") is True
         and row["facts"].get("cup_base_on_tray_floor") is True
         and row["facts"].get("cup_upright") is True
         and row["facts"].get("hand_touching_cup") is False
         and row["facts"].get("other_objects_touching_cup") is False) is row["truth"]["official"]
        for row in responded)
    summary["responded"] = len(responded)
    summary["empty_or_invalid"] = len(rows) - len(responded)
    summary["n"] = len(rows)
    result = {"model": model_info, "prompt": PROMPT, "rows": rows, "summary": summary,
              "diagnostic_only": True, "official_verdict_changed": False,
              "note": "Qwen is not a success oracle; use physical dense/official evaluation for success."}
    write_new(output / "triage.json", result)
    print(json.dumps(summary, indent=2))
    for row in rows:
        print(row["label"], row["facts"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output.resolve())
