#!/usr/bin/env python3
"""
pipeline_spec.py — End-to-end spec pipeline: NL → BuildSpec → PHP files.

Stages:
  1. Planner   : NL description → list of BuildSpec dicts (few-shot)
  2. Compiler  : validate + normalize each spec (spec_compiler.py)
  3. Generator : each spec → PHP file (adapters_spec_v3)
  4. Writer    : save PHP files to output directory

Usage:
    # Interactive
    python3 pipeline_spec.py

    # One-shot from description
    python3 pipeline_spec.py "Create a REST API for managing blog posts with tags"

    # From file, with output directory
    python3 pipeline_spec.py --input feature.txt --output ./generated/blog

    # Skip planner — use a spec file directly
    python3 pipeline_spec.py --spec specs.json --output ./generated/blog

    # With schema validation against existing migrations
    python3 pipeline_spec.py --input feature.txt --migrations-dir ./database/migrations
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
BASE_MODEL    = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
CODER_ADAPTER = "adapters_spec_v3"

# ── Lazy model loading ─────────────────────────────────────────────────────────
_model = None
_tokenizer = None

def _load_model():
    global _model, _tokenizer
    if _model is None:
        from mlx_lm import load
        print(f"  Loading coder ({CODER_ADAPTER})...", file=sys.stderr)
        _model, _tokenizer = load(BASE_MODEL, adapter_path=CODER_ADAPTER)
        print("  Coder loaded.", file=sys.stderr)
    return _model, _tokenizer


# ── Coder system prompt ────────────────────────────────────────────────────────
CODER_SYSTEM = """You are a Laravel 13.x PHP code generator. Input is a BuildSpec JSON object. Output is the complete PHP file.

