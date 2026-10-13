"""Read the header line twice with Qwen3-0.6B and record every head's attention.

    python extract.py --snapshot <huggingface snapshot dir of Qwen/Qwen3-0.6B> --out attention.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

from scores import check_causal, pick_heads, score_all

MODEL = "Qwen/Qwen3-0.6B"
SENTENCE = " Every number on this page came from a run."


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.use_deterministic_algorithms(True)

    tokenizer = AutoTokenizer.from_pretrained(args.snapshot)
    ids = tokenizer(SENTENCE, add_special_tokens=False)["input_ids"]
    if len(set(ids)) != len(ids):
        raise ValueError("a token repeats inside the line, so induction targets would be ambiguous")
    sequence = ids + ids
    if tokenizer(SENTENCE + SENTENCE, add_special_tokens=False)["input_ids"] != sequence:
        raise ValueError("the line does not tokenize identically when read twice")

    model = AutoModelForCausalLM.from_pretrained(
        args.snapshot, dtype=torch.float32, attn_implementation="eager"
    ).eval()
    with torch.no_grad():
        output = model(torch.tensor([sequence]), output_attentions=True)
    attentions = torch.stack(output.attentions)[:, 0].double().numpy()

    check_causal(attentions)
    scores = score_all(attentions, period=len(ids))
    heads = [
        {
            "role": role,
            "layer": layer,
            "head": head,
            "score": round(float(scores[role][layer, head]), 6),
            "pattern": np.round(attentions[layer, head], 6).tolist(),
        }
        for role, layer, head in pick_heads(scores)
    ]
    here = Path(__file__).resolve().parent
    record = {
        "config": {
            "model": MODEL,
            "revision": args.snapshot.resolve().name,
            "dtype": "float32",
            "device": "cpu",
            "attn_implementation": "eager",
            "seed": args.seed,
            "sentence": SENTENCE,
            "period": len(ids),
            "token_ids": sequence,
            "tokens": [tokenizer.decode([i]) for i in sequence],
            "layers": int(attentions.shape[0]),
            "heads_per_layer": int(attentions.shape[1]),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "numpy": np.__version__,
            "extract_sha256": sha256(here / "extract.py"),
            "scores_sha256": sha256(here / "scores.py"),
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "scores": {role: np.round(values, 6).tolist() for role, values in scores.items()},
        "heads": heads,
    }
    text = json.dumps(record, indent=1)
    text = re.sub(r"\[\n\s+([-0-9.e+,\s]+?)\n\s*\]", lambda m: "[" + " ".join(m.group(1).split()) + "]", text)
    args.out.write_text(text + "\n")
    for head in heads:
        print(f"{head['role']:>15}  layer {head['layer']:>2}  head {head['head']:>2}  score {head['score']:.4f}")


if __name__ == "__main__":
    main()
