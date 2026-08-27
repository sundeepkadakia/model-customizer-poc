from __future__ import annotations

import argparse
import json

from peft import PeftModel

from runtime import generate_text, load_base_model


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--adapter", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--max-new-tokens", type=int, default=50)
    args = p.parse_args()

    base, tokenizer, _ = load_base_model(args.model)
    messages = [{"role": "user", "content": args.prompt}]
    base_text = generate_text(base, tokenizer, messages, args.max_new_tokens)

    tuned = PeftModel.from_pretrained(base, args.adapter)
    tuned_text = generate_text(tuned, tokenizer, messages, args.max_new_tokens)

    print(json.dumps({"base": base_text, "tuned": tuned_text}, ensure_ascii=False))


if __name__ == "__main__":
    main()
