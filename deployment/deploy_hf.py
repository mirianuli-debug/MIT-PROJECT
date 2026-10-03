"""
HuggingFace deployment helper for GenAI Phishing Detector.

Deploys two repos:
  1. MODEL_REPO (type=model) - the fine-tuned DistilBERT weights + tokenizer
  2. SPACE_REPO (type=space) - the Streamlit app that loads those weights

The weights are never committed to git; they live only in the model repo. The
Space downloads them at runtime through the HF_MODEL_ID variable declared in the
front-matter of README.md.

Usage:
    set HF_TOKEN=<hf_write_token>
    py deployment/deploy_hf.py --user <hf_username>

Or pass the token directly (prefer the environment variable so it stays out of
your shell history):
    py deployment/deploy_hf.py --user <hf_username> --token <hf_write_token>
"""

import argparse
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Repo names
# ---------------------------------------------------------------------------
# HuggingFace namespaces are shared across repo types, so the model repo and the
# Space repo cannot share a name. The weights take the plain name, the demo app
# gets the "-demo" suffix.
DEFAULT_MODEL_REPO = "genaimitproject"
DEFAULT_SPACE_REPO = "genaimitproject-demo"

# Files to upload, as (local dir, [files in that dir]) pairs.
MODEL_FILES = [("phishing_model", ["config.json", "model.safetensors"])]
TOKENIZER_FILES = [("tokenizer", ["tokenizer.json", "tokenizer_config.json"])]

MODEL_CARD = """---
library_name: transformers
license: mit
tags:
  - phishing-detection
  - distilbert
  - text-classification
  - cybersecurity
  - nigerian-financial-sector
---

# GenAI Phishing Detector

Fine-tuned **DistilBERT** for three-way classification of financial-sector
messages in the Nigerian context.

| Label | Class | Description |
|-------|-------|-------------|
| 0 | Legitimate | Authentic bank communications (debit alerts, transfer confirmations, KYC reminders) |
| 1 | Traditional Phishing | Low-effort phishing with grammatical errors and suspicious links |
| 2 | AI-Generated Phishing | Polished, professionally written LLM-generated phishing |

## Usage

```python
from transformers import pipeline

classifier = pipeline(
    "text-classification",
    model="mirianuli-debug/genaimitproject",
    truncation=True,
    max_length=128,
)

print(classifier("URGENT!!! Your BVN has been BLOCKED. Click here to verify now: https://account-verify.tk/38472"))
```

## Training data

5000 procedurally generated samples (seed 42) across three classes.

## Evaluation caveat

The original random-split evaluation reports 1.0000 across all metrics. That
split allows template-sibling samples to appear in both train and test, so the
score overstates real-world performance. A template-aware group split with zero
shared template families is included in the repository for an honest comparison;
see `experiments/template_aware_split/` and `notebooks/template_aware_experiment.ipynb`.

## Framework versions

- transformers
- PyTorch
"""


def check_weights() -> None:
    """Verify the local model and tokenizer files exist before uploading."""
    missing = []
    for subdir, filenames in MODEL_FILES + TOKENIZER_FILES:
        base = PROJECT_ROOT / "models" / subdir
        for name in filenames:
            path = base / name
            if path.exists():
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"  OK  {subdir}/{name:24s} {size_mb:8.2f} MB")
            else:
                missing.append(f"models/{subdir}/{name}")

    if missing:
        print("\nERROR: missing files needed for upload:")
        for m in missing:
            print(f"  - {m}")
        print("\nTrain the model first. notebooks/training_notebook.ipynb writes the")
        print("weights into models/phishing_model/ and the tokenizer into")
        print("models/tokenizer/, then downloads them as phishing_model.zip.")
        sys.exit(1)


def upload_weights(api: HfApi, repo_id: str) -> None:
    """Upload the model config, weights, tokenizer and model card."""
    for subdir, filenames in MODEL_FILES + TOKENIZER_FILES:
        for name in filenames:
            local = PROJECT_ROOT / "models" / subdir / name
            print(f"  uploading {subdir}/{name} ...")
            api.upload_file(
                path_or_fileobj=str(local),
                path_in_repo=name,
                repo_id=repo_id,
                repo_type="model",
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy to the HuggingFace Hub")
    parser.add_argument("--user", required=True, help="HuggingFace username")
    parser.add_argument("--token", help="HF write token (or set HF_TOKEN)")
    parser.add_argument("--model-repo", default=DEFAULT_MODEL_REPO)
    parser.add_argument("--space-repo", default=DEFAULT_SPACE_REPO)
    parser.add_argument("--private", action="store_true", help="Make the model repo private")
    parser.add_argument("--skip-model", action="store_true", help="Deploy only the Space")
    args = parser.parse_args()

    token = args.token or os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("No token provided. Set HF_TOKEN or pass --token.")

    model_id = f"{args.user}/{args.model_repo}"
    space_id = f"{args.user}/{args.space_repo}"

    print("=" * 68)
    print("GenAI Phishing Detector - HuggingFace deployment")
    print("=" * 68)
    print(f"  Model repo : {model_id}")
    print(f"  Space repo : {space_id}")

    api = HfApi(token=token)
    who = api.whoami()
    print(f"\nAuthenticated as: {who.get('name', 'unknown')}")

    if args.skip_model:
        print("\nSkipping the model upload.")
    else:
        print("\n--- Step 1/3: checking local weights ---")
        check_weights()

        print("\n--- Step 2/3: creating the model repo ---")
        api.create_repo(
            repo_id=model_id,
            repo_type="model",
            exist_ok=True,
            private=args.private,
        )
        print(f"  ready: https://huggingface.co/{model_id}")

        print("\n--- Step 3/3: uploading weights and model card ---")
        upload_weights(api, model_id)
        api.upload_file(
            path_or_fileobj=MODEL_CARD.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=model_id,
            repo_type="model",
        )
        print(f"  done: https://huggingface.co/{model_id}")

    print("\n--- Creating the Space repo ---")
    api.create_repo(
        repo_id=space_id,
        repo_type="space",
        space_sdk="streamlit",
        exist_ok=True,
    )
    print(f"  ready: https://huggingface.co/spaces/{space_id}")

    print("\n" + "=" * 68)
    print("Remaining manual steps")
    print("=" * 68)
    print("HF_MODEL_ID is declared in the README.md front-matter, so the Space picks")
    print("it up automatically once the code is pushed. Update that line if your")
    print("username differs.\n")
    print("1. Push the app code to the Space:")
    print(f"     git remote add hf https://huggingface.co/spaces/{space_id}")
    print("     git push hf master")
    print(f"2. Watch the build:  https://huggingface.co/spaces/{space_id}")
    print(f"3. Live app:         https://{args.user}-{args.space_repo}.hf.space")


if __name__ == "__main__":
    main()