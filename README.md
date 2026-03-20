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

Training data: [fchis/Laravel-13x-Code-Instructions](https://huggingface.co/datasets/fchis/Laravel-13x-Code-Instructions) (162 examples)

All models fine-tuned on Apple M2 Pro 16GB in ~5-7 minutes each using [Laravel Boost](https://laravel.com/docs/13.x/boost) guidelines.

## Patterns Covered (15+ class types)

The 7B coder (v2) generates correct code for:

- **Eloquent Models** — fillable, casts, relationships, scopes, soft deletes
- **Migrations** — create table, alter table, foreign keys, pivot tables
- **Form Requests** — validation rules (array and pipe syntax)
- **Controllers** — API resource, CRUD, route model binding
- **Queue Jobs** — ShouldQueue, constructor injection, handle()
- **Events** — Dispatchable, SerializesModels
- **Listeners** — event handling, queued listeners
- **Notifications** — mail + database channels, Queueable
- **Factories** — definition, states, relationships
- **Seeders** — model creation, bulk data
- **Policies** — authorization methods
- **Observers** — model lifecycle hooks
- **Artisan Commands** — signature, handle, arguments
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

**What works well**: Migrations, models, form requests — consistently good output when instructions are specific.

**What needs improvement**: Controllers can use wrong patterns (`$request->user()` when no auth), routes default to apiResource without custom endpoints, planner gives vague instructions.

**The key insight**: The coder produces perfect output when instructions list exact fields, methods, and behavior. Most issues trace back to vague instructions, not model capability.

### The Repetition Problem

Small models (3B-7B) can enter repetition loops on longer outputs (>300 tokens). This happens when vague instructions trigger pretraining archetypes — the model "remembers" generic patterns and can't stop generating. Mitigated by: specific instructions, token caps, post-processing repetition detection.

### Evaluation Caveats

- Tested on a limited number of prompts, not a rigorous benchmark
- Test prompts closely match training patterns
- A proper evaluation using [Laravel's official 17-task benchmark](https://laravel.com/blog/which-ai-model-is-best-for-laravel) has not been done
- Results are exploratory — broader testing needed

## How It Was Built

23-step research investigation into local AI-assisted Laravel code generation:

1. Tested multiple models on 16GB Mac (GPT-OSS-20B, Qwen 14B, yannelli's Laravel models)
2. Found that instruction-to-code training format produces code generators, doc-Q&A produces documentation assistants
3. Fine-tuned planner (Qwen3-1.7B) and coder (Qwen2.5-Coder-3B/7B) with MLX
4. Integrated [Laravel Boost](https://laravel.com/docs/13.x/boost) guidelines into training
5. Added 23 new patterns (Jobs, Events, Notifications, Factories, etc.) — val loss dropped from 0.503 to 0.178
6. Tested GRPO (ineffective — failures are semantic), DoRA (better patterns but more memory)
7. Tested on real Laravel projects (todo app, contact form)

## License

Apache 2.0
