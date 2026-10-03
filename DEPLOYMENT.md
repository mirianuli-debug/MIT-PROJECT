# Deployment Guide

Two repos, two platforms:

| What | Where | Contents |
|------|-------|----------|
| Source code | `github.com/mirianuli-debug/MIT-PROJECT` | all code, notebooks, docs. **No model weights.** |
| Model weights | `huggingface.co/<user>/genaimitproject` | `config.json`, `model.safetensors` (~255 MB), tokenizer, model card |
| Live app | `huggingface.co/spaces/<user>/genaimitproject-demo` | Streamlit UI, CPU basic hardware |

The weights are ~255 MB, far beyond git's limits, so they live only on the HuggingFace Hub. The Space downloads them at runtime using the `HF_MODEL_ID` variable declared in the front-matter of `README.md`.

---

## Why the Space repo is named `genaimitproject-demo`

HuggingFace namespaces are shared across repo types, so `<user>/genaimitproject` can only exist once — as *either* a model *or* a Space. The model repo takes the plain name and the app gets the `-demo` suffix.

---

## One-time setup

### 1. Create a Hugging Face token

1. Go to <https://huggingface.co/settings/tokens>
2. Click **+ Create new token**
3. Choose the **Write** role (needed to create repos and upload files)
4. Copy it — you will only see it once

### 2. Install the Hub library

```powershell
py -m pip install huggingface_hub
```

### 3. Run the deployment script

```powershell
$env:HF_TOKEN = "hf_xxxxxxxxxxxxxxxxxxxx"
py deployment/deploy_hf.py --user <your-hf-username>
```

The script:
- verifies `models/phishing_model/` and `models/tokenizer/` are complete
- creates the model repo and uploads the weights, tokenizer and model card
- creates the Space repo (Streamlit SDK)

### 4. Push the app code to the Space

```powershell
git remote add hf https://huggingface.co/spaces/<your-hf-username>/genaimitproject-demo
git push hf master
```

### 5. Confirm the variable

The Space reads `HF_MODEL_ID` from the `variables:` block in `README.md`. Verify it
names your model repo, then check the build log:

- <https://huggingface.co/spaces/<your-hf-username>/genaimitproject-demo>
- Live app: <https://<your-hf-username>--genaimitproject-demo.hf.space>

---

## Updating the model later

Upload new weights to the same model repo; the Space picks them up on restart.

```powershell
py deployment/deploy_hf.py --user <your-hf-username> --skip-model
```

or upload just the weights by hand:

```powershell
hf upload <your-hf-username>/genaimitproject models/phishing_model/config.json config.json
hf upload <your-hf-username>/genaimitproject models/phishing_model/model.safetensors model.safetensors
hf upload <your-hf-username>/genaimitproject models/tokenizer/tokenizer.json tokenizer.json
hf upload <your-hf-username>/genaimitproject models/tokenizer/tokenizer_config.json tokenizer_config.json
```

Then restart the Space from its **Settings → Restart** button.

---

## Updating the app code later

```powershell
git push hf master
```

---

## Running locally instead

No HuggingFace needed. Train the model so that `models/phishing_model/config.json` exists,
then:

```powershell
streamlit run streamlit_app/app.py
```

The loader prefers local weights and falls back to the Hub only when they are absent:

1. `models/phishing_model/config.json` present → use local files
2. else `HF_MODEL_ID` set → download from the Hub and cache
3. else → keyword fallback, clearly labelled in the UI

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