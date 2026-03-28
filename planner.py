#!/usr/bin/env python3
"""
planner.py — Few-shot NL → BuildSpec JSON planner.

Converts a natural-language feature description into a list of BuildSpec JSON objects,
one per artifact (model, migration, controller, resource, form_request, pest_test).

The output is validated by spec_compiler before being passed to the generator.

Usage:
    python3 planner.py "Create a REST API for blog posts with categories and tags"
    python3 planner.py --interactive
    python3 planner.py --input feature.txt --output specs.json
"""

import json
import re
import sys
import argparse
from mlx_lm import load, generate

# ── Model (base or lightly fine-tuned — planner uses few-shot, not LoRA) ──────
BASE_MODEL = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
# Use adapters_spec_v3 as the base — it already understands BuildSpec JSON format
ADAPTER = "adapters_spec_v3"

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM = """You are a Laravel 13.x BuildSpec designer.
Given a feature description, output a JSON array of BuildSpec objects — one per artifact.

Rules:
- Output ONLY valid JSON. No markdown fences. No explanation.
- Include ALL artifacts needed: for each entity, generate: model, migration, controller, resource, form_request, pest_test.
- artifact=model: has_factory always true. soft_deletes: true for entities that get deleted. Only include relationships explicitly stated.
- artifact=controller: eager_load only relations the client needs. Use form_request (not inline) for controllers with validation.
- artifact=form_request: required fields on POST, sometimes on PUT via conditional_rules.
- artifact=pest_test: cover index, store, show, update, destroy. Test required field validation.
- Foreign keys: snake_case singular + _id (author → author_id). Table names: snake_case plural.
- Migrations: list in FK dependency order (parent tables before child tables).
- Do not invent fields not mentioned. Use reasonable defaults for obvious fields (id, timestamps).

BuildSpec field reference:
  model:        {artifact, laravel_version, class, namespace, table, has_factory, soft_deletes, fillable[], casts{}, relationships[], scopes[]}
  migration:    {artifact, laravel_version, class, table, columns[{name,type,nullable,default,foreign_key}]}
  controller:   {artifact, laravel_version, class, namespace, model, resource, form_request, validation_mode, eager_load[], paginate, filters[]}
  form_request: {artifact, laravel_version, class, namespace, rules{}, conditional_rules{}}
  resource:     {artifact, laravel_version, class, namespace, fields[], loaded_relations[{key,resource,type}]}
  pest_test:    {artifact, laravel_version, class, namespace, model, endpoints[], required_on_create[]}"""

# ── Few-shot examples ─────────────────────────────────────────────────────────

