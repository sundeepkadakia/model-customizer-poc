from __future__ import annotations

import argparse
import json
import math

import torch
from datasets import load_dataset
from peft import PeftModel

from runtime import generate_text, load_base_model


def prompt_and_reference(messages: list[dict]) -> tuple[list[dict], str]:
    assistant_indexes = [i for i, m in enumerate(messages) if m.get("role") == "assistant"]
    if not assistant_indexes:
        raise ValueError("Evaluation example has no assistant response")
    last = assistant_indexes[-1]
    return messages[:last], messages[last]["content"]


def completion_loss(model, tokenizer, prompt_messages: list[dict], reference: str) -> float:
    full_messages = prompt_messages + [{"role": "assistant", "content": reference}]
    prompt_text = tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    full_text = tokenizer.apply_chat_template(full_messages, tokenize=False, add_generation_prompt=False, enable_thinking=False)

    prompt_ids = tokenizer(prompt_text, return_tensors="pt", add_special_tokens=False)["input_ids"]
    encoded = tokenizer(full_text, return_tensors="pt", add_special_tokens=False).to(model.device)
    labels = encoded["input_ids"].clone()
    prompt_len = min(prompt_ids.shape[1], labels.shape[1])
    labels[:, :prompt_len] = -100

    model.config.use_cache = False
    with torch.no_grad():
        output = model(**encoded, labels=labels)
    return float(output.loss.detach().cpu())


def token_f1(reference: str, prediction: str) -> float:
    ref = reference.lower().split()
    pred = prediction.lower().split()
    if not ref or not pred:
        return 0.0
    ref_counts = {}
    for token in ref:
        ref_counts[token] = ref_counts.get(token, 0) + 1
    overlap = 0
    for token in pred:
        if ref_counts.get(token, 0) > 0:
            overlap += 1
            ref_counts[token] -= 1
    precision = overlap / len(pred)
    recall = overlap / len(ref)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--adapter", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--max-new-tokens", type=int, default=50)
    args = p.parse_args()

    ds = load_dataset("json", data_files=args.dataset, split="train")
    base, tokenizer, device = load_base_model(args.model)

    prepared = []
    for row in ds:
        prompt_messages, reference = prompt_and_reference(row["messages"])
        base_loss = completion_loss(base, tokenizer, prompt_messages, reference)
        base_generation = generate_text(base, tokenizer, prompt_messages, args.max_new_tokens)
        prepared.append({
            "prompt_messages": prompt_messages,
            "reference": reference,
            "base_loss": base_loss,
            "base_generation": base_generation,
            "base_f1": token_f1(reference, base_generation),
        })

    tuned = PeftModel.from_pretrained(base, args.adapter)
    examples = []
    tuned_losses = []
    base_losses = []
    base_f1s = []
    tuned_f1s = []

    for item in prepared:
        tuned_loss = completion_loss(tuned, tokenizer, item["prompt_messages"], item["reference"])
        tuned_generation = generate_text(tuned, tokenizer, item["prompt_messages"], args.max_new_tokens)
        tuned_f1 = token_f1(item["reference"], tuned_generation)

        base_losses.append(item["base_loss"])
        tuned_losses.append(tuned_loss)
        base_f1s.append(item["base_f1"])
        tuned_f1s.append(tuned_f1)
        examples.append({
            "prompt": item["prompt_messages"],
            "reference": item["reference"],
            "base": item["base_generation"],
            "tuned": tuned_generation,
            "base_reference_loss": round(item["base_loss"], 4),
            "tuned_reference_loss": round(tuned_loss, 4),
            "base_token_f1": round(item["base_f1"], 4),
            "tuned_token_f1": round(tuned_f1, 4),
        })

    avg_base = sum(base_losses) / len(base_losses)
    avg_tuned = sum(tuned_losses) / len(tuned_losses)
    improvement = ((avg_base - avg_tuned) / avg_base * 100) if avg_base else 0.0
    avg_base_f1 = sum(base_f1s) / len(base_f1s)
    avg_tuned_f1 = sum(tuned_f1s) / len(tuned_f1s)

    result = {
        "examples": len(examples),
        "device": device,
        "reference_fit": {
            "base_loss": round(avg_base, 4),
            "tuned_loss": round(avg_tuned, 4),
            "improvement_pct": round(improvement, 2),
            "base_perplexity": round(math.exp(min(avg_base, 20)), 2),
            "tuned_perplexity": round(math.exp(min(avg_tuned, 20)), 2),
        },
        "generated_overlap": {
            "base_token_f1": round(avg_base_f1, 4),
            "tuned_token_f1": round(avg_tuned_f1, 4),
            "delta": round(avg_tuned_f1 - avg_base_f1, 4),
        },
        "note": "Reference loss is the primary local MVP metric. Generated token overlap is only a rough secondary signal; domain-specific judge/rubric scoring should be added for production.",
        "samples": examples[:5],
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
