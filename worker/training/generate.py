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
    p.add_argument("--max-new-tokens", type=int, default=80)
    args = p.parse_args()

    base, tokenizer, device = load_base_model(args.model)
    tuned = PeftModel.from_pretrained(base, args.adapter)
    messages = [{"role": "user", "content": args.prompt}]
    response = generate_text(tuned, tokenizer, messages, args.max_new_tokens)
    print(json.dumps({"response": response, "model": args.model, "adapter": args.adapter, "device": device}, ensure_ascii=False))


if __name__ == "__main__":
    main()
