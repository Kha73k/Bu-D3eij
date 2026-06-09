"""Regenerate the Vanguard AI-text-detector model (dev tool, NOT shipped/bundled).

The detector (`desklib/ai-text-detector-v1.01`, a DeBERTa-v3-large fine-tune) has no
official ONNX, and — because Bu D3eij is a personal build — the exported model is neither
bundled in the exe nor hosted online. It lives only in the local cache:
    %USERPROFILE%\\.bud3eij\\models\\vanguard\\{model.onnx, tokenizer.json}
This script rebuilds those files. Run it if the cache is ever lost, or to refresh the model.

Output format is **fp32 (~1.7 GB)** on purpose: fp32 ONNX matches the PyTorch reference
exactly, whereas dynamic **int8** drifts ~+0.15 toward false positives and **fp16 won't
load in onnxruntime** for this graph (Cast/Clip op-type mismatches). So fp32 is the only
format that is both correct and loadable here.

Dev-only deps (NOT in requirements.txt, NOT bundled) — install into a throwaway venv,
never the runtime `.venv`:
    py -3.11 -m venv .venv_export
    .venv_export\\Scripts\\python -m pip install --index-url https://download.pytorch.org/whl/cpu torch
    .venv_export\\Scripts\\python -m pip install transformers sentencepiece onnx onnxruntime tokenizers numpy huggingface_hub safetensors onnxscript

Run from the project root:
    .venv_export\\Scripts\\python tools\\export_vanguard_model.py
"""
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file
from transformers import AutoConfig, AutoModel, AutoTokenizer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # torch prints emoji on Windows
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = "desklib/ai-text-detector-v1.01"
MAXLEN = 768
OUT = Path.home() / ".bud3eij" / "models" / "vanguard"  # the runtime cache location
OUT.mkdir(parents=True, exist_ok=True)

# Parity samples (any text works — we only need ONNX to match PyTorch).
HUMAN = ("I went down to the river last Saturday with my brother and we just sat there for "
         "hours, watching the water and skipping the flat stones we found near the bank.")
AI = ("Artificial intelligence has emerged as a transformative technology reshaping numerous "
      "industries by leveraging advanced algorithms and vast datasets with remarkable efficiency.")


class DesklibAIDetectionModel(nn.Module):
    """deberta-v3-large backbone -> attention-masked mean pooling -> linear -> 1 logit."""

    def __init__(self, config):
        super().__init__()
        self.model = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, 1)

    def forward(self, input_ids, attention_mask):
        last_hidden = self.model(input_ids=input_ids, attention_mask=attention_mask)[0]
        mask = attention_mask.unsqueeze(-1).float()
        pooled = (last_hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        return self.classifier(pooled)  # (B, 1) logit


def main():
    print("== downloading desklib files ==", flush=True)
    config = AutoConfig.from_pretrained(hf_hub_download(REPO, "config.json"))
    model = DesklibAIDetectionModel(config)
    model.load_state_dict(load_file(hf_hub_download(REPO, "model.safetensors")), strict=True)
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(REPO)
    tok_json = hf_hub_download(REPO, "tokenizer.json")

    def tk(text):
        e = tokenizer(text, truncation=True, max_length=MAXLEN, return_tensors="pt")
        return e["input_ids"], e["attention_mask"]

    print("== torch reference ==", flush=True)
    ref = {}
    with torch.no_grad():
        for name, text in (("human", HUMAN), ("ai", AI)):
            ref[name] = torch.sigmoid(model(*tk(text))).item()
            print(f"  {name}: P(AI)={ref[name]:.4f}", flush=True)

    print("== exporting fp32 ONNX ==", flush=True)
    ids, am = tk(AI)
    out_model = OUT / "model.onnx"
    torch.onnx.export(
        model, (ids, am), str(out_model),
        input_names=["input_ids", "attention_mask"], output_names=["logits"],
        dynamic_axes={"input_ids": {0: "b", 1: "t"}, "attention_mask": {0: "b", 1: "t"},
                      "logits": {0: "b"}},
        opset_version=17, do_constant_folding=True, dynamo=False,
    )
    print(f"  wrote {out_model} ({out_model.stat().st_size/1e6:.1f} MB)", flush=True)

    print("== onnxruntime + tokenizers parity ==", flush=True)
    import onnxruntime as ort
    from tokenizers import Tokenizer

    ftok = Tokenizer.from_file(tok_json)
    ftok.enable_truncation(max_length=MAXLEN)
    sess = ort.InferenceSession(str(out_model), providers=["CPUExecutionProvider"])
    names = {i.name for i in sess.get_inputs()}
    worst = 0.0
    for name, text in (("human", HUMAN), ("ai", AI)):
        e = ftok.encode(text)
        feed = {"input_ids": np.array([e.ids], np.int64),
                "attention_mask": np.array([e.attention_mask], np.int64)}
        feed = {k: v for k, v in feed.items() if k in names}
        p = 1.0 / (1.0 + np.exp(-float(sess.run(None, feed)[0].reshape(-1)[0])))
        d = abs(p - ref[name]); worst = max(worst, d)
        print(f"  {name}: P(AI)={p:.4f}  (Δ vs torch={d:.4f})", flush=True)
    import shutil
    shutil.copy(tok_json, OUT / "tokenizer.json")
    assert worst < 1e-3, f"ONNX parity too loose (Δ={worst})"
    print(f"\nDONE -> {OUT}  (parity Δ<{worst:.1e}; tokenizer copied)", flush=True)


if __name__ == "__main__":
    main()