Rules:
- Output ONLY the PHP file. No markdown fences. No explanation. No extra comments.
- Implement EXACTLY what the spec says. Do not add fields, relationships, or methods not in the spec.
- artifact=model: ALWAYS add use HasFactory when has_factory=true. ONLY add relationship methods listed in relationships[]. Import every relationship return type (BelongsTo etc).
- artifact=controller: ALWAYS import App\\Http\\Controllers\\Controller and Illuminate\\Http\\Request. destroy() returns response()->noContent(). store() returns response()->json($resource, 201). If validation_mode=inline use $request->validate([...]) in store() and update(). If validation_mode=form_request import and use the FormRequest class.
- artifact=resource: ALWAYS import Illuminate\\Http\\Resources\\Json\\JsonResource. For EVERY entry in loaded_relations[] that has a "resource" key, add `use App\\Http\\Resources\\{ResourceClass};` at the top — even if it is in the same namespace. Never use a Resource class without importing it.
- artifact=form_request: rules() returns exact rules from spec. If conditional_rules present, expand each field using $this->isMethod('POST') ternary or spread. For POST-only rules use spread: `...$this->isMethod('POST') ? ['rule'] : []`. authorize() returns true."""


def _generate_file(spec: dict, max_tokens: int = 1000) -> str:
    from mlx_lm import generate as mlx_generate
    model, tokenizer = _load_model()
    spec_str = json.dumps(spec, indent=2)
    msgs = [
        {"role": "system", "content": CODER_SYSTEM},
        {"role": "user",   "content": spec_str},
    ]
    prompt = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    prompt += "<?php\n"
    result = mlx_generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)
    for tok in ["<|im_end|>", "<|endoftext|>", "</s>"]:
        if tok in result:
            result = result[:result.find(tok)]
    lines = result.split("\n")
    real = [i for i, l in enumerate(lines) if l.strip() and not l.strip().startswith("!")]
    result = "\n".join(lines[:real[-1] + 1]) if real else result
    return "<?php\n" + result.lstrip("<?php\n")


# ── Stage 1: Plan ─────────────────────────────────────────────────────────────

def stage_plan(description: str) -> list:
    """NL → raw BuildSpec list."""
    import planner
    print("\n[1/3] Planning specs...", file=sys.stderr)
    specs = planner.plan(description)
    print(f"      → {len(specs)} spec(s) generated", file=sys.stderr)
    return specs


# ── Stage 2: Compile ──────────────────────────────────────────────────────────

def stage_compile(specs: list, migrations_dir: str = None) -> tuple[list, list]:
    """Validate + normalize specs. Returns (compiled_specs, error_list)."""
    from spec_compiler import compile_spec, SpecCompileError
    print(f"\n[2/3] Compiling {len(specs)} spec(s)...", file=sys.stderr)
    compiled = []
    errors = []
    for i, spec in enumerate(specs):
        artifact = spec.get("artifact", "?")
        cls      = spec.get("class",    "?")
        try:
            c = compile_spec(spec, migrations_dir=migrations_dir)
            compiled.append(c)
            print(f"      ✅ [{artifact}] {cls}", file=sys.stderr)
        except SpecCompileError as e:
            errors.append((i, artifact, cls, str(e)))
            compiled.append(spec)
            print(f"      ❌ [{artifact}] {cls}: {e}", file=sys.stderr)
    return compiled, errors


# ── Stage 3: Generate ─────────────────────────────────────────────────────────

def stage_generate(compiled_specs: list, output_dir: str, errors: list) -> list:
    """Each non-errored spec → PHP file. Returns list of written paths."""
    error_indices = {e[0] for e in errors}
    output_path = Path(output_dir)

    # Collect specs to generate (skip migrations for generation — they're template-based)
    to_generate = [
        (i, spec) for i, spec in enumerate(compiled_specs)
        if i not in error_indices
    ]

    print(f"\n[3/3] Generating {len(to_generate)} file(s) → {output_dir}", file=sys.stderr)

    written = []
    for i, spec in to_generate:
        artifact = spec.get("artifact", "?")
        cls      = spec.get("class",    "?")
        file_path = spec.get("file_path", f"{artifact}/{cls}.php")

        dest = output_path / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.time()
        try:
            code = _generate_file(spec)
            dest.write_text(code)
            elapsed = time.time() - t0
            print(f"      ✅ [{artifact}] {cls} → {file_path}  ({elapsed:.1f}s)", file=sys.stderr)
            written.append(str(dest))
        except Exception as e:
            print(f"      ❌ [{artifact}] {cls}: {e}", file=sys.stderr)

    return written


# ── PHP syntax check ──────────────────────────────────────────────────────────

def syntax_check(paths: list) -> dict:
    """Run php -l on all written files. Returns {path: ok/error}."""
    import subprocess
    results = {}
    for p in paths:
        r = subprocess.run(["php", "-l", p], capture_output=True, text=True)
        ok = r.returncode == 0
        results[p] = ("ok" if ok else r.stderr.strip())
    return results


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    description: str = None,
    spec_file: str = None,
    output_dir: str = "./pipeline_output",
    migrations_dir: str = None,
    skip_plan: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Run the full pipeline.
    Returns summary dict with keys: specs, compile_errors, written, syntax_errors.
    """
    t_start = time.time()

    # ── Stage 1: Plan or load specs ───────────────────────────────────────────
    if spec_file:
        with open(spec_file) as f:
            raw_specs = json.load(f)
        if not isinstance(raw_specs, list):
            raw_specs = [raw_specs]
        print(f"\n[1/3] Loaded {len(raw_specs)} spec(s) from {spec_file}", file=sys.stderr)
    elif description:
        raw_specs = stage_plan(description)
    else:
        raise ValueError("Must provide either description or spec_file")

    # ── Stage 2: Compile ──────────────────────────────────────────────────────
    compiled_specs, compile_errors = stage_compile(raw_specs, migrations_dir=migrations_dir)

    if compile_errors:
        print(f"\n⚠️  {len(compile_errors)} compile error(s) — these specs will be skipped:", file=sys.stderr)
        for idx, artifact, cls, msg in compile_errors:
            print(f"     spec[{idx}] {artifact} {cls}:", file=sys.stderr)
            for line in msg.split("\n"):
                print(f"       {line}", file=sys.stderr)

    # ── Stage 3: Generate ─────────────────────────────────────────────────────
    written = stage_generate(compiled_specs, output_dir, compile_errors)

    # ── Syntax check ─────────────────────────────────────────────────────────
    syntax_results = syntax_check(written)
    syntax_errors = {p: e for p, e in syntax_results.items() if e != "ok"}

    elapsed = time.time() - t_start

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'═'*60}", file=sys.stderr)
    print(f"Pipeline complete in {elapsed:.1f}s", file=sys.stderr)
    print(f"  Specs planned  : {len(raw_specs)}", file=sys.stderr)
    print(f"  Compile errors : {len(compile_errors)}", file=sys.stderr)
    print(f"  Files written  : {len(written)}", file=sys.stderr)
    php_valid = len(written) - len(syntax_errors)
    print(f"  PHP valid      : {php_valid}/{len(written)}", file=sys.stderr)
    if syntax_errors:
        print(f"\n  PHP syntax errors:", file=sys.stderr)
        for p, e in syntax_errors.items():
            print(f"    {p}: {e}", file=sys.stderr)
    print(f"\n  Output: {output_dir}", file=sys.stderr)

    return {
        "specs":          raw_specs,
        "compiled_specs": compiled_specs,
        "compile_errors": compile_errors,
        "written":        written,
        "syntax_errors":  syntax_errors,
        "elapsed":        elapsed,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(
        description="Laravel spec pipeline: NL → BuildSpec → PHP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("description", nargs="?", help="Feature description (NL)")
    parser.add_argument("--input",          "-f", help="Read description from file")
    parser.add_argument("--spec",           "-s", help="Skip planner: use spec JSON file directly")
    parser.add_argument("--output",         "-o", default="./pipeline_output", help="Output directory")
    parser.add_argument("--migrations-dir",       default=None, help="Path to migrations dir for schema validation")
    parser.add_argument("--interactive",    "-i", action="store_true")
    parser.add_argument("--plan-only",            action="store_true", help="Only run planner, print specs JSON")
    args = parser.parse_args()

    # Get description
    if args.input:
        with open(args.input) as f:
            description = f.read().strip()
    elif args.description:
        description = args.description
    elif args.interactive or not args.spec:
        print("Describe the feature to generate (press Enter twice to submit):")
        lines = []
        while True:
            try:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            except EOFError:
                break
        description = "\n".join(lines).strip()
        if not description:
            parser.print_help()
            sys.exit(1)
    else:
        description = None

    # Plan-only mode
    if args.plan_only:
        import planner
        specs = planner.plan(description)
        print(json.dumps(specs, indent=2))
        return

    # Full pipeline
    run_pipeline(
        description=description,
        spec_file=args.spec,
        output_dir=args.output,
        migrations_dir=args.migrations_dir,
    )


if __name__ == "__main__":
    _cli()