FEW_SHOT = [
    # ── Example 1: Single model, no relationships ─────────────────────────────
    {
        "prompt": "Create a REST API for managing subscribers. A subscriber has an email, name, status (active/unsubscribed), and subscribed_at date.",
        "spec": [
            {
                "laravel_version": "13.x",
                "artifact": "migration",
                "class": "CreateSubscribersTable",
                "table": "subscribers",
                "columns": [
                    {"name": "email",         "type": "string",    "nullable": False, "unique": True},
                    {"name": "name",          "type": "string",    "nullable": False},
                    {"name": "status",        "type": "string",    "nullable": False, "default": "active"},
                    {"name": "subscribed_at", "type": "timestamp", "nullable": True},
                ]
            },
            {
                "laravel_version": "13.x",
                "artifact": "model",
                "class": "Subscriber",
                "namespace": "App\\Models",
                "table": "subscribers",
                "has_factory": True,
                "soft_deletes": False,
                "fillable": ["email", "name", "status", "subscribed_at"],
                "casts": {"subscribed_at": "datetime"},
                "relationships": [],
                "scopes": [
                    {"name": "active",       "column": "status", "value": "active"},
                    {"name": "unsubscribed", "column": "status", "value": "unsubscribed"},
                ]
            },
            {
                "laravel_version": "13.x",
                "artifact": "resource",
                "class": "SubscriberResource",
                "namespace": "App\\Http\\Resources",
                "fields": [
                    {"key": "id",            "source": "id"},
                    {"key": "email",         "source": "email"},
                    {"key": "name",          "source": "name"},
                    {"key": "status",        "source": "status"},
                    {"key": "subscribed_at", "source": "subscribed_at"},
                    {"key": "created_at",    "source": "created_at"},
                ],
                "loaded_relations": []
            },
            {
                "laravel_version": "13.x",
                "artifact": "form_request",
                "class": "StoreSubscriberRequest",
                "namespace": "App\\Http\\Requests",
                "rules": {
                    "email":         ["required", "email", "max:255", "unique:subscribers,email"],
                    "name":          ["required", "string", "max:255"],
                    "status":        ["nullable", "string", "in:active,unsubscribed"],
                    "subscribed_at": ["nullable", "date"],
                },
                "conditional_rules": {}
            },
            {
                "laravel_version": "13.x",
                "artifact": "controller",
                "class": "SubscriberController",
                "namespace": "App\\Http\\Controllers\\Api",
                "model": "Subscriber",
                "resource": "SubscriberResource",
                "form_request": "StoreSubscriberRequest",
                "validation_mode": "form_request",
                "eager_load": [],
                "paginate": 15,
                "filters": ["status"],
            },
            {
                "laravel_version": "13.x",
                "artifact": "pest_test",
                "class": "Subscriber",
                "namespace": "Tests\\Feature",
                "model": "App\\Models\\Subscriber",
                "endpoints": [
                    {"method": "GET",    "path": "/api/subscribers",      "action": "index"},
                    {"method": "POST",   "path": "/api/subscribers",      "action": "store"},
                    {"method": "GET",    "path": "/api/subscribers/{id}", "action": "show"},
                    {"method": "PUT",    "path": "/api/subscribers/{id}", "action": "update"},
                    {"method": "DELETE", "path": "/api/subscribers/{id}", "action": "destroy"},
                ],
                "required_on_create": ["email", "name"],
            },
        ]
    },

    # ── Example 2: One-to-many relationship ───────────────────────────────────
    {
        "prompt": "Create a REST API for a book library. Authors have many books. A book has a title, ISBN, year (integer), status (draft/published/archived), and belongs to an author.",
        "spec": [
            {
                "laravel_version": "13.x",
                "artifact": "migration",
                "class": "CreateAuthorsTable",
                "table": "authors",
                "columns": [
                    {"name": "name",        "type": "string",  "nullable": False},
                    {"name": "bio",         "type": "text",    "nullable": True},
                    {"name": "nationality", "type": "string",  "nullable": True},
                ]
            },
            {
                "laravel_version": "13.x",
                "artifact": "migration",
                "class": "CreateBooksTable",
                "table": "books",
                "columns": [
                    {"name": "title",     "type": "string",  "nullable": False},
                    {"name": "isbn",      "type": "string",  "nullable": False, "unique": True},
                    {"name": "year",      "type": "integer", "nullable": False},
                    {"name": "status",    "type": "string",  "nullable": False, "default": "draft"},
                    {"name": "author_id", "type": "foreignId", "nullable": False, "foreign_key": "authors.id"},
                ]
            },
            {
                "laravel_version": "13.x",
                "artifact": "model",
                "class": "Author",
                "namespace": "App\\Models",
                "table": "authors",
                "has_factory": True,
                "soft_deletes": False,
                "fillable": ["name", "bio", "nationality"],
                "casts": {},
                "relationships": [
                    {"type": "HasMany", "model": "Book", "method": "books"}
                ],
                "scopes": []
            },
            {
                "laravel_version": "13.x",
                "artifact": "model",
                "class": "Book",
                "namespace": "App\\Models",
                "table": "books",
                "has_factory": True,
                "soft_deletes": True,
                "fillable": ["title", "isbn", "year", "status", "author_id"],
                "casts": {"year": "integer"},
                "relationships": [
                    {"type": "BelongsTo", "model": "Author", "method": "author"}
                ],
                "scopes": []
            },
            {
                "laravel_version": "13.x",
                "artifact": "resource",
                "class": "AuthorResource",
                "namespace": "App\\Http\\Resources",
                "fields": [
                    {"key": "id",          "source": "id"},
                    {"key": "name",        "source": "name"},
                    {"key": "bio",         "source": "bio",         "modifier": "whenNotNull"},
                    {"key": "nationality", "source": "nationality", "modifier": "whenNotNull"},
                    {"key": "books_count", "modifier": "whenCounted"},
                    {"key": "created_at",  "source": "created_at"},
                ],
                "loaded_relations": [
                    {"key": "books", "resource": "BookResource", "type": "collection"}
                ]
            },
            {
                "laravel_version": "13.x",
                "artifact": "resource",
                "class": "BookResource",
                "namespace": "App\\Http\\Resources",
                "fields": [
                    {"key": "id",         "source": "id"},
                    {"key": "title",      "source": "title"},
                    {"key": "isbn",       "source": "isbn"},
                    {"key": "year",       "source": "year"},
                    {"key": "status",     "source": "status"},
                    {"key": "created_at", "source": "created_at"},
                ],
                "loaded_relations": [
                    {"key": "author", "resource": "AuthorResource", "type": "make"}
                ]
            },
            {
                "laravel_version": "13.x",
                "artifact": "form_request",
                "class": "StoreBookRequest",
                "namespace": "App\\Http\\Requests",
                "rules": {
                    "title":     ["required", "string", "max:255"],
                    "isbn":      ["required", "string", "max:20", "unique:books,isbn"],
                    "year":      ["required", "integer", "min:1000", "max:2100"],
                    "status":    ["nullable", "string", "in:draft,published,archived"],
                    "author_id": ["required", "integer", "exists:authors,id"],
                },
                "conditional_rules": {}
            },
            {
                "laravel_version": "13.x",
                "artifact": "controller",
                "class": "BookController",
                "namespace": "App\\Http\\Controllers\\Api",
                "model": "Book",
                "resource": "BookResource",
                "form_request": "StoreBookRequest",
                "validation_mode": "form_request",
                "eager_load": ["author"],
                "paginate": 15,
                "filters": ["status"],
            },
            {
                "laravel_version": "13.x",
                "artifact": "pest_test",
                "class": "Book",
                "namespace": "Tests\\Feature",
                "model": "App\\Models\\Book",
                "endpoints": [
                    {"method": "GET",    "path": "/api/books",      "action": "index"},
                    {"method": "POST",   "path": "/api/books",      "action": "store"},
                    {"method": "GET",    "path": "/api/books/{id}", "action": "show"},
                    {"method": "PUT",    "path": "/api/books/{id}", "action": "update"},
                    {"method": "DELETE", "path": "/api/books/{id}", "action": "destroy"},
                ],
                "required_on_create": ["title", "isbn", "year", "author_id"],
            },
        ]
    },
]


