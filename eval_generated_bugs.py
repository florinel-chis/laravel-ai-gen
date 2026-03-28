#!/usr/bin/env python3
"""eval_generated_bugs.py — Analyze generated PHP files for known bug patterns.

Usage: python3 eval_generated_bugs.py <generated_dir>
Reports: PHP validity, optional rule, cross-resource imports, wasRecentlyCreated, etc.
"""

import os, sys, subprocess, re

BUGS = {
    "optional_rule": {
        "desc": "'optional' used as validation rule (should be nullable/sometimes)",
        "pattern": r"'optional'",
        "files": ["Request"],
    },
    "cross_resource_import": {
        "desc": "Resource class used in toArray() without import",
        "pattern": None,  # custom check
        "files": ["Resource"],
    },
    "was_recently_created": {
        "desc": "wasRecentlyCreated used for created_at/updated_at",
        "pattern": r"wasRecentlyCreated|wasRecentlyUpdated",
        "files": ["Resource"],
    },
    "validated_on_base_request": {
        "desc": "$request->validated() called after $request->validate() on base Request",
        "pattern": r"\$request->validate\([^)]+\);\s*[^\n]*\n[^\n]*\$(?:data|validated|result)\s*=\s*\$request->validated\(\)",
        "files": ["Controller"],
    },
    "relationship_assumption": {
        "desc": "$request->user()->relation()->create() used (assumes user relationship)",
        "pattern": r"\$request->user\(\)->\w+\(\)->create\(",
        "files": ["Controller"],
    },
    "missing_controller_import": {
        "desc": "Controller class used in sub-namespace without import",
        "pattern": None,  # custom check
        "files": ["Controller"],
    },
    "missing_hasfactory": {
        "desc": "Eloquent model missing 'use HasFactory' trait",
        "pattern": None,  # custom check
        "files": [],  # checked by custom function on all files
    },
    "missing_relation_import": {
        "desc": "Relationship method uses return type without importing it",
        "pattern": None,  # custom check
        "files": [],
    },
}


