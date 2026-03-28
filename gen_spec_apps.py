#!/usr/bin/env python3
"""gen_spec_apps.py — Generate 3-app benchmark using JSON BuildSpec format.

Each artifact is described as a JSON spec rather than natural-language prose.
Tests whether structured spec input produces better code than text prompts.

Usage:
  python3 gen_spec_apps.py                        # use adapters_v9 (zero-shot spec test)
  python3 gen_spec_apps.py adapters_spec          # use spec-trained adapter
  python3 gen_spec_apps.py adapters_spec_v2 --compile  # use compiler before generation
"""
import argparse, os, sys, json, time
from mlx_lm import load, generate

parser = argparse.ArgumentParser()
parser.add_argument("adapter", nargs="?", default="adapters_v9")
parser.add_argument("--compile", action="store_true", help="Run spec_compiler before generation")
parser.add_argument("--migrations-dir", default=None, help="Path to migrations dir for schema validation")
args = parser.parse_args()

ADAPTER = args.adapter
USE_COMPILER = args.compile
MIGRATIONS_DIR = args.migrations_dir

if USE_COMPILER:
    from spec_compiler import compile_spec, SpecCompileError
BASE_MODEL = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"

print(f"Loading model with adapter: {ADAPTER} {'(+compiler)' if USE_COMPILER else ''} ...")
model, tokenizer = load(BASE_MODEL, adapter_path=ADAPTER)
print("Model loaded.")

# ── System prompt for spec→code ─────────────────────────────────────────────
SYSTEM = """You are a Laravel 13.x PHP code generator. Input is a BuildSpec JSON object. Output is the complete PHP file.

Rules:
- Output ONLY the PHP file. No markdown fences. No explanation. No comments beyond code.
- Implement EXACTLY what the spec says. Do not add fields, relationships, or methods not in the spec.
- artifact=model: ALWAYS add `use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;` and `use HasFactory;` when has_factory=true. ONLY add relationship methods listed in relationships[]. Import every relationship return type (BelongsTo, HasMany, BelongsToMany, etc.).
- artifact=controller: ALWAYS import `use App\\Http\\Controllers\\Controller;` and `use Illuminate\\Http\\Request;`. destroy() returns response()->noContent(). store() returns response()->json($resource, 201).
- artifact=resource: ALWAYS import `use Illuminate\\Http\\Resources\\Json\\JsonResource;`. Import every Resource class used in toArray().
- artifact=form_request: rules() returns exact rules from spec. If conditional_rules present, expand each field using $this->isMethod('POST') ternary or spread. For POST-only rules use spread: `...$this->isMethod('POST') ? ['rule'] : []`. authorize() returns true. When unique_ignore_route_param is set (non-null), replace any 'unique:table,col' string rule with Rule::unique('table', 'col')->ignore($this->route('param')). Import use Illuminate\\Validation\\Rule; at the top.
- artifact=controller: If validation_mode=inline use $request->validate([...]) in store() and update(). If validation_mode=form_request import and use the FormRequest class. When the model has FK fields in fillable (e.g. author_id), ALWAYS include them in $request->validated() passed to Model::create(). NEVER exclude FK fields or set them separately after create()."""


def gen(spec: dict, max_tokens: int = 1000) -> str:
    if USE_COMPILER and spec.get("artifact") != "migration":
        try:
            spec = compile_spec(spec, migrations_dir=MIGRATIONS_DIR)
        except SpecCompileError as e:
            raise RuntimeError(f"Spec compile error for {spec.get('artifact')} {spec.get('class')}:\n{e}") from e
    spec_str = json.dumps(spec, indent=2)
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": spec_str},
    ]
    text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    text += "<?php\n"
    result = generate(model, tokenizer, prompt=text, max_tokens=max_tokens, verbose=False)
    if "<|im_end|>" in result:
        result = result[:result.find("<|im_end|>")]
    lines = result.split("\n")
    real = [i for i, l in enumerate(lines) if l.strip() and l.strip() != "!" and not l.strip().startswith("![]")]
    result = "\n".join(lines[:real[-1] + 1]) if real else result
    return "<?php\n" + result.lstrip("<?php\n")


