#!/usr/bin/env python3
"""
Laravel Code Generator CLI
Two-model pipeline: Planner (1.7B) decomposes → Coder (3B) generates → Files written to disk.

Usage:
  python3 laravel-gen.py "add favorites feature with pagination"
  python3 laravel-gen.py "create a blog with categories and tags"
  python3 laravel-gen.py --list   # show what would be generated without writing files
"""
import sys, os, json, re, time
from mlx_lm import load, generate

# ============================================================
# CONFIG
# ============================================================
PLANNER_MODEL = "/Users/fch/qwen/fused_planner_v6"
CODER_MODEL = "/Users/fch/qwen/fused_qwen3b_v5"

PLANNER_SYS = "You are a Laravel architect. Decompose feature requests into specific coding tasks. Think briefly, then output a JSON array of objects. Each object has 'file' (the Laravel project file path) and 'instruction' (what code to write for that file)."
CODER_SYS = "You are a senior Laravel developer. Write clean, production-ready Laravel code."

# Map instruction keywords to file paths
FILE_PATH_RULES = [
    # Migrations
    (r"migration.*create.*?(\w+)\s+table", lambda m: f"database/migrations/{time.strftime('%Y_%m_%d')}_{int(time.time()) % 100000}_create_{m.group(1)}_table.php"),
    (r"migration.*add.*?(\w+).*?(\w+)\s+table", lambda m: f"database/migrations/{time.strftime('%Y_%m_%d')}_{int(time.time()) % 100000}_add_{m.group(1)}_to_{m.group(2)}_table.php"),
    (r"migration", lambda m: f"database/migrations/{time.strftime('%Y_%m_%d')}_{int(time.time()) % 100000}_migration.php"),
    # Models
    (r"model\s+for\s+(\w+)", lambda m: f"app/Models/{m.group(1)}.php"),
    (r"(\w+)\s+model", lambda m: f"app/Models/{m.group(1)}.php"),
    # Controllers
    (r"(\w+Controller)", lambda m: f"app/Http/Controllers/{m.group(1)}.php"),
    (r"controller.*?(\w+)", lambda m: f"app/Http/Controllers/{m.group(1).title()}Controller.php"),
    # Form Requests
    (r"Form\s*Request\s+for\s+(\w+)", lambda m: f"app/Http/Requests/{m.group(1).title()}Request.php"),
    (r"Form\s*Request.*?class\s+(\w+)", lambda m: f"app/Http/Requests/{m.group(1)}.php"),
    (r"(\w+Request)\b", lambda m: f"app/Http/Requests/{m.group(1)}.php"),
    # Middleware
    (r"middleware.*?(\w+)", lambda m: f"app/Http/Middleware/{m.group(1).title()}.php"),
    # API Resources
    (r"API\s*Resource.*?(\w+)", lambda m: f"app/Http/Resources/{m.group(1)}.php"),
    (r"(\w+Resource)", lambda m: f"app/Http/Resources/{m.group(1)}.php"),
    # Routes
    (r"route", lambda m: "routes/api.php"),
    # Blade views
    (r"[Bb]lade.*view", lambda m: "resources/views/component.blade.php"),
    # Jobs
    (r"Job\s+(\w+)", lambda m: f"app/Jobs/{m.group(1)}.php"),
    (r"(\w+Job)", lambda m: f"app/Jobs/{m.group(1)}.php"),
    # Mailable
    (r"[Mm]ailable.*?(\w+)", lambda m: f"app/Mail/{m.group(1)}.php"),
    # Service Provider
    (r"[Ss]ervice\s*[Pp]rovider", lambda m: "app/Providers/AppServiceProvider.php"),
    # Trait
    (r"trait\s+(\w+)", lambda m: f"app/Traits/{m.group(1)}.php"),
    # Scope / general
    (r"scope.*?(\w+)\s+model", lambda m: f"app/Models/{m.group(1)}.php"),
]

def guess_filepath(instruction):
    """Guess the file path from the instruction text."""
    for pattern, path_fn in FILE_PATH_RULES:
        match = re.search(pattern, instruction, re.IGNORECASE)
        if match:
            return path_fn(match)
    return None

