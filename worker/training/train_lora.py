from __future__ import annotations

import torch
import argparse

from datasets import load_dataset
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer

from runtime import load_base_model, runtime_device


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--rank", type=int, default=4)
    p.add_argument("--max-length", type=int, default=128)
    args = p.parse_args()

    ds = load_dataset("json", data_files=args.dataset, split="train")
    model, tokenizer, device = load_base_model(args.model)
    model.config.use_cache = False

    device, dtype = runtime_device()

    use_bf16 = device == "cuda" and dtype == torch.bfloat16
    use_fp16 = device == "cuda" and dtype == torch.float16

    # Keep the local smoke-test adapter intentionally small. Cloud training can target more modules later.
    peft_config = LoraConfig(
        r=args.rank,
        lora_alpha=args.rank * 2,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj"],
    )

    config = SFTConfig(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=1,
        gradient_checkpointing=True,
        logging_steps=1,
        save_strategy="no",
        report_to="none",
        max_length=args.max_length,
        bf16=use_bf16,
        fp16=use_fp16,
    )

    trainer = SFTTrainer(
        model=model,
        args=config,
        train_dataset=ds,
        peft_config=peft_config,
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    print(f"Saved adapter to {args.output} on {device}")


if __name__ == "__main__":
    main()