def save(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    name = os.path.basename(path)
    print(f"  ✅ {name}")


# ── APP 1: Subscriber API ─────────────────────────────────────────────────────
print("\n=== App 1: Subscriber API ===")
D1 = "/Users/fch/qwen/app1_subscriber_spec_v5_generated"

save(f"{D1}/database/migrations/2026_03_28_200001_create_subscribers_table.php", gen({
    "laravel_version": "13.x",
    "artifact": "migration",
    "operation": "create",
    "table": "subscribers",
    "columns": [
        {"name": "email", "type": "string", "unique": True},
        {"name": "name", "type": "string"},
        {"name": "status", "type": "string", "default": "active"},
        {"name": "subscribed_at", "type": "timestamp", "nullable": True}
    ],
    "timestamps": True,
    "soft_deletes": False
}))

save(f"{D1}/app/Models/Subscriber.php", gen({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Subscriber",
    "namespace": "App\\Models",
    "table": "subscribers",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["email", "name", "status", "subscribed_at"],
    "casts": {"subscribed_at": "datetime", "status": "string"},
    "relationships": [],
    "scopes": [
        {"name": "active", "column": "status", "value": "active"},
        {"name": "unsubscribed", "column": "status", "value": "unsubscribed"}
    ]
}))

save(f"{D1}/app/Http/Resources/SubscriberResource.php", gen({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "SubscriberResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id", "source": "id"},
        {"key": "email", "source": "email"},
        {"key": "name", "source": "name"},
        {"key": "status", "source": "status"},
        {"key": "subscribed_at", "source": "subscribed_at", "modifier": "whenNotNull"},
        {"key": "created_at", "source": "created_at"},
        {"key": "updated_at", "source": "updated_at"}
    ],
    "loaded_relations": []
}))

save(f"{D1}/app/Http/Requests/StoreSubscriberRequest.php", gen({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreSubscriberRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "email": ["required", "email", "max:255", "unique:subscribers,email"],
        "name": ["required", "string", "max:255"],
        "status": ["nullable", "string", "in:active,unsubscribed"],
        "subscribed_at": ["nullable", "date"]
    },
    "unique_ignore_route_param": None
}))

save(f"{D1}/app/Http/Controllers/Api/SubscriberController.php", gen({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "SubscriberController",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Subscriber",
    "model_namespace": "App\\Models",
    "resource": "SubscriberResource",
    "form_request": "StoreSubscriberRequest",
    "actions": {
        "index": {"paginate": 15, "filters": [{"param": "status", "column": "status"}], "eager_load": []},
        "store": {"status_code": 201, "many_to_many": None},
        "show": {"eager_load": []},
        "update": {"many_to_many": None},
        "destroy": {"force_delete": False}
    }
}, max_tokens=1200))

print(f"App 1 done → {D1}")

# ── APP 2: Book Library ───────────────────────────────────────────────────────
print("\n=== App 2: Book Library ===")
D2 = "/Users/fch/qwen/app2_library_spec_v5_generated"

save(f"{D2}/database/migrations/2026_03_28_300001_create_authors_table.php", gen({
    "laravel_version": "13.x",
    "artifact": "migration",
    "operation": "create",
    "table": "authors",
    "columns": [
        {"name": "name", "type": "string"},
        {"name": "bio", "type": "text", "nullable": True},
        {"name": "nationality", "type": "string", "nullable": True}
    ],
    "timestamps": True,
    "soft_deletes": False
}))

save(f"{D2}/database/migrations/2026_03_28_300002_create_books_table.php", gen({
    "laravel_version": "13.x",
    "artifact": "migration",
    "operation": "create",
    "table": "books",
    "columns": [
        {"name": "author_id", "type": "foreignId", "constrained": "authors", "on_delete": "cascade"},
        {"name": "title", "type": "string"},
        {"name": "isbn", "type": "string", "unique": True, "length": 20},
        {"name": "description", "type": "text", "nullable": True},
        {"name": "year", "type": "integer", "nullable": True},
        {"name": "pages", "type": "integer", "nullable": True},
        {"name": "status", "type": "string", "nullable": True}
    ],
    "timestamps": True,
    "soft_deletes": True
}))

save(f"{D2}/app/Models/Author.php", gen({
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
        {"type": "HasMany", "method": "books", "related": "Book"}
    ],
    "scopes": []
}))

save(f"{D2}/app/Models/Book.php", gen({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Book",
    "namespace": "App\\Models",
    "table": "books",
    "has_factory": True,
    "soft_deletes": True,
    "fillable": ["title", "isbn", "description", "author_id", "year", "pages", "status"],
    "casts": {"year": "integer", "pages": "integer"},
    "relationships": [
        {"type": "BelongsTo", "method": "author", "related": "Author"}
    ],
    "scopes": []
}))

save(f"{D2}/app/Http/Resources/AuthorResource.php", gen({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "AuthorResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id", "source": "id"},
        {"key": "name", "source": "name"},
        {"key": "bio", "source": "bio", "modifier": "whenNotNull"},
        {"key": "nationality", "source": "nationality", "modifier": "whenNotNull"},
        {"key": "created_at", "source": "created_at"}
    ],
    "loaded_relations": [
        {"key": "books", "resource": "BookResource", "type": "collection"},
        {"key": "books_count", "modifier": "whenCounted"}
    ]
}))