def extract_code(raw_output):
    """Extract just the PHP/Blade code from model output."""
    code = raw_output.strip()
    # Remove markdown fences
    if code.startswith("```php"):
        code = code[6:]
    elif code.startswith("```blade"):
        code = code[8:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()

    # Strip prose before <?php (model sometimes explains before coding)
    if "<?php" in code:
        code = "<?php" + code.split("<?php", 1)[1]

    # Strip prose before first "use " or "namespace " if no <?php
    elif code and not code.startswith("use ") and not code.startswith("namespace ") and not code.startswith("@") and not code.startswith("Route::") and not code.startswith("Schema::"):
        for marker in ["use ", "namespace ", "return new class"]:
            if marker in code:
                code = code[code.index(marker):]
                break

    # Detect repetition: if any line appears 3+ times, truncate
    lines = code.split("\n")
    seen = {}
    truncate_at = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if len(stripped) > 10:  # only check meaningful lines
            seen[stripped] = seen.get(stripped, 0) + 1
            if seen[stripped] >= 3 and truncate_at is None:
                truncate_at = i
    if truncate_at is not None:
        # Find the last closing brace before the repetition
        for j in range(truncate_at, -1, -1):
            if lines[j].strip() in ("}", "};"):
                code = "\n".join(lines[:j+1])
                break

    return code.strip()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 laravel-gen.py \"feature description\"")
        print("       python3 laravel-gen.py --list \"feature description\"")
        sys.exit(1)

    list_only = "--list" in sys.argv
    request = " ".join(arg for arg in sys.argv[1:] if arg != "--list")

    if not request:
        print("Error: provide a feature description")
        sys.exit(1)

    output_dir = os.getcwd()

    print(f"\n{'='*60}")
    print(f"  Laravel Code Generator")
    print(f"  Request: {request}")
    print(f"  Output:  {output_dir}")
    print(f"{'='*60}")

    # Load models
    print("\n[1/3] Loading models...")
    t0 = time.time()
    planner, planner_tok = load(PLANNER_MODEL)
    coder, coder_tok = load(CODER_MODEL)
    print(f"  Models loaded in {time.time()-t0:.1f}s")

    # Plan
    print(f"\n[2/3] Planning...")
    msgs = [{"role": "system", "content": PLANNER_SYS}, {"role": "user", "content": request}]
    prompt = planner_tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)

    t0 = time.time()
    plan_raw = generate(planner, planner_tok, prompt=prompt, max_tokens=1500, )
    plan_time = time.time() - t0

    # Extract thinking
    think_match = re.search(r'<think>(.*?)</think>', plan_raw, re.DOTALL)
    thinking = think_match.group(1).strip() if think_match else ""

    # Parse tasks (new format: array of {file, instruction})
    match = re.search(r'\[.*?\]', plan_raw, re.DOTALL)
    tasks = []
    if match:
        try:
            parsed = json.loads(match.group())
            # Handle both old format (strings) and new format (objects)
            for item in parsed:
                if isinstance(item, dict):
                    tasks.append(item)
                elif isinstance(item, str):
                    tasks.append({"file": guess_filepath(item) or "unknown", "instruction": item})
        except json.JSONDecodeError:
            pass

    if not tasks:
        print(f"  Error: planner did not produce valid tasks")
        print(f"  Raw output: {plan_raw[:500]}")
        sys.exit(1)

    # Deduplicate: keep first occurrence of each file path
    seen_files = set()
    deduped = []
    for task in tasks:
        fp = task.get("file", "")
        if fp not in seen_files:
            seen_files.add(fp)
            deduped.append(task)
    if len(deduped) < len(tasks):
        print(f"  (Deduplicated: {len(tasks)} → {len(deduped)} tasks)")
    tasks = deduped

    print(f"  Thinking: {thinking[:120]}")
    print(f"  {len(tasks)} tasks planned in {plan_time:.1f}s:")
    for i, task in enumerate(tasks):
        filepath = task.get("file", "unknown")
        inst = task.get("instruction", "")
        print(f"    {i+1}. {filepath}")
        print(f"       {inst[:70]}...")

    if list_only:
        print("\n  [--list mode, no files written]")
        sys.exit(0)

    # Generate code
    print(f"\n[3/3] Generating code...")
    results = []
    total_code_time = 0

    for i, task in enumerate(tasks):
        filepath = task.get("file", "unknown")
        inst = task.get("instruction", "")
        msgs = [{"role": "system", "content": CODER_SYS}, {"role": "user", "content": inst}]
        prompt = coder_tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)

        # Set max_tokens based on file type
        if "migration" in filepath.lower():
            mtok = 500
        elif "Model" in filepath or "models" in filepath.lower():
            mtok = 600
        else:
            mtok = 900

        t0 = time.time()
        raw_code = generate(coder, coder_tok, prompt=prompt, max_tokens=mtok, )
        ct = time.time() - t0
        total_code_time += ct

        code = extract_code(raw_code)
        results.append({"instruction": inst, "filepath": filepath, "code": code, "time": ct})

        status = "✓" if filepath and filepath != "unknown" else "?"
        print(f"  {status} [{i+1}/{len(tasks)}] {os.path.basename(filepath)} ({len(code)} chars, {ct:.1f}s)")

    # Write files
    print(f"\n  Writing files...")
    written = 0
    for r in results:
        if r["filepath"] and r["code"]:
            full_path = os.path.join(output_dir, r["filepath"])
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # If file exists (like routes/api.php), append instead of overwrite
            if os.path.exists(full_path) and "routes/" in r["filepath"]:
                with open(full_path, "a") as f:
                    f.write("\n\n// Generated by laravel-gen\n")
                    f.write(r["code"])
                print(f"  + Appended to {r['filepath']}")
            else:
                with open(full_path, "w") as f:
                    f.write(r["code"])
                print(f"  + Created {r['filepath']}")
            written += 1
        else:
            print(f"  ? Skipped: {r['instruction'][:60]}... (no file path matched)")

    # Summary
    print(f"\n{'='*60}")
    print(f"  DONE")
    print(f"  Files: {written}/{len(tasks)} written")
    print(f"  Plan:  {plan_time:.1f}s")
    print(f"  Code:  {total_code_time:.1f}s")
    print(f"  Total: {plan_time + total_code_time:.1f}s")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