def check_php_syntax(path: str) -> tuple[bool, str]:
    r = subprocess.run(["php", "-l", path], capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip() + r.stderr.strip()


def check_cross_resource_imports(content: str, filename: str) -> list[str]:
    """Find Resource classes used without import."""
    if "Resource" not in filename:
        return []
    # Find all XxxResource references in toArray() body (class names ending in Resource)
    used = set(re.findall(r'\b([A-Z][a-zA-Z]+Resource)\b', content))
    # Remove the class itself
    class_match = re.search(r'class\s+(\w+Resource)', content)
    if class_match:
        used.discard(class_match.group(1))
    # Ignore JsonResource (from Illuminate)
    used.discard('JsonResource')

    missing = []
    for res in sorted(used):
        # Check if it's imported
        if f'use App\\Http\\Resources\\{res};' not in content:
            missing.append(res)
    return missing


def check_controller_imports(content: str, filename: str) -> list[str]:
    """Check controller sub-namespace imports."""
    if "Controller" not in filename:
        return []
    if 'namespace App\\Http\\Controllers\\Api' not in content:
        return []
    missing = []
    if 'extends Controller' in content and 'use App\\Http\\Controllers\\Controller;' not in content:
        missing.append('Controller')
    if re.search(r'(?<![A-Za-z])Request \$request', content) and 'use Illuminate\\Http\\Request;' not in content:
        missing.append('Illuminate\\Http\\Request')
    return missing


def check_model_hasfactory(content: str, filename: str) -> list[str]:
    """Check that Eloquent models include use HasFactory."""
    if 'extends Model' not in content:
        return []
    if 'use HasFactory' not in content:
        return ['model missing use HasFactory trait']
    if 'Factories\\HasFactory' not in content:
        return ['HasFactory trait used but not imported from Factories namespace']
    return []


def check_relationship_imports(content: str, filename: str) -> list[str]:
    """Every relationship return type must have a corresponding use import."""
    rel_types = ['BelongsTo', 'HasMany', 'HasOne', 'BelongsToMany',
                 'MorphTo', 'MorphMany', 'MorphOne']
    missing = []
    for rel_type in rel_types:
        if re.search(rf'public function \w+\(\):\s*{rel_type}\b', content):
            if f'use Illuminate\\Database\\Eloquent\\Relations\\{rel_type};' not in content:
                missing.append(rel_type)
    if missing:
        return [f'missing: {", ".join(missing)}']
    return []


def analyze_file(path: str) -> dict:
    filename = os.path.basename(path)
    with open(path) as f:
        content = f.read()

    result = {
        "file": filename,
        "php_valid": False,
        "bugs": [],
        "content_length": len(content),
    }

    # PHP syntax
    valid, msg = check_php_syntax(path)
    result["php_valid"] = valid
    if not valid:
        result["bugs"].append(f"PHP_SYNTAX_ERROR: {msg[:100]}")

    # Pattern-based bugs
    for bug_id, bug in BUGS.items():
        if bug["pattern"] is None:
            continue
        if any(t in filename for t in bug["files"]) or not bug["files"]:
            if re.search(bug["pattern"], content, re.DOTALL | re.MULTILINE):
                result["bugs"].append(f"{bug_id}: {bug['desc']}")

    # Cross-resource imports
    missing_res = check_cross_resource_imports(content, filename)
    if missing_res:
        result["bugs"].append(f"cross_resource_import: Missing imports for: {', '.join(missing_res)}")

    # Controller imports
    missing_ctrl = check_controller_imports(content, filename)
    if missing_ctrl:
        result["bugs"].append(f"missing_controller_import: Missing: {', '.join(missing_ctrl)}")

    # HasFactory check on Eloquent models
    missing_factory = check_model_hasfactory(content, filename)
    if missing_factory:
        result["bugs"].append(f"missing_hasfactory: {missing_factory[0]}")

    # Relationship import check
    missing_rel_imports = check_relationship_imports(content, filename)
    if missing_rel_imports:
        result["bugs"].append(f"missing_relation_import: {missing_rel_imports[0]}")

    return result


def analyze_directory(directory: str) -> None:
    php_files = []
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith('.php') and 'test' not in f.lower() and 'factory' not in f.lower():
                php_files.append(os.path.join(root, f))
    php_files.sort()

    print(f"\n{'='*60}")
    print(f"Analysis: {directory}")
    print(f"{'='*60}")

    valid_count = 0
    perfect_count = 0
    total_bugs = 0
    bug_summary = {}

    for path in php_files:
        r = analyze_file(path)
        rel = path.replace(directory + '/', '')
        if r["php_valid"]:
            valid_count += 1
        bugs = r["bugs"]
        perfect = r["php_valid"] and not bugs
        if perfect:
            perfect_count += 1
        total_bugs += len(bugs)

        status = "✅" if perfect else ("⚠️" if r["php_valid"] else "❌")
        print(f"{status} {rel}")
        for b in bugs:
            bug_type = b.split(':')[0]
            bug_summary[bug_type] = bug_summary.get(bug_type, 0) + 1
            print(f"     └─ {b}")

    n = len(php_files)
    print(f"\n{'─'*60}")
    print(f"Files: {n} | PHP valid: {valid_count}/{n} | Perfect: {perfect_count}/{n} | Bugs: {total_bugs}")
    if bug_summary:
        print("\nBug breakdown:")
        for bug_type, count in sorted(bug_summary.items(), key=lambda x: -x[1]):
            print(f"  {bug_type}: {count}")


if __name__ == "__main__":
    dirs = sys.argv[1:] if len(sys.argv) > 1 else ["."]
    for d in dirs:
        if os.path.isdir(d):
            analyze_directory(d)
        else:
            print(f"Not a directory: {d}")