save(f"{D2}/app/Http/Resources/BookResource.php", gen({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "BookResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id", "source": "id"},
        {"key": "title", "source": "title"},
        {"key": "isbn", "source": "isbn"},
        {"key": "description", "source": "description", "modifier": "whenNotNull"},
        {"key": "year", "source": "year"},
        {"key": "pages", "source": "pages", "modifier": "whenNotNull"},
        {"key": "status", "source": "status"},
        {"key": "created_at", "source": "created_at"},
        {"key": "updated_at", "source": "updated_at"}
    ],
    "loaded_relations": [
        {"key": "author", "resource": "AuthorResource", "type": "make"}
    ]
}))

save(f"{D2}/app/Http/Requests/StoreBookRequest.php", gen({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreBookRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "title": ["required", "string", "max:255"],
        "isbn": ["required", "string", "max:20", "unique:books,isbn"],
        "description": ["nullable", "string"],
        "author_id": ["required", "integer", "exists:authors,id"],
        "year": ["required", "integer", "min:1000", "max:2100"],
        "pages": ["nullable", "integer", "min:1"],
        "status": ["nullable", "string", "in:draft,published,archived"]
    },
    "unique_ignore_route_param": "book"
}))

save(f"{D2}/app/Http/Controllers/Api/AuthorController.php", gen({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "AuthorController",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Author",
    "model_namespace": "App\\Models",
    "resource": "AuthorResource",
    "form_request": None,
    "inline_validation": {
        "store": {"name": "required|string|max:255", "bio": "nullable|string", "nationality": "nullable|string|max:100"},
        "update": {"name": "sometimes|string|max:255", "bio": "sometimes|string", "nationality": "sometimes|string|max:100"}
    },
    "actions": {
        "index": {"paginate": 15, "filters": [], "with_count": ["books"]},
        "store": {"status_code": 201, "many_to_many": None},
        "show": {"eager_load": ["books"]},
        "update": {"many_to_many": None},
        "destroy": {"force_delete": False}
    }
}, max_tokens=1200))

save(f"{D2}/app/Http/Controllers/Api/BookController.php", gen({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "BookController",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Book",
    "model_namespace": "App\\Models",
    "resource": "BookResource",
    "form_request": "StoreBookRequest",
    "actions": {
        "index": {
            "paginate": 15,
            "filters": [{"param": "status", "column": "status"}],
            "eager_load": ["author"]
        },
        "store": {"status_code": 201, "eager_load_after": ["author"], "many_to_many": None},
        "show": {"eager_load": ["author"]},
        "update": {"many_to_many": None},
        "destroy": {"force_delete": False}
    }
}, max_tokens=1200))

print(f"App 2 done → {D2}")

# ── APP 3: Event Management ───────────────────────────────────────────────────
print("\n=== App 3: Event Management ===")
D3 = "/Users/fch/qwen/app3_events_spec_v5_generated"

save(f"{D3}/database/migrations/2026_03_28_400001_create_venues_table.php", gen({
    "laravel_version": "13.x",
    "artifact": "migration",
    "operation": "create",
    "table": "venues",
    "columns": [
        {"name": "name", "type": "string"},
        {"name": "address", "type": "text"},
        {"name": "capacity", "type": "integer", "nullable": True}
    ],
    "timestamps": True,
    "soft_deletes": False
}))

save(f"{D3}/database/migrations/2026_03_28_400002_create_speakers_table.php", gen({
    "laravel_version": "13.x",
    "artifact": "migration",
    "operation": "create",
    "table": "speakers",
    "columns": [
        {"name": "name", "type": "string"},
        {"name": "email", "type": "string", "unique": True},
        {"name": "bio", "type": "text", "nullable": True}
    ],
    "timestamps": True,
    "soft_deletes": False
}))

save(f"{D3}/database/migrations/2026_03_28_400003_create_events_table.php", gen({
    "laravel_version": "13.x",
    "artifact": "migration",
    "operation": "create",
    "table": "events",
    "columns": [
        {"name": "title", "type": "string"},
        {"name": "description", "type": "text", "nullable": True},
        {"name": "venue_id", "type": "foreignId", "constrained": "venues", "on_delete": "cascade"},
        {"name": "event_date", "type": "datetime"},
        {"name": "status", "type": "string", "default": "draft"}
    ],
    "timestamps": True,
    "soft_deletes": True
}))

