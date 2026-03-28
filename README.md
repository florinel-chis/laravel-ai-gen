# Laravel AI Code Generator

A two-model AI pipeline that generates Laravel PHP code from natural language. Runs entirely on Apple Silicon Macs using MLX. No cloud GPU needed.

## How It Works

```
You: "REST API for a todo app - tasks with title, mark as completed"
                    |
    [Planner Model - 1.7B params, ~1.5s]
    Decomposes into tasks with file paths
                    |
    [Coder Model - 7B params, ~12s per file]
    Generates production-ready PHP for each task
                    |
    Files written to your Laravel project
```

**Total memory: ~4-6 GB. Both models loaded simultaneously.**

## Quick Start

```bash
pip install mlx-lm

# Full pipeline: describe a feature, get files
python3 laravel-gen.py "simple contact form - name, email, subject, message"

# Preview only (don't write files)
python3 laravel-gen.py --list "add favorites feature with pagination"

# Single file mode: give a specific instruction
python3 laravel-gen.py --coder-only "Create a Laravel Eloquent model for Contact with fillable fields: name, email, subject, message"

# Use 7B coder (better quality, needs 16GB+ RAM)
python3 laravel-gen.py --model 7b "REST API for a todo app"
```

Models are downloaded automatically from HuggingFace on first run.

## Models

