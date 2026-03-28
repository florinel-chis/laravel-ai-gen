"""
spec_compiler.py — Deterministic validation + normalization layer for BuildSpec JSON.

Runs before every generation call to catch spec design errors early.

Usage:
    from spec_compiler import compile_spec, SpecCompileError

    spec = compile_spec(raw_spec, migrations_dir="/path/to/migrations")
    # raises SpecCompileError on invalid spec
    # returns normalized spec with defaults filled in

CLI:
    python3 spec_compiler.py spec.json [--migrations-dir path/to/migrations]
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional


# ─── Exception ───────────────────────────────────────────────────────────────

class SpecCompileError(Exception):
    """Raised when spec validation or normalization fails."""
    pass


# ─── Migration helpers ────────────────────────────────────────────────────────

# Tokens that indicate a conditional rule — not valid Laravel validation rules
_CONDITIONAL_TOKENS = {
    "required_on_post",
    "required_on_put",
    "required_on_create",
    "required_on_update",
    "required_on_store",
    "required_on_patch",
    "sometimes_on_post",
    "sometimes_on_put",
    "after_now_on_post",
    "after_now_on_put",
    "nullable_on_put",
    "nullable_on_update",
}


def _extract_migration_columns(migration_path: str) -> set:
    """
    Parse a Laravel migration file and return the set of column names defined in it.
    Handles $table->string('col'), $table->integer('col'), etc.
    Does NOT handle complex expressions or raw SQL.
    """
    content = Path(migration_path).read_text()
    # Match $table->type('column_name', ...) patterns
    pattern = re.compile(r'\$table->\w+\(\s*[\'"]([a-zA-Z_][a-zA-Z0-9_]*)[\'"]')
    columns = set(pattern.findall(content))
    # Always present implicit columns
    columns.update({"id", "created_at", "updated_at"})
    # Check for softDeletes
    if re.search(r'\$table->softDeletes\(\)', content):
        columns.add("deleted_at")
    return columns


def _find_migration(table_name: str, migrations_dir: str) -> Optional[str]:
    """
    Find the migration file for a given table name.
    Looks for files matching *_create_{table_name}_table.php or
    *_{table_name}.php in the migrations directory.
    """
    migrations_path = Path(migrations_dir)
    if not migrations_path.exists():
        return None

    # Try exact create pattern first
    for pattern in [
        f"*_create_{table_name}_table.php",
        f"*_{table_name}_table.php",
        f"*_{table_name}.php",
    ]:
        matches = sorted(migrations_path.glob(pattern))
        if matches:
            return str(matches[-1])  # most recent

    return None


def _table_from_class(class_name: str) -> str:
    """Convert a class name to a snake_case plural table name. e.g. BookAuthor -> book_authors"""
    # Insert underscore before uppercase letters (after first)
    s = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
    # Naive pluralization
    if s.endswith('y'):
        return s[:-1] + 'ies'
    elif s.endswith(('s', 'sh', 'ch', 'x', 'z')):
        return s + 'es'
    else:
        return s + 's'


# ─── Infer file path ──────────────────────────────────────────────────────────

_ARTIFACT_PATHS = {
    "model":        "app/Models/{class}.php",
    "migration":    "database/migrations/{timestamp}_create_{table}_table.php",
    "controller":   "app/Http/Controllers/Api/{class}Controller.php",
    "form_request": "app/Http/Requests/Store{class}Request.php",
    "resource":     "app/Http/Resources/{class}Resource.php",
    "pest_test":    "tests/Feature/{class}Test.php",
    "factory":      "database/factories/{class}Factory.php",
    "seeder":       "database/seeders/{class}Seeder.php",
    "policy":       "app/Policies/{class}Policy.php",
}

_ARTIFACT_NAMESPACES = {
    "model":        "App\\Models",
    "controller":   "App\\Http\\Controllers\\Api",
    "form_request": "App\\Http\\Requests",
    "resource":     "App\\Http\\Resources",
    "factory":      "Database\\Factories",
    "seeder":       "Database\\Seeders",
    "policy":       "App\\Policies",
}


def _infer_file_path(spec: dict) -> str:
    artifact = spec["artifact"]
    class_name = spec.get("class", "")
    table = spec.get("table", _table_from_class(class_name))

    template = _ARTIFACT_PATHS.get(artifact)
    if not template:
        raise SpecCompileError(f"Unknown artifact type: {artifact!r}")

    path = template.replace("{class}", class_name).replace("{table}", table)
    # migration timestamp: use placeholder if not set
    path = path.replace("{timestamp}", spec.get("timestamp", "YYYY_MM_DD_HHMMSS"))
    return path


def _infer_namespace(spec: dict) -> str:
    artifact = spec["artifact"]
    return _ARTIFACT_NAMESPACES.get(artifact, "")


# ─── Rule validation ──────────────────────────────────────────────────────────

def _validate_rules(spec: dict) -> None:
    """
    Check rules[] for literal conditional tokens and raise SpecCompileError.
    Callers should use conditional_rules{} instead.
    """
    rules = spec.get("rules", {})
    if not isinstance(rules, dict):
        raise SpecCompileError("'rules' must be a dict mapping field names to rule arrays")

    for field, field_rules in rules.items():
        if not isinstance(field_rules, list):
            raise SpecCompileError(f"rules[{field!r}] must be a list, got {type(field_rules).__name__}")
        for rule in field_rules:
            if not isinstance(rule, str):
                raise SpecCompileError(f"rules[{field!r}] contains non-string rule: {rule!r}")
            # Check for known conditional tokens
            if rule in _CONDITIONAL_TOKENS:
                raise SpecCompileError(
                    f"rules[{field!r}] contains conditional token {rule!r}. "
                    f"Use 'conditional_rules' dict instead. "
                    f"Example: {{\"conditional_rules\": {{{field!r}: {{\"POST\": [\"required\"], \"PUT\": [\"sometimes\"]}}}}}}"
                )
            # Check for snake_case tokens that look like conditional patterns
            if re.match(r'^(required|sometimes|nullable)_(on|for)_(post|put|patch|get|delete|create|update|store)$', rule, re.I):
                raise SpecCompileError(
                    f"rules[{field!r}] contains what looks like a conditional token {rule!r}. "
                    f"Use 'conditional_rules' dict instead."
                )


def _validate_conditional_rules(spec: dict) -> None:
    """Validate the conditional_rules structure."""
    cond = spec.get("conditional_rules", {})
    if not isinstance(cond, dict):
        raise SpecCompileError("'conditional_rules' must be a dict")

    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
    for field, method_map in cond.items():
        if not isinstance(method_map, dict):
            raise SpecCompileError(
                f"conditional_rules[{field!r}] must be a dict of HTTP method → rules, "
                f"got {type(method_map).__name__}"
            )
        for method, method_rules in method_map.items():
            if method.upper() not in valid_methods:
                raise SpecCompileError(
                    f"conditional_rules[{field!r}] has unknown HTTP method {method!r}. "
                    f"Valid: {sorted(valid_methods)}"
                )
            if not isinstance(method_rules, list):
                raise SpecCompileError(
                    f"conditional_rules[{field!r}][{method!r}] must be a list of rule strings"
                )
            for rule in method_rules:
                if not isinstance(rule, str):
                    raise SpecCompileError(
                        f"conditional_rules[{field!r}][{method!r}] contains non-string: {rule!r}"
                    )


# ─── Schema validation ────────────────────────────────────────────────────────

def _validate_schema(spec: dict, migrations_dir: Optional[str]) -> None:
    """
    Validate model fillable/casts fields against actual migration columns.
    Only runs when migrations_dir is provided.
    """
    if not migrations_dir:
        return
    if spec.get("artifact") != "model":
        return

    class_name = spec.get("class", "")
    table = spec.get("table", _table_from_class(class_name))
    migration_path = _find_migration(table, migrations_dir)

    if not migration_path:
        # No migration found — skip validation (table may be created elsewhere)
        return

    db_columns = _extract_migration_columns(migration_path)
    if not db_columns:
        return

    fillable = spec.get("fillable", [])
    casts = spec.get("casts", {})

    issues = []
    for field in fillable:
        if field not in db_columns:
            # Suggest close matches
            close = [c for c in db_columns if c in field or field in c or
                     _edit_distance(field, c) <= 2]
            hint = f" (close matches: {close})" if close else ""
            issues.append(f"fillable field {field!r} not in migration columns{hint}")

    for field in casts:
        if field not in db_columns and field not in ("id", "created_at", "updated_at", "deleted_at"):
            issues.append(f"casts field {field!r} not in migration columns")

    if issues:
        raise SpecCompileError(
            f"Schema mismatch for {class_name} (table: {table}, migration: {migration_path}):\n"
            + "\n".join(f"  - {i}" for i in issues)
            + f"\n\nMigration columns: {sorted(db_columns)}"
        )


def _edit_distance(a: str, b: str) -> int:
    """Simple edit distance for close-match detection."""
    if len(a) > len(b):
        a, b = b, a
    if len(b) - len(a) > 3:
        return 99
    row = list(range(len(a) + 1))
    for c in b:
        new_row = [row[0] + 1]
        for j, d in enumerate(a):
            new_row.append(min(row[j + 1] + 1, new_row[-1] + 1, row[j] + (c != d)))
        row = new_row
    return row[-1]


# ─── Defaults ─────────────────────────────────────────────────────────────────

_MODEL_DEFAULTS = {
    "has_factory": True,
    "soft_deletes": False,
    "relationships": [],
    "scopes": [],
    "fillable": [],
    "casts": {},
}

_CONTROLLER_DEFAULTS = {
    "validation_mode": "form_request",
    "eager_load": [],
}

_FORM_REQUEST_DEFAULTS = {
    "rules": {},
    "conditional_rules": {},
}

_DEFAULTS_BY_ARTIFACT = {
    "model": _MODEL_DEFAULTS,
    "controller": _CONTROLLER_DEFAULTS,
    "form_request": _FORM_REQUEST_DEFAULTS,
}


def _apply_defaults(spec: dict) -> dict:
    """Fill in missing optional fields with sensible defaults."""
    artifact = spec.get("artifact", "")
    defaults = _DEFAULTS_BY_ARTIFACT.get(artifact, {})
    result = dict(spec)
    for key, default in defaults.items():
        if key not in result:
            result[key] = default if not isinstance(default, (dict, list)) else type(default)(default)
    return result


# ─── Required field validation ────────────────────────────────────────────────

_REQUIRED_BASE = {"artifact", "laravel_version"}
_REQUIRED_BY_ARTIFACT = {
    "model":        {"class"},
    "migration":    {"class"},
    "controller":   {"class"},
    "form_request": {"class"},
    "resource":     {"class"},
    "pest_test":    {"class"},
    "factory":      {"class"},
    "seeder":       {"class"},
    "policy":       {"class"},
}


def _validate_required(spec: dict) -> None:
    missing = _REQUIRED_BASE - set(spec.keys())
    if missing:
        raise SpecCompileError(f"Missing required fields: {sorted(missing)}")

    artifact = spec["artifact"]
    extra_required = _REQUIRED_BY_ARTIFACT.get(artifact, set())
    missing_extra = extra_required - set(spec.keys())
    if missing_extra:
        raise SpecCompileError(f"Missing required fields for {artifact!r}: {sorted(missing_extra)}")

    valid_artifacts = set(_ARTIFACT_PATHS.keys())
    if artifact not in valid_artifacts:
        raise SpecCompileError(
            f"Unknown artifact {artifact!r}. Valid: {sorted(valid_artifacts)}"
        )


# ─── Main compile function ────────────────────────────────────────────────────

def compile_spec(spec: dict, migrations_dir: Optional[str] = None) -> dict:
    """
    Validate and normalize a BuildSpec dict.

    1. Validates required fields are present
    2. Validates schema fields against migration columns (if migrations_dir provided)
    3. Validates rules[] for conditional tokens → raises SpecCompileError
    4. Validates conditional_rules structure
    5. Infers file_path and namespace if not set
    6. Applies defaults (has_factory, relationships, scopes, validation_mode, etc.)

    Returns normalized spec dict.
    Raises SpecCompileError on any violation.
    """
    if not isinstance(spec, dict):
        raise SpecCompileError(f"Spec must be a dict, got {type(spec).__name__}")

    # 1. Required fields
    _validate_required(spec)

    # 2. Schema validation
    _validate_schema(spec, migrations_dir)

    # 3. Rule validation
    _validate_rules(spec)

    # 4. Conditional rule structure
    _validate_conditional_rules(spec)

    # 5. Apply defaults
    spec = _apply_defaults(spec)

    # 6. Infer file_path if missing
    if "file_path" not in spec:
        spec["file_path"] = _infer_file_path(spec)

    # 7. Infer namespace if missing
    if "namespace" not in spec:
        ns = _infer_namespace(spec)
        if ns:
            spec["namespace"] = ns

    # 8. Normalize table name
    if "table" not in spec and "class" in spec:
        spec["table"] = _table_from_class(spec["class"])

    return spec


def compile_spec_list(specs: list, migrations_dir: Optional[str] = None) -> list:
    """Compile a list of specs. Returns all compiled specs or raises on first error."""
    return [compile_spec(s, migrations_dir) for s in specs]


# ─── PHP expansion helpers (used by gen_spec_apps.py) ────────────────────────

def expand_conditional_rules_php(rules: dict, conditional_rules: dict) -> str:
    """
    Given rules{} and conditional_rules{}, return PHP array entries string
    suitable for insertion into a FormRequest rules() method.

    Example output:
        'venue_id' => [$this->isMethod('POST') ? 'required' : 'sometimes', 'integer', 'exists:venues,id'],
        'event_date' => ['required', 'date', ...$this->isMethod('POST') ? ['after:now'] : []],
    """
    lines = []

    # Collect all fields (union of rules keys and conditional_rules keys)
    all_fields = list(rules.keys())
    for f in conditional_rules:
        if f not in all_fields:
            all_fields.append(f)

    for field in all_fields:
        base_rules = list(rules.get(field, []))
        cond = conditional_rules.get(field, {})

        if not cond:
            # Simple rules — no conditionals
            if base_rules:
                rule_strs = ", ".join(f"'{r}'" for r in base_rules)
                lines.append(f"            '{field}' => [{rule_strs}],")
            continue

        # Build conditional PHP expansion
        methods = {m.upper() for m in cond}

        if methods <= {"POST", "PUT", "PATCH"}:
            post_rules = list(cond.get("POST", []))
            put_key = "PUT" if "PUT" in cond else "PATCH" if "PATCH" in cond else None
            put_rules = list(cond.get(put_key, [])) if put_key else []

            # Find rules shared between POST and PUT (position-independent)
            post_set = set(post_rules)
            put_set = set(put_rules)
            shared = post_set & put_set
            post_only = [r for r in post_rules if r not in shared]
            put_only = [r for r in put_rules if r not in shared]
            # Rules that differ between POST and PUT (same position, different value)
            # Pair them up for ternary: first post_only with first put_only, etc.
            ternary_pairs = list(zip(post_only, put_only))
            remaining_post = post_only[len(ternary_pairs):]
            remaining_put = put_only[len(ternary_pairs):]

            parts = [f"'{r}'" for r in base_rules]

            # Ternary pairs: e.g. required vs sometimes
            for p, q in ternary_pairs:
                parts.append(f"$this->isMethod('POST') ? '{p}' : '{q}'")

            # POST-only extras (spread)
            for r in remaining_post:
                parts.append(f"...$this->isMethod('POST') ? ['{r}'] : []")

            # PUT-only extras (spread)
            for r in remaining_put:
                parts.append(f"...$this->isMethod('POST') ? [] : ['{r}']")

            # Shared conditional rules that appear in BOTH — keep as plain rules (preserve POST order)
            for r in post_rules:
                if r in shared:
                    parts.append(f"'{r}'")

            rule_str = ", ".join(parts)
            lines.append(f"            '{field}' => [{rule_str}],")

        else:
            # Fallback: just emit base rules and add a comment
            if base_rules:
                rule_strs = ", ".join(f"'{r}'" for r in base_rules)
                lines.append(f"            '{field}' => [{rule_strs}], // conditional_rules not expanded for methods: {sorted(methods)}")
            else:
                lines.append(f"            '{field}' => [], // conditional_rules not expanded for methods: {sorted(methods)}")

    return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="Validate and normalize a BuildSpec JSON file")
    parser.add_argument("spec_file", help="Path to spec JSON file (single spec or array)")
    parser.add_argument("--migrations-dir", default=None, help="Path to migrations directory for schema validation")
    parser.add_argument("--expand-rules", action="store_true", help="Print PHP conditional rule expansion (form_request only)")
    args = parser.parse_args()

    with open(args.spec_file) as f:
        data = json.load(f)

    specs = data if isinstance(data, list) else [data]

    errors = 0
    for i, raw_spec in enumerate(specs):
        label = f"spec[{i}] ({raw_spec.get('artifact', '?')} {raw_spec.get('class', '?')})"
        try:
            compiled = compile_spec(raw_spec, migrations_dir=args.migrations_dir)
            print(f"[OK] {label}")
            print(f"     file_path: {compiled.get('file_path', '?')}")
            print(f"     namespace: {compiled.get('namespace', '?')}")

            if args.expand_rules and compiled.get("artifact") == "form_request":
                rules = compiled.get("rules", {})
                cond = compiled.get("conditional_rules", {})
                if cond:
                    print("     PHP rules expansion:")
                    php = expand_conditional_rules_php(rules, cond)
                    for line in php.split("\n"):
                        print("     " + line)

        except SpecCompileError as e:
            print(f"[ERROR] {label}:")
            for line in str(e).split("\n"):
                print(f"  {line}")
            errors += 1

    if errors:
        sys.exit(1)
    else:
        print(f"\n{len(specs)} spec(s) compiled successfully.")


if __name__ == "__main__":
    _cli()