save(f"{D3}/database/migrations/2026_03_28_400004_create_event_speaker_table.php", gen({
    "laravel_version": "13.x",
    "artifact": "migration",
    "operation": "create",
    "table": "event_speaker",
    "pivot": True,
    "columns": [
        {"name": "event_id", "type": "foreignId", "constrained": "events", "on_delete": "cascade"},
        {"name": "speaker_id", "type": "foreignId", "constrained": "speakers", "on_delete": "cascade"}
    ],
    "timestamps": False,
    "soft_deletes": False
}))

save(f"{D3}/app/Models/Venue.php", gen({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Venue",
    "namespace": "App\\Models",
    "table": "venues",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["name", "address", "capacity"],
    "casts": {},
    "relationships": [
        {"type": "HasMany", "method": "events", "related": "Event"}
    ],
    "scopes": []
}))

save(f"{D3}/app/Models/Speaker.php", gen({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Speaker",
    "namespace": "App\\Models",
    "table": "speakers",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["name", "email", "bio"],
    "casts": {},
    "relationships": [
        {"type": "BelongsToMany", "method": "events", "related": "Event"}
    ],
    "scopes": []
}))

save(f"{D3}/app/Models/Event.php", gen({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Event",
    "namespace": "App\\Models",
    "table": "events",
    "has_factory": True,
    "soft_deletes": True,
    "fillable": ["title", "description", "venue_id", "event_date", "status"],
    "casts": {"event_date": "datetime", "status": "string"},
    "relationships": [
        {"type": "BelongsTo", "method": "venue", "related": "Venue"},
        {"type": "BelongsToMany", "method": "speakers", "related": "Speaker"}
    ],
    "scopes": []
}))

save(f"{D3}/app/Http/Resources/VenueResource.php", gen({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "VenueResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id", "source": "id"},
        {"key": "name", "source": "name"},
        {"key": "address", "source": "address"},
        {"key": "capacity", "source": "capacity", "modifier": "whenNotNull"}
    ],
    "loaded_relations": []
}))

save(f"{D3}/app/Http/Resources/SpeakerResource.php", gen({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "SpeakerResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id", "source": "id"},
        {"key": "name", "source": "name"},
        {"key": "email", "source": "email"},
        {"key": "bio", "source": "bio", "modifier": "whenNotNull"}
    ],
    "loaded_relations": []
}))

save(f"{D3}/app/Http/Resources/EventResource.php", gen({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "EventResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id", "source": "id"},
        {"key": "title", "source": "title"},
        {"key": "description", "source": "description", "modifier": "whenNotNull"},
        {"key": "event_date", "source": "event_date"},
        {"key": "status", "source": "status"},
        {"key": "created_at", "source": "created_at"}
    ],
    "loaded_relations": [
        {"key": "venue", "resource": "VenueResource", "type": "make"},
        {"key": "speakers", "resource": "SpeakerResource", "type": "collection"}
    ]
}))

save(f"{D3}/app/Http/Requests/StoreEventRequest.php", gen({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreEventRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "title": ["required", "string", "max:255"],
        "description": ["nullable", "string"],
        "venue_id": [],
        "event_date": ["required", "date"],
        "status": ["nullable", "string", "in:draft,published,cancelled"],
        "speaker_ids": ["nullable", "array"],
        "speaker_ids.*": ["integer", "exists:speakers,id"]
    },
    "conditional_rules": {
        "venue_id": {
            "POST": ["required", "integer", "exists:venues,id"],
            "PUT":  ["sometimes", "integer", "exists:venues,id"]
        },
        "event_date": {
            "POST": ["after:now"]
        }
    }
}))

save(f"{D3}/app/Http/Controllers/Api/EventController.php", gen({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "EventController",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Event",
    "model_namespace": "App\\Models",
    "resource": "EventResource",
    "form_request": "StoreEventRequest",
    "actions": {
        "index": {
            "paginate": 10,
            "filters": [{"param": "status", "column": "status"}],
            "eager_load": ["venue", "speakers"]
        },
        "store": {
            "status_code": 201,
            "many_to_many": {"relation": "speakers", "input_key": "speaker_ids"},
            "except_keys": ["speaker_ids"],
            "eager_load_after": ["venue", "speakers"]
        },
        "show": {"eager_load": ["venue", "speakers"]},
        "update": {
            "many_to_many": {"relation": "speakers", "input_key": "speaker_ids"},
            "except_keys": ["speaker_ids"]
        },
        "destroy": {"force_delete": False}
    }
}, max_tokens=1400))

print(f"App 3 done → {D3}")
print(f"\n=== All spec generation complete (adapter: {ADAPTER}) ===")
