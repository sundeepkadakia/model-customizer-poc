from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def runtime_device() -> tuple[str, torch.dtype]:
    if torch.cuda.is_available():
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        return "cuda", dtype
    if torch.backends.mps.is_available():
        # Intel-era MPS does not reliably support bfloat16.
        return "mps", torch.float32
    return "cpu", torch.float32


def load_base_model(model_name: str):
    device, dtype = runtime_device()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=dtype)
    model.config.use_cache = False
    model = model.to(device)
    return model, tokenizer, device


def format_prompt(tokenizer, messages: list[dict]) -> str:
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False
)

def generate_text(model, tokenizer, messages: list[dict], max_new_tokens: int = 50) -> str:
    text = format_prompt(tokenizer, messages)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    model.config.use_cache = True
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    model.config.use_cache = False
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