def build_few_shot_messages(description: str) -> list:
    """Build the messages list with few-shot examples + new description."""
    messages = [{"role": "system", "content": SYSTEM}]
    for ex in FEW_SHOT:
        messages.append({"role": "user",      "content": ex["prompt"]})
        messages.append({"role": "assistant", "content": json.dumps(ex["spec"], indent=2)})
    messages.append({"role": "user", "content": description})
    return messages


def extract_json(text: str):
    """Extract first JSON array from model output."""
    # Strip any leading/trailing whitespace
    text = text.strip()

    # Try direct parse first
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try extracting from markdown fence
    fence = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    # Find first [ ... ] block by bracket matching
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


_model = None
_tokenizer = None


def load_model():
    global _model, _tokenizer
    if _model is None:
        print(f"Loading model ({ADAPTER})...", file=sys.stderr)
        _model, _tokenizer = load(BASE_MODEL, adapter_path=ADAPTER)
        print("Model loaded.", file=sys.stderr)
    return _model, _tokenizer


def _recover_partial_json_array(text: str) -> list:
    """
    Try to recover complete JSON objects from a truncated array.
    Finds all complete {...} objects at depth=1 within the array.
    """
    objects = []
    depth = 0
    start = None
    i = 0
    in_string = False
    escape = False

    # Skip leading "[" if present
    if text.strip().startswith("["):
        text = text.strip()[1:]

    while i < len(text):
        ch = text[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == '\\' and in_string:
            escape = True
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        obj = json.loads(text[start:i + 1])
                        objects.append(obj)
                    except json.JSONDecodeError:
                        pass
                    start = None
        i += 1

    return objects


def plan(description: str, max_tokens: int = 6000) -> list:
    """
    Convert a natural-language feature description to a list of BuildSpec dicts.
    Returns the parsed list or raises ValueError on parse failure.
    If output is truncated, recovers all complete spec objects from the partial output.
    """
    model, tokenizer = load_model()
    messages = build_few_shot_messages(description)
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    # Seed with "[" to force JSON array output
    prompt += "["
    result = generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)

    # Strip end-of-turn tokens
    for tok in ["<|im_end|>", "<|endoftext|>", "</s>"]:
        if tok in result:
            result = result[:result.find(tok)]

    specs_json = "[" + result.strip()

    # Try full parse first
    parsed = extract_json(specs_json)
    if parsed is not None:
        return parsed

    # Output was likely truncated — recover complete objects
    recovered = _recover_partial_json_array(specs_json)
    if recovered:
        print(
            f"⚠️  Output truncated: recovered {len(recovered)} complete spec(s) "
            f"from partial JSON (increase max_tokens for full output)",
            file=sys.stderr
        )
        return recovered

    raise ValueError(f"Could not parse JSON from model output:\n{specs_json[:500]}")


