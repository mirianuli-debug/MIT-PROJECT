# Deployment Guide

Two repos, two platforms:

| What | Where | Contents |
|------|-------|----------|
| Source code | `github.com/mirianuli-debug/MIT-PROJECT` | all code, notebooks, docs. **No model weights.** |
| Model weights | `huggingface.co/Mirianuli/genaimitproject` | `config.json`, `model.safetensors` (~255 MB), tokenizer, model card |
| Live app | Streamlit Community Cloud | Streamlit UI, downloads weights from the Hub at runtime |

The weights are ~255 MB, far beyond git's limits, so they live only on the HuggingFace Hub. The app downloads them at runtime using the `HF_MODEL_ID` variable declared in the front-matter of `README.md`.

---

## Why the app is not on a HuggingFace Space

HuggingFace now routes Streamlit Spaces through Docker, and the Hub's free tier no longer includes
CPU hardware for dynamic Spaces. Creating one returns:

```
402 Payment Required
Static Spaces are free for everyone, but hosting Gradio and Docker Spaces
on free cpu-basic requires a PRO subscription.
```

Verified on 2026-10-03: `sdk: static` succeeds, `sdk: streamlit` and `sdk: docker` both return 402.
Streamlit Community Cloud is used instead, which is free.

---

## Why the Space-style repo name is not used

HuggingFace namespaces are shared across repo types, so `<user>/genaimitproject` can only exist
once — as *either* a model *or* a Space. Only the model repo exists on the Hub.

---

## Deploy the app to Streamlit Community Cloud

1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. **New app** → pick the repository `mirianuli-debug/MIT-PROJECT`, branch `master`.
3. Open **Advanced settings** and set:
   - **Main file path**: `streamlit_app/app.py`
   - **Python version**: `3.10`
   - **Requirements file**: leave it as `requirements.txt`
4. **Deploy**.

The model id `Mirianuli/genaimitproject` is built into `config/config.py`, so nothing else is
required. To point a fork at a different model repo, add an environment variable
`HF_MODEL_ID=<user>/<repo>` in the same Advanced settings panel; the env var always wins.

The app reports which model it loaded in the sidebar (`Model source: HuggingFace Hub (Mirianuli/genaimitproject)`).

### Why requirements.txt is CPU-pinned

The root `requirements.txt` is what Streamlit Community Cloud installs by default, and it pins
the CPU-only PyTorch wheel:

```
--extra-index-url https://download.pytorch.org/whl/cpu
```

Without that line pip resolves the default PyPI `torch` wheel, which drags in roughly 2.5 GB of
CUDA libraries. The free container does not have the disk for that, and the build dies before
the app ever starts. Training-only packages (`datasets`, `accelerate`, `evaluate`, `seaborn`,
`tqdm`) were moved to `requirements_train.txt` so they are not installed on the host.

**If you hit an install error, read the deployment log.** Streamlit prints the failing package
and the reason before the error page appears.

### Memory note

The free container has roughly 1 GB of RAM, and the model alone is ~255 MB. SHAP attribution is
far more expensive than inference, so `explain(..., use_shap=False)` is wired in as a fallback:
if SHAP runs out of memory the app still returns the prediction and says so, instead of failing.
To reduce memory further, lower `max_evals` and `background_size` in
`streamlit_app/app.py` (`load_explainer`), or convert the weights to float16 and upload them again.

---

## One-time setup (already done)

The HuggingFace model repo is live and public:

```powershell
$env:HF_TOKEN = "<your hf write token>"
py deployment/deploy_hf.py --user Mirianuli
```

This verifies `models/phishing_model/` and `models/tokenizer/` are complete, creates the model
repo and uploads the weights, tokenizer and model card.

---

## Updating the model later

Upload new weights to the same model repo, then restart the app.

```powershell
hf upload Mirianuli/genaimitproject models/phishing_model/model.safetensors model.safetensors
hf upload Mirianuli/genaimitproject models/phishing_model/config.json config.json
hf upload Mirianuli/genaimitproject models/tokenizer/tokenizer.json tokenizer.json
hf upload Mirianuli/genaimitproject models/tokenizer/tokenizer_config.json tokenizer_config.json
```

The deployment host caches the download, so it must be restarted to pick up new weights.

---

## Updating the app code later

Push to GitHub — Streamlit Community Cloud redeploys automatically on every push to the
deployed branch.

```powershell
git push mit master
```

---

## Running locally instead

```powershell
pip install -r requirements.txt   # or requirements_train.txt for training work
streamlit run streamlit_app/app.py
```

The loader prefers local weights and falls back to the Hub only when they are absent:

1. `models/phishing_model/config.json` present → use local files
2. else `HF_MODEL_ID` set (built-in default is `Mirianuli/genaimitproject`) → download from the Hub and cache
3. else → keyword fallback, clearly labelled in the UI

To work fully offline, download the Hub repo once and drop it into `models/`:

```powershell
hf download Mirianuli/genaimitproject --local-dir models/hub_model
```

---

## Interpreting results honestly

The original random-split evaluation reports 1.0000 on every metric. That split places
template-sibling samples in both train and test, so the number overstates real-world
performance. The template-aware group split, which guarantees zero shared template
families between train/validation/test, is included for comparison:

- `experiments/template_aware_split/`
- `notebooks/template_aware_experiment.ipynb`
- `notebooks/training_notebook.ipynb` (runs both splits in one pass and saves both to `results_summary.json`)

Do not present the 1.0000 figure as evidence of production accuracy.