| Model | Params | Role | HuggingFace |
|-------|--------|------|-------------|
| Planner | 1.7B | Decompose features into tasks with file paths | [fchis/Laravel-13x-Planner-Qwen3-1.7B-LoRA](https://huggingface.co/fchis/Laravel-13x-Planner-Qwen3-1.7B-LoRA) |
| Coder (default) | 3B | Generate code (faster, ~1-2s/file) | [fchis/Laravel-13x-Qwen2.5-Coder-3B-Instruct-LoRA](https://huggingface.co/fchis/Laravel-13x-Qwen2.5-Coder-3B-Instruct-LoRA) |
| **Coder (recommended)** | **7B** | **Generate code (best quality, ~12s/file)** | [fchis/Laravel-13x-Qwen2.5-Coder-7B-Instruct-LoRA](https://huggingface.co/fchis/Laravel-13x-Qwen2.5-Coder-7B-Instruct-LoRA) |

Training data: [fchis/Laravel-13x-Code-Instructions](https://huggingface.co/datasets/fchis/Laravel-13x-Code-Instructions) (235 examples)

All models fine-tuned on Apple M2 Pro 16GB in ~7-20 minutes each using [Laravel Boost](https://laravel.com/docs/13.x/boost) guidelines.

## Patterns Covered (18+ class types)

The 7B coder (v5) generates correct code for:

- **Eloquent Models** — fillable, casts, relationships, scopes, soft deletes
- **Migrations** — create table, alter table, foreign keys, pivot tables
- **Form Requests** — rules, `messages()`, `attributes()`, `prepareForValidation()`, `after()` cross-field validation
- **API Resources** — `JsonResource` with `whenLoaded()`, `$this->when()`, `mergeWhen()`, `whenNotNull()`, `ResourceCollection` with custom `with()` metadata
- **Pest Feature Tests** — CRUD, auth/authorization, validation, pagination, `Queue::fake()`, `Mail::fake()`
- **Controllers** — API resource, CRUD, route model binding
- **Queue Jobs** — ShouldQueue, constructor injection, handle()
- **Events** — Dispatchable, SerializesModels
- **Listeners** — event handling, queued listeners
- **Notifications** — mail + database channels, Queueable
- **Factories** — definition, states, relationships
- **Seeders** — model creation, bulk data
- **Policies** — authorization methods
- **Observers** — model lifecycle hooks
- **Artisan Commands** — signature, handle, arguments, CSV/JSON/HTTP data operations, progress bars, interactive prompts, file export, chunked imports, Storage facade
- **Blade Components** — class components with props
- **Mailables** — envelope, content, markdown
- **Routes** — API resource, groups, custom endpoints

## Real Test: Todo REST API

Generated with specific instructions, tested in a real Laravel 13.x project:

| File | Valid PHP | Usable as-is |
|------|----------|-------------|
| Migration (tasks table) | Yes | **Yes** — correct columns, FK, cascadeOnDelete |
| Model (Task) | Yes | **Yes** — fillable, belongsTo, casts |
| Form Request | Yes | **Yes** — title required, string, max 255 |
| Controller (CRUD + toggle) | Yes | Minor fix — used `$request->user()` instead of direct create |
| Routes | Yes | Minor fix — used apiResource without custom toggle route |

All 7 endpoints work: create, list, toggle, delete, validation.

## Requirements

- **Hardware**: Apple Silicon Mac (M1/M2/M3/M4) with 8GB+ RAM (16GB for 7B model)
- **Python**: 3.10+
- **Dependencies**: `mlx-lm` (`pip install mlx-lm`)

## Limitations

This is a research project, not a production tool.

**What works well**: Migrations, models, form requests (including precision hooks), API resources with whenLoaded, Artisan commands, Pest feature tests — consistently good output when instructions are specific.

**What needs improvement**: For Pest tests, explicitly say "use Pest function syntax (uses/test/it)" to avoid PHPUnit class-based output. Controllers can use wrong patterns without auth context. Planner gives vague instructions.

**The key insight**: The coder produces perfect output when instructions list exact fields, methods, and behavior. Most issues trace back to vague instructions, not model capability.

### API Resources (v5)

The 7B v5 model covers all key relationship loading patterns:

```bash
python3 laravel-gen.py --coder-only "Create UserResource with whenLoaded for posts (PostResource collection) and subscription (SubscriptionResource). Use whenNotNull for email_verified_at."
```

Generated code correctly uses `whenLoaded()`, not `$this->posts` — **3/3 resource eval prompts pass**.

### Form Request Precision (v5)

```bash
python3 laravel-gen.py --coder-only "StoreInvoiceRequest with messages() for required/numeric rules, attributes() renaming client_id and due_date, prepareForValidation() that rounds amount to 2 decimal places"
```

Generated code correctly uses `messages()` with `field.rule` keys, `prepareForValidation()` calls `$this->merge()` — **2/2 form request eval prompts pass**.

### Pest Feature Tests (v5)

```bash
python3 laravel-gen.py --coder-only "Write a Pest feature test (Pest function syntax) for POST /api/posts: authenticated user creates post (assertCreated + assertDatabaseHas), unauthenticated returns 401, missing title returns 422"
```

All 6 generated test assertions pass in a real Laravel 13.2.0 project:
```
Tests: 6 passed (13 assertions)
```

### Artisan Commands: CSV/JSON/HTTP (v4+)

The 7B v4 model was trained on 40+ Artisan command examples. Sprint 2 (v4) eliminated 3 precision bugs — **5/5 × 11/11 eval score, zero manual fixes needed**. v5 confirms no regression.

### The Repetition Problem

Small models (3B-7B) can enter repetition loops on longer outputs (>300 tokens). This happens when vague instructions trigger pretraining archetypes — the model "remembers" generic patterns and can't stop generating. Mitigated by: specific instructions, token caps, post-processing repetition detection, and end-token stripping (`<|im_end|>`).

### Evaluation Caveats

- Eval prompts are structurally similar to training patterns — not a rigorous benchmark
- A proper evaluation using [Laravel's official 17-task benchmark](https://laravel.com/blog/which-ai-model-is-best-for-laravel) has not been done (we cover ~5/17 tasks)
- Results are exploratory — broader testing needed

## How It Was Built

28-step research investigation into local AI-assisted Laravel code generation:

1. Tested multiple models on 16GB Mac (GPT-OSS-20B, Qwen 14B, yannelli's Laravel models)
2. Found that instruction-to-code training format produces code generators, doc-Q&A produces documentation assistants
3. Fine-tuned planner (Qwen3-1.7B) and coder (Qwen2.5-Coder-3B/7B) with MLX
4. Integrated [Laravel Boost](https://laravel.com/docs/13.x/boost) guidelines into training
5. Added 23 new patterns (Jobs, Events, Notifications, Factories, etc.) — val loss dropped from 0.503 to 0.178
6. Tested GRPO (ineffective — failures are semantic), DoRA (better patterns but more memory)
7. Tested on real Laravel projects (todo app, contact form)
8. Diagnosed Artisan command repetition bug (only 2/145 training examples → model hallucinated fake `Facades\Progress`)
9. Added 25 targeted Artisan command examples (CSV/JSON/HTTP data operations) — val loss 0.076
10. Sprint 2: targeted precision fixes (3 bug patterns eliminated) — val loss 0.055, 5/5 × 11/11
11. Sprint 3: API Resources + Form Request precision + Pest tests — val loss 0.032, 14/14 test assertions pass in real Laravel

## BuildSpec Pipeline (New)

A second, higher-precision pipeline using structured **BuildSpec JSON** instead of natural language.

```bash
# NL → specs → compile → generate PHP
python3 pipeline_spec.py "Create a REST API for managing blog posts with tags"

# Skip planner — use a spec file directly
python3 pipeline_spec.py --spec specs.json --output ./generated

# Plan only (inspect specs before generating)
python3 pipeline_spec.py --plan-only "REST API for subscribers"
```

**Why spec-first?** Natural language gives the model room to hallucinate. BuildSpec removes that ambiguity:

| Stage | Tool | What it does |
|-------|------|-------------|
| 1. Plan | `planner.py` | NL → BuildSpec JSON array (few-shot) |
| 2. Compile | `spec_compiler.py` | Validates + normalizes each spec, catches errors before generation |
| 3. Generate | `pipeline_spec.py` | Each spec → PHP file (adapters_spec_v4) |
| 4. Check | `php -l` | Syntax-validates all written files |

**LoRA adapter**: [fchis/Laravel-13x-Qwen2.5-Coder-7B-Instruct-LoRA-Spec](https://huggingface.co/fchis/Laravel-13x-Qwen2.5-Coder-7B-Instruct-LoRA-Spec)
**Training dataset**: [fchis/laravel-buildspec-training](https://huggingface.co/datasets/fchis/laravel-buildspec-training) (49 examples)

### Ablation: Spec vs Prompt

| Config | Pest tests | Manual fixes | Error type |
|--------|-----------|-------------|------------|
| Prompt (adapters_v9) | 52/58 | 5 | Semantic hallucinations |
| BuildSpec (adapters_spec_v4) | 20/20 | 4 | Spec quality issues |

Spec errors are compiler-catchable before generation. Prompt errors require runtime debugging.

## License

Apache 2.0