def plan_and_validate(description: str, migrations_dir: str = None) -> tuple[list, list]:
    """
    Plan + compile. Returns (compiled_specs, errors).
    Errors is a list of (spec_index, artifact, class, error_message).
    """
    from spec_compiler import compile_spec, SpecCompileError
    raw_specs = plan(description)
    compiled = []
    errors = []
    for i, spec in enumerate(raw_specs):
        try:
            c = compile_spec(spec, migrations_dir=migrations_dir)
            compiled.append(c)
        except SpecCompileError as e:
            errors.append((i, spec.get("artifact", "?"), spec.get("class", "?"), str(e)))
            compiled.append(spec)  # keep raw for inspection
    return compiled, errors


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli():
    parser = argparse.ArgumentParser(description="NL → BuildSpec JSON planner")
    parser.add_argument("description", nargs="?", help="Feature description")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--input",  "-f", help="Read description from file")
    parser.add_argument("--output", "-o", help="Write specs JSON to file")
    parser.add_argument("--validate", action="store_true", help="Run spec_compiler on output")
    parser.add_argument("--migrations-dir", default=None)
    args = parser.parse_args()

    if args.input:
        with open(args.input) as f:
            description = f.read().strip()
    elif args.description:
        description = args.description
    elif args.interactive:
        print("Describe the feature (press Enter twice to submit):")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        description = "\n".join(lines).strip()
    else:
        parser.print_help()
        sys.exit(1)

    print(f"\nPlanning: {description[:100]}...\n", file=sys.stderr)

    if args.validate:
        specs, errors = plan_and_validate(description, migrations_dir=args.migrations_dir)
        if errors:
            print(f"\n⚠️  {len(errors)} spec error(s):", file=sys.stderr)
            for idx, artifact, cls, msg in errors:
                print(f"  spec[{idx}] {artifact} {cls}: {msg}", file=sys.stderr)
        else:
            print(f"✅ All {len(specs)} specs compiled successfully.", file=sys.stderr)
    else:
        specs = plan(description)

    output = json.dumps(specs, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output + "\n")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)

    print(f"\n{len(specs)} spec(s) generated.", file=sys.stderr)


if __name__ == "__main__":
    _cli()
