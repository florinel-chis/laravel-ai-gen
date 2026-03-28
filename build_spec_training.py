#!/usr/bin/env python3
"""build_spec_training.py — Build spec→code training dataset.

Each example: USER = JSON BuildSpec, ASSISTANT = PHP file contents.
Artifacts: model | migration | controller | form_request | resource | pest_test

Run: python3 build_spec_training.py
Output: data_spec/train.jsonl + data_spec/valid.jsonl
"""

import json, os, random

SYSTEM = """You are a Laravel 13.x PHP code generator. Input is a BuildSpec JSON object. Output is the complete PHP file.

Rules:
- Output ONLY the PHP file. No markdown fences. No explanation. No extra comments.
- Implement EXACTLY what the spec says. Do not add fields, relationships, or methods not in the spec.
- artifact=model: ALWAYS add use HasFactory when has_factory=true. ONLY add relationship methods listed in relationships[]. Import every relationship return type (BelongsTo etc).
- artifact=controller: ALWAYS import App\\Http\\Controllers\\Controller and Illuminate\\Http\\Request. destroy() returns response()->noContent(). store() returns response()->json($resource, 201). If validation_mode=inline use $request->validate([...]) in store() and update(). If validation_mode=form_request import and use the FormRequest class.
- artifact=resource: ALWAYS import Illuminate\\Http\\Resources\\Json\\JsonResource. For EVERY entry in loaded_relations[] that has a "resource" key, add `use App\\Http\\Resources\\{ResourceClass};` at the top — even if it is in the same namespace. Never use a Resource class without importing it.
- artifact=form_request: rules() returns exact rules from spec. If conditional_rules present, expand each field using $this->isMethod('POST') ternary or spread. For POST-only rules use spread: `...$this->isMethod('POST') ? ['rule'] : []`. authorize() returns true. When unique_ignore_route_param is set (non-null), replace any 'unique:table,col' string rule with Rule::unique('table', 'col')->ignore($this->route('param')). Import use Illuminate\\Validation\\Rule; at the top.
- artifact=controller: When the model has FK fields in fillable (e.g. author_id, category_id), ALWAYS include them in $request->validated() passed to Model::create(). NEVER exclude FK fields or set them separately after create()."""

# ── EXAMPLES ─────────────────────────────────────────────────────────────────

EXAMPLES = []

def ex(spec: dict, php: str):
    EXAMPLES.append({"spec": spec, "php": php.strip()})


# ═══════════════════════════════════════════════════════════════════════════
# MODELS — plain (no relationships)
# ═══════════════════════════════════════════════════════════════════════════

ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Contact",
    "namespace": "App\\Models",
    "table": "contacts",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["name", "email", "phone", "message"],
    "casts": {},
    "relationships": [],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;

class Contact extends Model
{
    use HasFactory;

    protected $fillable = [
        'name',
        'email',
        'phone',
        'message',
    ];
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Setting",
    "namespace": "App\\Models",
    "table": "settings",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["key", "value", "group"],
    "casts": {},
    "relationships": [],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;

class Setting extends Model
{
    use HasFactory;

    protected $fillable = [
        'key',
        'value',
        'group',
    ];
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Product",
    "namespace": "App\\Models",
    "table": "products",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["name", "sku", "price", "stock", "category_id"],
    "casts": {"price": "decimal:2", "stock": "integer"},
    "relationships": [],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;

class Product extends Model
{
    use HasFactory;

    protected $fillable = [
        'name',
        'sku',
        'price',
        'stock',
        'category_id',
    ];

    protected function casts(): array
    {
        return [
            'price' => 'decimal:2',
            'stock' => 'integer',
        ];
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Invoice",
    "namespace": "App\\Models",
    "table": "invoices",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["number", "amount", "currency", "status", "customer_id", "due_at"],
    "casts": {"amount": "decimal:2", "due_at": "datetime"},
    "relationships": [],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;

class Invoice extends Model
{
    use HasFactory;

    protected $fillable = [
        'number',
        'amount',
        'currency',
        'status',
        'customer_id',
        'due_at',
    ];

    protected function casts(): array
    {
        return [
            'amount'  => 'decimal:2',
            'due_at'  => 'datetime',
        ];
    }
}
""")

ex({
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
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;

class Subscriber extends Model
{
    use HasFactory;

    protected $fillable = [
        'email',
        'name',
        'status',
        'subscribed_at',
    ];

    protected function casts(): array
    {
        return [
            'subscribed_at' => 'datetime',
            'status'        => 'string',
        ];
    }

    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }

    public function scopeUnsubscribed($query)
    {
        return $query->where('status', 'unsubscribed');
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Ticket",
    "namespace": "App\\Models",
    "table": "tickets",
    "has_factory": True,
    "soft_deletes": True,
    "fillable": ["subject", "body", "status", "user_id", "assigned_to"],
    "casts": {},
    "relationships": [],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\SoftDeletes;

class Ticket extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'subject',
        'body',
        'status',
        'user_id',
        'assigned_to',
    ];
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# MODELS — with relationships
# ═══════════════════════════════════════════════════════════════════════════

ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Review",
    "namespace": "App\\Models",
    "table": "reviews",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["rating", "body", "product_id"],
    "casts": {"rating": "integer"},
    "relationships": [
        {"type": "BelongsTo", "method": "product", "related": "Product"}
    ],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsTo;

class Review extends Model
{
    use HasFactory;

    protected $fillable = [
        'rating',
        'body',
        'product_id',
    ];

    protected function casts(): array
    {
        return [
            'rating' => 'integer',
        ];
    }

    public function product(): BelongsTo
    {
        return $this->belongsTo(Product::class);
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "OrderItem",
    "namespace": "App\\Models",
    "table": "order_items",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["order_id", "product_id", "qty", "price"],
    "casts": {"qty": "integer", "price": "decimal:2"},
    "relationships": [
        {"type": "BelongsTo", "method": "order", "related": "Order"}
    ],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsTo;

class OrderItem extends Model
{
    use HasFactory;

    protected $fillable = [
        'order_id',
        'product_id',
        'qty',
        'price',
    ];

    protected function casts(): array
    {
        return [
            'qty'   => 'integer',
            'price' => 'decimal:2',
        ];
    }

    public function order(): BelongsTo
    {
        return $this->belongsTo(Order::class);
    }
}
""")

ex({
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
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\HasMany;

class Author extends Model
{
    use HasFactory;

    protected $fillable = [
        'name',
        'bio',
        'nationality',
    ];

    public function books(): HasMany
    {
        return $this->hasMany(Book::class);
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Book",
    "namespace": "App\\Models",
    "table": "books",
    "has_factory": True,
    "soft_deletes": True,
    "fillable": ["title", "isbn", "description", "author_id", "published_year"],
    "casts": {"published_year": "integer"},
    "relationships": [
        {"type": "BelongsTo", "method": "author", "related": "Author"}
    ],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsTo;
use Illuminate\\Database\\Eloquent\\SoftDeletes;

class Book extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'title',
        'isbn',
        'description',
        'author_id',
        'published_year',
    ];

    protected function casts(): array
    {
        return [
            'published_year' => 'integer',
        ];
    }

    public function author(): BelongsTo
    {
        return $this->belongsTo(Author::class);
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Post",
    "namespace": "App\\Models",
    "table": "posts",
    "has_factory": True,
    "soft_deletes": True,
    "fillable": ["title", "body", "status", "user_id", "category_id"],
    "casts": {},
    "relationships": [
        {"type": "BelongsTo", "method": "user", "related": "User"},
        {"type": "BelongsTo", "method": "category", "related": "Category"},
        {"type": "HasMany", "method": "comments", "related": "Comment"}
    ],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsTo;
use Illuminate\\Database\\Eloquent\\Relations\\HasMany;
use Illuminate\\Database\\Eloquent\\SoftDeletes;

class Post extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'title',
        'body',
        'status',
        'user_id',
        'category_id',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function category(): BelongsTo
    {
        return $this->belongsTo(Category::class);
    }

    public function comments(): HasMany
    {
        return $this->hasMany(Comment::class);
    }
}
""")

ex({
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
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsTo;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsToMany;
use Illuminate\\Database\\Eloquent\\SoftDeletes;

class Event extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'title',
        'description',
        'venue_id',
        'event_date',
        'status',
    ];

    protected function casts(): array
    {
        return [
            'event_date' => 'datetime',
            'status'     => 'string',
        ];
    }

    public function venue(): BelongsTo
    {
        return $this->belongsTo(Venue::class);
    }

    public function speakers(): BelongsToMany
    {
        return $this->belongsToMany(Speaker::class);
    }
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# MIGRATIONS
# ═══════════════════════════════════════════════════════════════════════════

ex({
    "laravel_version": "13.x",
    "artifact": "migration",
    "operation": "create",
    "table": "contacts",
    "columns": [
        {"name": "name", "type": "string"},
        {"name": "email", "type": "string", "unique": True},
        {"name": "phone", "type": "string", "nullable": True},
        {"name": "message", "type": "text", "nullable": True}
    ],
    "timestamps": True,
    "soft_deletes": False
}, """
<?php
use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('contacts', function (Blueprint $table) {
            $table->id();
            $table->string('name');
            $table->string('email')->unique();
            $table->string('phone')->nullable();
            $table->text('message')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('contacts');
    }
};
""")

ex({
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
}, """
<?php
use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('subscribers', function (Blueprint $table) {
            $table->id();
            $table->string('email')->unique();
            $table->string('name');
            $table->string('status')->default('active');
            $table->timestamp('subscribed_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('subscribers');
    }
};
""")

ex({
    "laravel_version": "13.x",
    "artifact": "migration",
    "operation": "create",
    "table": "books",
    "columns": [
        {"name": "author_id", "type": "foreignId", "constrained": "authors", "on_delete": "cascade"},
        {"name": "title", "type": "string"},
        {"name": "isbn", "type": "string", "unique": True, "length": 20},
        {"name": "description", "type": "text", "nullable": True},
        {"name": "published_year", "type": "integer", "nullable": True}
    ],
    "timestamps": True,
    "soft_deletes": True
}, """
<?php
use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('books', function (Blueprint $table) {
            $table->id();
            $table->foreignId('author_id')->constrained()->cascadeOnDelete();
            $table->string('title');
            $table->string('isbn', 20)->unique();
            $table->text('description')->nullable();
            $table->integer('published_year')->nullable();
            $table->softDeletes();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('books');
    }
};
""")

ex({
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
}, """
<?php
use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('event_speaker', function (Blueprint $table) {
            $table->foreignId('event_id')->constrained()->cascadeOnDelete();
            $table->foreignId('speaker_id')->constrained()->cascadeOnDelete();
            $table->primary(['event_id', 'speaker_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('event_speaker');
    }
};
""")

# ═══════════════════════════════════════════════════════════════════════════
# FORM REQUESTS
# ═══════════════════════════════════════════════════════════════════════════

ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreSubscriberRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "email": ["required", "email", "max:255", "unique:subscribers,email"],
        "name": ["required", "string", "max:255"],
        "status": ["required", "string", "in:active,unsubscribed"],
        "subscribed_at": ["nullable", "date"]
    },
    "unique_ignore_route_param": None
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;

class StoreSubscriberRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'email'         => ['required', 'email', 'max:255', 'unique:subscribers,email'],
            'name'          => ['required', 'string', 'max:255'],
            'status'        => ['required', 'string', 'in:active,unsubscribed'],
            'subscribed_at' => ['nullable', 'date'],
        ];
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreProductRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "name": ["required", "string", "max:255"],
        "sku": ["required", "string", "max:50", "unique:products,sku"],
        "price": ["required", "numeric", "min:0"],
        "stock": ["nullable", "integer", "min:0"],
        "category_id": ["required", "integer", "exists:categories,id"]
    },
    "unique_ignore_route_param": "product"
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;
use Illuminate\\Validation\\Rule;

class StoreProductRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'name'        => ['required', 'string', 'max:255'],
            'sku'         => ['required', 'string', 'max:50', Rule::unique('products', 'sku')->ignore($this->route('product'))],
            'price'       => ['required', 'numeric', 'min:0'],
            'stock'       => ['nullable', 'integer', 'min:0'],
            'category_id' => ['required', 'integer', 'exists:categories,id'],
        ];
    }
}
""")

ex({
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
        "published_year": ["nullable", "integer", "min:1000", "max:2100"]
    },
    "unique_ignore_route_param": "book"
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;
use Illuminate\\Validation\\Rule;

class StoreBookRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'title'          => ['required', 'string', 'max:255'],
            'isbn'           => ['required', 'string', 'max:20', Rule::unique('books', 'isbn')->ignore($this->route('book'))],
            'description'    => ['nullable', 'string'],
            'author_id'      => ['required', 'integer', 'exists:authors,id'],
            'published_year' => ['nullable', 'integer', 'min:1000', 'max:2100'],
        ];
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreEventRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "title": ["required", "string", "max:255"],
        "description": ["nullable", "string"],
        "venue_id": ["required_on_post", "integer", "exists:venues,id"],
        "event_date": ["required", "date", "after_now_on_post"],
        "status": ["nullable", "string", "in:draft,published,cancelled"],
        "speaker_ids": ["nullable", "array"],
        "speaker_ids.*": ["integer", "exists:speakers,id"]
    },
    "unique_ignore_route_param": None
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;

class StoreEventRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'title'         => ['required', 'string', 'max:255'],
            'description'   => ['nullable', 'string'],
            'venue_id'      => [$this->isMethod('POST') ? 'required' : 'sometimes', 'integer', 'exists:venues,id'],
            'event_date'    => ['required', 'date', $this->isMethod('POST') ? 'after:now' : 'sometimes'],
            'status'        => ['nullable', 'string', 'in:draft,published,cancelled'],
            'speaker_ids'   => ['nullable', 'array'],
            'speaker_ids.*' => ['integer', 'exists:speakers,id'],
        ];
    }
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# API RESOURCES
# ═══════════════════════════════════════════════════════════════════════════

ex({
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
}, """
<?php
namespace App\\Http\\Resources;

use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class SubscriberResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id'            => $this->id,
            'email'         => $this->email,
            'name'          => $this->name,
            'status'        => $this->status,
            'subscribed_at' => $this->whenNotNull($this->subscribed_at),
            'created_at'    => $this->created_at,
            'updated_at'    => $this->updated_at,
        ];
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "BookResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id", "source": "id"},
        {"key": "title", "source": "title"},
        {"key": "isbn", "source": "isbn"},
        {"key": "description", "source": "description", "modifier": "whenNotNull"},
        {"key": "published_year", "source": "published_year", "modifier": "whenNotNull"},
        {"key": "created_at", "source": "created_at"},
        {"key": "updated_at", "source": "updated_at"}
    ],
    "loaded_relations": [
        {"key": "author", "resource": "AuthorResource", "type": "make"}
    ]
}, """
<?php
namespace App\\Http\\Resources;

use App\\Http\\Resources\\AuthorResource;
use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class BookResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id'             => $this->id,
            'title'          => $this->title,
            'isbn'           => $this->isbn,
            'description'    => $this->whenNotNull($this->description),
            'published_year' => $this->whenNotNull($this->published_year),
            'author'         => AuthorResource::make($this->whenLoaded('author')),
            'created_at'     => $this->created_at,
            'updated_at'     => $this->updated_at,
        ];
    }
}
""")

ex({
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
        {"key": "books_count", "source": "books_count", "modifier": "whenCounted"}
    ]
}, """
<?php
namespace App\\Http\\Resources;

use App\\Http\\Resources\\BookResource;
use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class AuthorResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id'          => $this->id,
            'name'        => $this->name,
            'bio'         => $this->whenNotNull($this->bio),
            'nationality' => $this->whenNotNull($this->nationality),
            'books'       => BookResource::collection($this->whenLoaded('books')),
            'books_count' => $this->whenCounted('books'),
            'created_at'  => $this->created_at,
        ];
    }
}
""")

ex({
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
}, """
<?php
namespace App\\Http\\Resources;

use App\\Http\\Resources\\SpeakerResource;
use App\\Http\\Resources\\VenueResource;
use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class EventResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id'          => $this->id,
            'title'       => $this->title,
            'description' => $this->whenNotNull($this->description),
            'event_date'  => $this->event_date,
            'status'      => $this->status,
            'venue'       => VenueResource::make($this->whenLoaded('venue')),
            'speakers'    => SpeakerResource::collection($this->whenLoaded('speakers')),
            'created_at'  => $this->created_at,
        ];
    }
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# CONTROLLERS
# ═══════════════════════════════════════════════════════════════════════════

ex({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "SubscriberController",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Subscriber",
    "model_namespace": "App\\Models",
    "resource": "SubscriberResource",
    "form_request": "StoreSubscriberRequest",
    "actions": {
        "index": {
            "paginate": 15,
            "filters": [{"param": "status", "column": "status"}],
            "eager_load": []
        },
        "store": {"status_code": 201, "many_to_many": None},
        "show": {"eager_load": []},
        "update": {"many_to_many": None},
        "destroy": {"force_delete": False}
    }
}, """
<?php
namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Http\\Requests\\StoreSubscriberRequest;
use App\\Http\\Resources\\SubscriberResource;
use App\\Models\\Subscriber;
use Illuminate\\Http\\Request;

class SubscriberController extends Controller
{
    public function index(Request $request)
    {
        $subscribers = Subscriber::query()
            ->when($request->filled('status'), fn ($q) => $q->where('status', $request->input('status')))
            ->paginate(15);

        return SubscriberResource::collection($subscribers);
    }

    public function store(StoreSubscriberRequest $request)
    {
        $subscriber = Subscriber::create($request->validated());

        return response()->json(new SubscriberResource($subscriber), 201);
    }

    public function show(Subscriber $subscriber)
    {
        return new SubscriberResource($subscriber);
    }

    public function update(StoreSubscriberRequest $request, Subscriber $subscriber)
    {
        $subscriber->update($request->validated());

        return new SubscriberResource($subscriber);
    }

    public function destroy(Subscriber $subscriber)
    {
        $subscriber->delete();

        return response()->noContent();
    }
}
""")

ex({
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
}, """
<?php
namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Http\\Requests\\StoreBookRequest;
use App\\Http\\Resources\\BookResource;
use App\\Models\\Book;
use Illuminate\\Http\\Request;

class BookController extends Controller
{
    public function index(Request $request)
    {
        $books = Book::query()
            ->when($request->filled('status'), fn ($q) => $q->where('status', $request->input('status')))
            ->with('author')
            ->paginate(15);

        return BookResource::collection($books);
    }

    public function store(StoreBookRequest $request)
    {
        $book = Book::create($request->validated());

        return response()->json(new BookResource($book->load('author')), 201);
    }

    public function show(Book $book)
    {
        return new BookResource($book->load('author'));
    }

    public function update(StoreBookRequest $request, Book $book)
    {
        $book->update($request->validated());

        return new BookResource($book->load('author'));
    }

    public function destroy(Book $book)
    {
        $book->delete();

        return response()->noContent();
    }
}
""")

ex({
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
}, """
<?php
namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Http\\Requests\\StoreEventRequest;
use App\\Http\\Resources\\EventResource;
use App\\Models\\Event;
use Illuminate\\Http\\Request;

class EventController extends Controller
{
    public function index(Request $request)
    {
        $events = Event::query()
            ->when($request->filled('status'), fn ($q) => $q->where('status', $request->input('status')))
            ->with(['venue', 'speakers'])
            ->paginate(10);

        return EventResource::collection($events);
    }

    public function store(StoreEventRequest $request)
    {
        $data = collect($request->validated())->except(['speaker_ids'])->toArray();
        $event = Event::create($data);
        $event->speakers()->sync($request->input('speaker_ids', []));

        return response()->json(new EventResource($event->load(['venue', 'speakers'])), 201);
    }

    public function show(Event $event)
    {
        return new EventResource($event->load(['venue', 'speakers']));
    }

    public function update(StoreEventRequest $request, Event $event)
    {
        $data = collect($request->validated())->except(['speaker_ids'])->toArray();
        $event->update($data);
        $event->speakers()->sync($request->input('speaker_ids', []));

        return new EventResource($event->load(['venue', 'speakers']));
    }

    public function destroy(Event $event)
    {
        $event->delete();

        return response()->noContent();
    }
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# PEST TESTS
# ═══════════════════════════════════════════════════════════════════════════

ex({
    "laravel_version": "13.x",
    "artifact": "pest_test",
    "suite": "Feature",
    "class_under_test": "SubscriberController",
    "model": "Subscriber",
    "model_namespace": "App\\Models",
    "base_uri": "/api/subscribers",
    "test_cases": [
        {
            "name": "GET /api/subscribers returns paginated list",
            "method": "getJson",
            "uri": "/api/subscribers",
            "setup": {"factory_count": 3},
            "assertions": ["assertOk", {"assertJsonCount": [3, "data"]}]
        },
        {
            "name": "POST /api/subscribers creates a subscriber",
            "method": "postJson",
            "uri": "/api/subscribers",
            "body": {"email": "test@example.com", "name": "Test User", "status": "active"},
            "assertions": ["assertCreated", {"assertJsonPath": ["email", "test@example.com"]}]
        },
        {
            "name": "POST /api/subscribers rejects duplicate email",
            "method": "postJson",
            "uri": "/api/subscribers",
            "setup": {"existing": {"email": "dupe@example.com"}},
            "body": {"email": "dupe@example.com"},
            "assertions": ["assertUnprocessable", {"assertJsonValidationErrors": [["email"]]}]
        }
    ]
}, """
<?php
use App\\Models\\Subscriber;
use Illuminate\\Foundation\\Testing\\RefreshDatabase;

uses(RefreshDatabase::class);

test('GET /api/subscribers returns paginated list', function () {
    Subscriber::factory()->count(3)->create();
    $this->getJson('/api/subscribers')
        ->assertOk()
        ->assertJsonCount(3, 'data');
});

test('POST /api/subscribers creates a subscriber', function () {
    $this->postJson('/api/subscribers', [
        'email'  => 'test@example.com',
        'name'   => 'Test User',
        'status' => 'active',
    ])->assertCreated()
      ->assertJsonPath('email', 'test@example.com');
});

test('POST /api/subscribers rejects duplicate email', function () {
    Subscriber::factory()->create(['email' => 'dupe@example.com']);
    $this->postJson('/api/subscribers', ['email' => 'dupe@example.com'])
        ->assertUnprocessable()
        ->assertJsonValidationErrors(['email']);
});
""")

# ═══════════════════════════════════════════════════════════════════════════
# FORM REQUESTS — conditional_rules (NEW)
# ═══════════════════════════════════════════════════════════════════════════

# Example 1: Event FormRequest with conditional_rules (the canonical fix)
ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "Event",
    "namespace": "App\\Http\\Requests",
    "rules": {
        "title":         ["required", "string", "max:255"],
        "description":   ["nullable", "string"],
        "venue_id":      [],
        "event_date":    ["required", "date"],
        "status":        ["nullable", "string", "in:draft,published,cancelled"],
        "speaker_ids":   ["nullable", "array"],
        "speaker_ids.*": ["integer", "exists:speakers,id"],
    },
    "conditional_rules": {
        "venue_id": {
            "POST": ["required", "integer", "exists:venues,id"],
            "PUT":  ["sometimes", "integer", "exists:venues,id"],
        },
        "event_date": {
            "POST": ["after:now"],
        }
    }
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;

class StoreEventRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'title'          => ['required', 'string', 'max:255'],
            'description'    => ['nullable', 'string'],
            'venue_id'       => [$this->isMethod('POST') ? 'required' : 'sometimes', 'integer', 'exists:venues,id'],
            'event_date'     => ['required', 'date', ...$this->isMethod('POST') ? ['after:now'] : []],
            'status'         => ['nullable', 'string', 'in:draft,published,cancelled'],
            'speaker_ids'    => ['nullable', 'array'],
            'speaker_ids.*'  => ['integer', 'exists:speakers,id'],
        ];
    }
}
""")

# Example 2: Article FormRequest — published_at conditional
ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "Article",
    "namespace": "App\\Http\\Requests",
    "rules": {
        "title":        ["required", "string", "max:255"],
        "body":         ["required", "string"],
        "category_id":  [],
        "published_at": ["nullable", "date"],
        "slug":         [],
    },
    "conditional_rules": {
        "category_id": {
            "POST": ["required", "integer", "exists:categories,id"],
            "PUT":  ["sometimes", "integer", "exists:categories,id"],
        },
        "slug": {
            "POST": ["required", "string", "max:100", "unique:articles,slug"],
            "PUT":  ["sometimes", "string", "max:100"],
        },
    }
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;

class StoreArticleRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'title'        => ['required', 'string', 'max:255'],
            'body'         => ['required', 'string'],
            'category_id'  => [$this->isMethod('POST') ? 'required' : 'sometimes', 'integer', 'exists:categories,id'],
            'published_at' => ['nullable', 'date'],
            'slug'         => [$this->isMethod('POST') ? 'required' : 'sometimes', 'string', 'max:100', ...$this->isMethod('POST') ? ['unique:articles,slug'] : []],
        ];
    }
}
""")

# Example 3: Order FormRequest — shipping_address required on POST only
ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "Order",
    "namespace": "App\\Http\\Requests",
    "rules": {
        "customer_id":       [],
        "status":            ["required", "string", "in:pending,processing,shipped,delivered,cancelled"],
        "shipping_address":  [],
        "notes":             ["nullable", "string"],
        "items":             [],
        "items.*.product_id":["integer", "exists:products,id"],
        "items.*.quantity":  ["integer", "min:1"],
    },
    "conditional_rules": {
        "customer_id": {
            "POST": ["required", "integer", "exists:customers,id"],
            "PUT":  ["sometimes", "integer", "exists:customers,id"],
        },
        "shipping_address": {
            "POST": ["required", "string"],
            "PUT":  ["sometimes", "string"],
        },
        "items": {
            "POST": ["required", "array", "min:1"],
            "PUT":  ["sometimes", "array"],
        },
    }
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;

class StoreOrderRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'customer_id'        => [$this->isMethod('POST') ? 'required' : 'sometimes', 'integer', 'exists:customers,id'],
            'status'             => ['required', 'string', 'in:pending,processing,shipped,delivered,cancelled'],
            'shipping_address'   => [$this->isMethod('POST') ? 'required' : 'sometimes', 'string'],
            'notes'              => ['nullable', 'string'],
            'items'              => [$this->isMethod('POST') ? 'required' : 'sometimes', 'array', ...$this->isMethod('POST') ? ['min:1'] : []],
            'items.*.product_id' => ['integer', 'exists:products,id'],
            'items.*.quantity'   => ['integer', 'min:1'],
        ];
    }
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# CONTROLLERS — inline validation (validation_mode: inline)
# ═══════════════════════════════════════════════════════════════════════════

# Example 4: Author controller — inline validation, no FormRequest
ex({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "Author",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Author",
    "resource": "AuthorResource",
    "validation_mode": "inline",
    "eager_load": [],
    "paginate": 15,
    "store_rules": {
        "name":       ["required", "string", "max:255"],
        "email":      ["nullable", "email", "unique:authors,email"],
        "bio":        ["nullable", "string"],
        "birth_year": ["nullable", "integer", "min:1800", "max:2010"],
    },
    "update_rules": {
        "name":       ["sometimes", "string", "max:255"],
        "email":      ["nullable", "email", "unique:authors,email"],
        "bio":        ["nullable", "string"],
        "birth_year": ["nullable", "integer", "min:1800", "max:2010"],
    },
}, """
<?php
namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Http\\Resources\\AuthorResource;
use App\\Models\\Author;
use Illuminate\\Http\\Request;

class AuthorController extends Controller
{
    public function index(Request $request)
    {
        $authors = Author::query()->paginate(15);

        return AuthorResource::collection($authors);
    }

    public function store(Request $request)
    {
        $data = $request->validate([
            'name'       => ['required', 'string', 'max:255'],
            'email'      => ['nullable', 'email', 'unique:authors,email'],
            'bio'        => ['nullable', 'string'],
            'birth_year' => ['nullable', 'integer', 'min:1800', 'max:2010'],
        ]);

        $author = Author::create($data);

        return response()->json(new AuthorResource($author), 201);
    }

    public function show(Author $author)
    {
        return new AuthorResource($author);
    }

    public function update(Request $request, Author $author)
    {
        $data = $request->validate([
            'name'       => ['sometimes', 'string', 'max:255'],
            'email'      => ['nullable', 'email', 'unique:authors,email'],
            'bio'        => ['nullable', 'string'],
            'birth_year' => ['nullable', 'integer', 'min:1800', 'max:2010'],
        ]);

        $author->update($data);

        return new AuthorResource($author);
    }

    public function destroy(Author $author)
    {
        $author->delete();

        return response()->noContent();
    }
}
""")

# Example 5: Tag controller — inline validation, simple model, no relationships
ex({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "Tag",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Tag",
    "resource": "TagResource",
    "validation_mode": "inline",
    "eager_load": [],
    "paginate": 20,
    "store_rules": {
        "name":  ["required", "string", "max:100", "unique:tags,name"],
        "color": ["nullable", "string", "max:7"],
    },
    "update_rules": {
        "name":  ["sometimes", "string", "max:100"],
        "color": ["nullable", "string", "max:7"],
    },
}, """
<?php
namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Http\\Resources\\TagResource;
use App\\Models\\Tag;
use Illuminate\\Http\\Request;

class TagController extends Controller
{
    public function index(Request $request)
    {
        $tags = Tag::query()->paginate(20);

        return TagResource::collection($tags);
    }

    public function store(Request $request)
    {
        $data = $request->validate([
            'name'  => ['required', 'string', 'max:100', 'unique:tags,name'],
            'color' => ['nullable', 'string', 'max:7'],
        ]);

        $tag = Tag::create($data);

        return response()->json(new TagResource($tag), 201);
    }

    public function show(Tag $tag)
    {
        return new TagResource($tag);
    }

    public function update(Request $request, Tag $tag)
    {
        $data = $request->validate([
            'name'  => ['sometimes', 'string', 'max:100'],
            'color' => ['nullable', 'string', 'max:7'],
        ]);

        $tag->update($data);

        return new TagResource($tag);
    }

    public function destroy(Tag $tag)
    {
        $tag->delete();

        return response()->noContent();
    }
}
""")

# Example 6: Category controller — inline validation, with status filter
ex({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "Category",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Category",
    "resource": "CategoryResource",
    "validation_mode": "inline",
    "eager_load": [],
    "paginate": 20,
    "filters": ["status"],
    "store_rules": {
        "name":        ["required", "string", "max:255"],
        "description": ["nullable", "string"],
        "status":      ["required", "string", "in:active,inactive"],
        "parent_id":   ["nullable", "integer", "exists:categories,id"],
    },
    "update_rules": {
        "name":        ["sometimes", "string", "max:255"],
        "description": ["nullable", "string"],
        "status":      ["sometimes", "string", "in:active,inactive"],
        "parent_id":   ["nullable", "integer", "exists:categories,id"],
    },
}, """
<?php
namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Http\\Resources\\CategoryResource;
use App\\Models\\Category;
use Illuminate\\Http\\Request;

class CategoryController extends Controller
{
    public function index(Request $request)
    {
        $categories = Category::query()
            ->when($request->filled('status'), fn ($q) => $q->where('status', $request->input('status')))
            ->paginate(20);

        return CategoryResource::collection($categories);
    }

    public function store(Request $request)
    {
        $data = $request->validate([
            'name'        => ['required', 'string', 'max:255'],
            'description' => ['nullable', 'string'],
            'status'      => ['required', 'string', 'in:active,inactive'],
            'parent_id'   => ['nullable', 'integer', 'exists:categories,id'],
        ]);

        $category = Category::create($data);

        return response()->json(new CategoryResource($category), 201);
    }

    public function show(Category $category)
    {
        return new CategoryResource($category);
    }

    public function update(Request $request, Category $category)
    {
        $data = $request->validate([
            'name'        => ['sometimes', 'string', 'max:255'],
            'description' => ['nullable', 'string'],
            'status'      => ['sometimes', 'string', 'in:active,inactive'],
            'parent_id'   => ['nullable', 'integer', 'exists:categories,id'],
        ]);

        $category->update($data);

        return new CategoryResource($category);
    }

    public function destroy(Category $category)
    {
        $category->delete();

        return response()->noContent();
    }
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# CONTROLLERS — form_request + eager_load combinations
# ═══════════════════════════════════════════════════════════════════════════

# Example 7: ProductController with StoreProductRequest, status filter
ex({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "Product",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Product",
    "resource": "ProductResource",
    "form_request": "StoreProductRequest",
    "validation_mode": "form_request",
    "eager_load": ["category"],
    "paginate": 15,
    "filters": ["status", "category_id"],
}, """
<?php
namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Http\\Requests\\StoreProductRequest;
use App\\Http\\Resources\\ProductResource;
use App\\Models\\Product;
use Illuminate\\Http\\Request;

class ProductController extends Controller
{
    public function index(Request $request)
    {
        $products = Product::query()
            ->when($request->filled('status'), fn ($q) => $q->where('status', $request->input('status')))
            ->when($request->filled('category_id'), fn ($q) => $q->where('category_id', $request->input('category_id')))
            ->with('category')
            ->paginate(15);

        return ProductResource::collection($products);
    }

    public function store(StoreProductRequest $request)
    {
        $product = Product::create($request->validated());

        return response()->json(new ProductResource($product->load('category')), 201);
    }

    public function show(Product $product)
    {
        return new ProductResource($product->load('category'));
    }

    public function update(StoreProductRequest $request, Product $product)
    {
        $product->update($request->validated());

        return new ProductResource($product->load('category'));
    }

    public function destroy(Product $product)
    {
        $product->delete();

        return response()->noContent();
    }
}
""")

# Example 8: PostController with many-to-many tags, eager load author + tags
ex({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "Post",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Post",
    "resource": "PostResource",
    "form_request": "StorePostRequest",
    "validation_mode": "form_request",
    "eager_load": ["author", "tags"],
    "paginate": 10,
    "filters": ["status"],
    "many_to_many": {"relation": "tags", "input_key": "tag_ids"},
}, """
<?php
namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Http\\Requests\\StorePostRequest;
use App\\Http\\Resources\\PostResource;
use App\\Models\\Post;
use Illuminate\\Http\\Request;

class PostController extends Controller
{
    public function index(Request $request)
    {
        $posts = Post::query()
            ->when($request->filled('status'), fn ($q) => $q->where('status', $request->input('status')))
            ->with(['author', 'tags'])
            ->paginate(10);

        return PostResource::collection($posts);
    }

    public function store(StorePostRequest $request)
    {
        $data = collect($request->validated())->except(['tag_ids'])->toArray();
        $post = Post::create($data);
        $post->tags()->sync($request->input('tag_ids', []));

        return response()->json(new PostResource($post->load(['author', 'tags'])), 201);
    }

    public function show(Post $post)
    {
        return new PostResource($post->load(['author', 'tags']));
    }

    public function update(StorePostRequest $request, Post $post)
    {
        $data = collect($request->validated())->except(['tag_ids'])->toArray();
        $post->update($data);
        $post->tags()->sync($request->input('tag_ids', []));

        return new PostResource($post->load(['author', 'tags']));
    }

    public function destroy(Post $post)
    {
        $post->delete();

        return response()->noContent();
    }
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# MODELS — additional variety
# ═══════════════════════════════════════════════════════════════════════════

# Example 9: Article model — BelongsTo author + BelongsToMany tags + scopes
ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Article",
    "namespace": "App\\Models",
    "table": "articles",
    "has_factory": True,
    "soft_deletes": True,
    "fillable": ["title", "body", "slug", "status", "author_id", "published_at"],
    "casts": {"published_at": "datetime"},
    "relationships": [
        {"type": "BelongsTo", "model": "Author", "method": "author"},
        {"type": "BelongsToMany", "model": "Tag", "method": "tags", "table": "article_tag"},
    ],
    "scopes": [
        {"name": "published", "column": "status", "value": "published"},
    ]
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsTo;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsToMany;
use Illuminate\\Database\\Eloquent\\SoftDeletes;

class Article extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'title',
        'body',
        'slug',
        'status',
        'author_id',
        'published_at',
    ];

    protected $casts = [
        'published_at' => 'datetime',
    ];

    public function scopePublished($query)
    {
        return $query->where('status', 'published');
    }

    public function author(): BelongsTo
    {
        return $this->belongsTo(Author::class);
    }

    public function tags(): BelongsToMany
    {
        return $this->belongsToMany(Tag::class, 'article_tag');
    }
}
""")

# Example 10: Product model — BelongsTo category, no scopes, no soft deletes
ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Product",
    "namespace": "App\\Models",
    "table": "products",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["name", "sku", "price", "stock", "status", "category_id"],
    "casts": {"price": "decimal:2", "stock": "integer"},
    "relationships": [
        {"type": "BelongsTo", "model": "Category", "method": "category"},
    ],
    "scopes": []
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsTo;

class Product extends Model
{
    use HasFactory;

    protected $fillable = [
        'name',
        'sku',
        'price',
        'stock',
        'status',
        'category_id',
    ];

    protected $casts = [
        'price' => 'decimal:2',
        'stock' => 'integer',
    ];

    public function category(): BelongsTo
    {
        return $this->belongsTo(Category::class);
    }
}
""")

# Example 11: Post model — BelongsTo user, BelongsToMany tags, HasMany comments
ex({
    "laravel_version": "13.x",
    "artifact": "model",
    "class": "Post",
    "namespace": "App\\Models",
    "table": "posts",
    "has_factory": True,
    "soft_deletes": False,
    "fillable": ["title", "body", "slug", "status", "user_id"],
    "casts": {},
    "relationships": [
        {"type": "BelongsTo", "model": "User", "method": "author", "foreign_key": "user_id"},
        {"type": "BelongsToMany", "model": "Tag", "method": "tags"},
        {"type": "HasMany", "model": "Comment", "method": "comments"},
    ],
    "scopes": [
        {"name": "published", "column": "status", "value": "published"},
    ]
}, """
<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsTo;
use Illuminate\\Database\\Eloquent\\Relations\\BelongsToMany;
use Illuminate\\Database\\Eloquent\\Relations\\HasMany;

class Post extends Model
{
    use HasFactory;

    protected $fillable = [
        'title',
        'body',
        'slug',
        'status',
        'user_id',
    ];

    public function scopePublished($query)
    {
        return $query->where('status', 'published');
    }

    public function author(): BelongsTo
    {
        return $this->belongsTo(User::class, 'user_id');
    }

    public function tags(): BelongsToMany
    {
        return $this->belongsToMany(Tag::class);
    }

    public function comments(): HasMany
    {
        return $this->hasMany(Comment::class);
    }
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# PEST TESTS — conditional validation patterns
# ═══════════════════════════════════════════════════════════════════════════

# Example 12: Pest test for Event — tests conditional validation
ex({
    "laravel_version": "13.x",
    "artifact": "pest_test",
    "class": "Event",
    "namespace": "Tests\\Feature",
    "model": "App\\Models\\Event",
    "endpoints": [
        {"method": "GET",    "path": "/api/events",      "action": "index"},
        {"method": "POST",   "path": "/api/events",      "action": "store"},
        {"method": "GET",    "path": "/api/events/{id}", "action": "show"},
        {"method": "PUT",    "path": "/api/events/{id}", "action": "update"},
        {"method": "DELETE", "path": "/api/events/{id}", "action": "destroy"},
    ],
    "required_on_create": ["title", "event_date", "venue_id"],
    "optional_on_update": ["venue_id"],
}, """
<?php
use App\\Models\\Event;
use App\\Models\\Venue;
use App\\Models\\Speaker;

test('GET /api/events returns paginated list', function () {
    Event::factory()->count(3)->create();
    $this->getJson('/api/events')
        ->assertOk()
        ->assertJsonCount(3, 'data');
});

test('POST /api/events creates an event', function () {
    $venue = Venue::factory()->create();
    $this->postJson('/api/events', [
        'title'      => 'Test Event',
        'event_date' => now()->addDays(10)->toDateString(),
        'venue_id'   => $venue->id,
    ])->assertCreated()
      ->assertJsonPath('title', 'Test Event');
});

test('POST /api/events requires venue_id', function () {
    $this->postJson('/api/events', [
        'title'      => 'Test Event',
        'event_date' => now()->addDays(10)->toDateString(),
    ])->assertUnprocessable()
      ->assertJsonValidationErrors(['venue_id']);
});

test('PUT /api/events/:id venue_id is optional', function () {
    $event = Event::factory()->create();
    $this->putJson("/api/events/{$event->id}", [
        'title' => 'Updated Event',
    ])->assertOk()
      ->assertJsonPath('title', 'Updated Event');
});

test('DELETE /api/events/:id deletes the event', function () {
    $event = Event::factory()->create();
    $this->deleteJson("/api/events/{$event->id}")
        ->assertNoContent();
    $this->assertDatabaseMissing('events', ['id' => $event->id]);
});
""")

# Example 13: Pest test for Article — tests published scope + soft deletes
ex({
    "laravel_version": "13.x",
    "artifact": "pest_test",
    "class": "Article",
    "namespace": "Tests\\Feature",
    "model": "App\\Models\\Article",
    "endpoints": [
        {"method": "GET",    "path": "/api/articles",      "action": "index"},
        {"method": "POST",   "path": "/api/articles",      "action": "store"},
        {"method": "GET",    "path": "/api/articles/{id}", "action": "show"},
        {"method": "PUT",    "path": "/api/articles/{id}", "action": "update"},
        {"method": "DELETE", "path": "/api/articles/{id}", "action": "destroy"},
    ],
    "soft_deletes": True,
    "required_on_create": ["title", "body"],
}, """
<?php
use App\\Models\\Article;

test('GET /api/articles returns paginated list', function () {
    Article::factory()->count(3)->create();
    $this->getJson('/api/articles')
        ->assertOk()
        ->assertJsonCount(3, 'data');
});

test('POST /api/articles creates an article', function () {
    $this->postJson('/api/articles', [
        'title' => 'Test Article',
        'body'  => 'Article body content',
    ])->assertCreated()
      ->assertJsonPath('title', 'Test Article');
});

test('POST /api/articles requires title and body', function () {
    $this->postJson('/api/articles', [])
        ->assertUnprocessable()
        ->assertJsonValidationErrors(['title', 'body']);
});

test('GET /api/articles/:id shows article', function () {
    $article = Article::factory()->create();
    $this->getJson("/api/articles/{$article->id}")
        ->assertOk()
        ->assertJsonPath('id', $article->id);
});

test('DELETE /api/articles/:id soft deletes the article', function () {
    $article = Article::factory()->create();
    $this->deleteJson("/api/articles/{$article->id}")
        ->assertNoContent();
    $this->assertSoftDeleted('articles', ['id' => $article->id]);
});
""")

# Example 14: Pest test for Product — tests category filter + nested resource
ex({
    "laravel_version": "13.x",
    "artifact": "pest_test",
    "class": "Product",
    "namespace": "Tests\\Feature",
    "model": "App\\Models\\Product",
    "endpoints": [
        {"method": "GET",    "path": "/api/products",      "action": "index"},
        {"method": "POST",   "path": "/api/products",      "action": "store"},
        {"method": "GET",    "path": "/api/products/{id}", "action": "show"},
        {"method": "PUT",    "path": "/api/products/{id}", "action": "update"},
        {"method": "DELETE", "path": "/api/products/{id}", "action": "destroy"},
    ],
    "filters": ["status", "category_id"],
    "required_on_create": ["name", "sku", "price"],
}, """
<?php
use App\\Models\\Category;
use App\\Models\\Product;

test('GET /api/products returns paginated list', function () {
    Product::factory()->count(3)->create();
    $this->getJson('/api/products')
        ->assertOk()
        ->assertJsonCount(3, 'data');
});

test('GET /api/products filters by status', function () {
    Product::factory()->create(['status' => 'active']);
    Product::factory()->create(['status' => 'inactive']);
    $this->getJson('/api/products?status=active')
        ->assertOk()
        ->assertJsonCount(1, 'data');
});

test('POST /api/products creates a product', function () {
    $category = Category::factory()->create();
    $this->postJson('/api/products', [
        'name'        => 'Widget',
        'sku'         => 'WDG-001',
        'price'       => 9.99,
        'category_id' => $category->id,
    ])->assertCreated()
      ->assertJsonPath('name', 'Widget');
});

test('POST /api/products requires name, sku, price', function () {
    $this->postJson('/api/products', [])
        ->assertUnprocessable()
        ->assertJsonValidationErrors(['name', 'sku', 'price']);
});

test('DELETE /api/products/:id deletes the product', function () {
    $product = Product::factory()->create();
    $this->deleteJson("/api/products/{$product->id}")
        ->assertNoContent();
    $this->assertDatabaseMissing('products', ['id' => $product->id]);
});
""")

# Example 15: Pest test for Post with many-to-many tags
ex({
    "laravel_version": "13.x",
    "artifact": "pest_test",
    "class": "Post",
    "namespace": "Tests\\Feature",
    "model": "App\\Models\\Post",
    "endpoints": [
        {"method": "GET",    "path": "/api/posts",      "action": "index"},
        {"method": "POST",   "path": "/api/posts",      "action": "store"},
        {"method": "GET",    "path": "/api/posts/{id}", "action": "show"},
        {"method": "PUT",    "path": "/api/posts/{id}", "action": "update"},
        {"method": "DELETE", "path": "/api/posts/{id}", "action": "destroy"},
    ],
    "required_on_create": ["title", "body"],
    "many_to_many": {"relation": "tags", "input_key": "tag_ids"},
}, """
<?php
use App\\Models\\Post;
use App\\Models\\Tag;

test('GET /api/posts returns paginated list', function () {
    Post::factory()->count(3)->create();
    $this->getJson('/api/posts')
        ->assertOk()
        ->assertJsonCount(3, 'data');
});

test('POST /api/posts creates a post with tags', function () {
    $tags = Tag::factory()->count(2)->create();
    $this->postJson('/api/posts', [
        'title'   => 'Test Post',
        'body'    => 'Post body',
        'tag_ids' => $tags->pluck('id')->toArray(),
    ])->assertCreated()
      ->assertJsonPath('title', 'Test Post');
});

test('POST /api/posts requires title and body', function () {
    $this->postJson('/api/posts', [])
        ->assertUnprocessable()
        ->assertJsonValidationErrors(['title', 'body']);
});

test('PUT /api/posts/:id updates tags', function () {
    $post = Post::factory()->create();
    $tags = Tag::factory()->count(2)->create();
    $this->putJson("/api/posts/{$post->id}", [
        'title'   => 'Updated Post',
        'tag_ids' => $tags->pluck('id')->toArray(),
    ])->assertOk()
      ->assertJsonPath('title', 'Updated Post');
});

test('DELETE /api/posts/:id deletes the post', function () {
    $post = Post::factory()->create();
    $this->deleteJson("/api/posts/{$post->id}")
        ->assertNoContent();
    $this->assertDatabaseMissing('posts', ['id' => $post->id]);
});
""")

# ═══════════════════════════════════════════════════════════════════════════
# RESOURCES — cross-resource imports (targeted fix for cross_resource_import bug)
# Rule: every loaded_relations[].resource → must have `use App\Http\Resources\X;`
# These examples use diverse class-name pairs to train the import pattern broadly.
# ═══════════════════════════════════════════════════════════════════════════

# Ex 0: FormRequest with POST-only conditional rule (spread pattern, NOT ternary)
# Specifically teaches: "after:now" POST-only → spread, NOT ternary with 'after_now'
ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreMeetingRequest",
    "namespace": "App\\Http\\Requests",
    "rules": {
        "title":        ["required", "string", "max:255"],
        "meeting_date": ["required", "date"],
        "location":     ["nullable", "string", "max:255"],
        "room_id":      [],
    },
    "conditional_rules": {
        "room_id": {
            "POST": ["required", "integer", "exists:rooms,id"],
            "PUT":  ["sometimes", "integer", "exists:rooms,id"],
        },
        "meeting_date": {
            "POST": ["after:now"],
        },
    }
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;

class StoreMeetingRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'title'        => ['required', 'string', 'max:255'],
            'meeting_date' => ['required', 'date', ...$this->isMethod('POST') ? ['after:now'] : []],
            'location'     => ['nullable', 'string', 'max:255'],
            'room_id'      => [$this->isMethod('POST') ? 'required' : 'sometimes', 'integer', 'exists:rooms,id'],
        ];
    }
}
""")

# Ex A: PostResource loads AuthorResource (make) + TagResource (collection) — TWO imports
ex({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "PostResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id",         "source": "id"},
        {"key": "title",      "source": "title"},
        {"key": "body",       "source": "body"},
        {"key": "status",     "source": "status"},
        {"key": "created_at", "source": "created_at"},
    ],
    "loaded_relations": [
        {"key": "author", "resource": "AuthorResource", "type": "make"},
        {"key": "tags",   "resource": "TagResource",    "type": "collection"},
    ]
}, """
<?php
namespace App\\Http\\Resources;

use App\\Http\\Resources\\AuthorResource;
use App\\Http\\Resources\\TagResource;
use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class PostResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id'         => $this->id,
            'title'      => $this->title,
            'body'       => $this->body,
            'status'     => $this->status,
            'author'     => AuthorResource::make($this->whenLoaded('author')),
            'tags'       => TagResource::collection($this->whenLoaded('tags')),
            'created_at' => $this->created_at,
        ];
    }
}
""")

# Ex B: OrderResource loads CustomerResource (make) + OrderItemResource (collection)
ex({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "OrderResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id",           "source": "id"},
        {"key": "status",       "source": "status"},
        {"key": "total",        "source": "total"},
        {"key": "created_at",   "source": "created_at"},
    ],
    "loaded_relations": [
        {"key": "customer", "resource": "CustomerResource", "type": "make"},
        {"key": "items",    "resource": "OrderItemResource", "type": "collection"},
    ]
}, """
<?php
namespace App\\Http\\Resources;

use App\\Http\\Resources\\CustomerResource;
use App\\Http\\Resources\\OrderItemResource;
use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class OrderResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id'         => $this->id,
            'status'     => $this->status,
            'total'      => $this->total,
            'customer'   => CustomerResource::make($this->whenLoaded('customer')),
            'items'      => OrderItemResource::collection($this->whenLoaded('items')),
            'created_at' => $this->created_at,
        ];
    }
}
""")

# Ex C: InvoiceResource loads ClientResource (make) only — single cross-import
ex({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "InvoiceResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id",           "source": "id"},
        {"key": "invoice_no",   "source": "invoice_no"},
        {"key": "amount",       "source": "amount"},
        {"key": "due_date",     "source": "due_date"},
        {"key": "status",       "source": "status"},
        {"key": "created_at",   "source": "created_at"},
    ],
    "loaded_relations": [
        {"key": "client", "resource": "ClientResource", "type": "make"},
    ]
}, """
<?php
namespace App\\Http\\Resources;

use App\\Http\\Resources\\ClientResource;
use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class InvoiceResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id'         => $this->id,
            'invoice_no' => $this->invoice_no,
            'amount'     => $this->amount,
            'due_date'   => $this->due_date,
            'status'     => $this->status,
            'client'     => ClientResource::make($this->whenLoaded('client')),
            'created_at' => $this->created_at,
        ];
    }
}
""")

# Ex D: PlaylistResource loads TrackResource (collection) + UserResource (make)
ex({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "PlaylistResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id",           "source": "id"},
        {"key": "name",         "source": "name"},
        {"key": "description",  "source": "description", "modifier": "whenNotNull"},
        {"key": "tracks_count", "modifier": "whenCounted"},
        {"key": "created_at",   "source": "created_at"},
    ],
    "loaded_relations": [
        {"key": "tracks", "resource": "TrackResource", "type": "collection"},
        {"key": "owner",  "resource": "UserResource",  "type": "make"},
    ]
}, """
<?php
namespace App\\Http\\Resources;

use App\\Http\\Resources\\TrackResource;
use App\\Http\\Resources\\UserResource;
use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class PlaylistResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id'           => $this->id,
            'name'         => $this->name,
            'description'  => $this->whenNotNull($this->description),
            'tracks_count' => $this->whenCounted('tracks'),
            'tracks'       => TrackResource::collection($this->whenLoaded('tracks')),
            'owner'        => UserResource::make($this->whenLoaded('owner')),
            'created_at'   => $this->created_at,
        ];
    }
}
""")

# Ex E: ProjectResource loads TeamMemberResource (collection) + CategoryResource (make)
ex({
    "laravel_version": "13.x",
    "artifact": "resource",
    "class": "ProjectResource",
    "namespace": "App\\Http\\Resources",
    "fields": [
        {"key": "id",          "source": "id"},
        {"key": "name",        "source": "name"},
        {"key": "status",      "source": "status"},
        {"key": "deadline",    "source": "deadline", "modifier": "whenNotNull"},
        {"key": "members_count", "modifier": "whenCounted"},
        {"key": "created_at",  "source": "created_at"},
    ],
    "loaded_relations": [
        {"key": "members",  "resource": "TeamMemberResource", "type": "collection"},
        {"key": "category", "resource": "CategoryResource",   "type": "make"},
    ]
}, """
<?php
namespace App\\Http\\Resources;

use App\\Http\\Resources\\CategoryResource;
use App\\Http\\Resources\\TeamMemberResource;
use Illuminate\\Http\\Request;
use Illuminate\\Http\\Resources\\Json\\JsonResource;

class ProjectResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id'             => $this->id,
            'name'           => $this->name,
            'status'         => $this->status,
            'deadline'       => $this->whenNotNull($this->deadline),
            'members_count'  => $this->whenCounted('members'),
            'members'        => TeamMemberResource::collection($this->whenLoaded('members')),
            'category'       => CategoryResource::make($this->whenLoaded('category')),
            'created_at'     => $this->created_at,
        ];
    }
}
""")

# ── v5: Rule::unique()->ignore() additional examples ─────────────────────

ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreUserRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "name": ["required", "string", "max:255"],
        "email": ["required", "email", "max:255", "unique:users,email"],
        "password": ["required", "string", "min:8"],
        "role": ["nullable", "string", "in:admin,editor,viewer"]
    },
    "unique_ignore_route_param": "user"
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;
use Illuminate\\Validation\\Rule;

class StoreUserRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'name'     => ['required', 'string', 'max:255'],
            'email'    => ['required', 'email', 'max:255', Rule::unique('users', 'email')->ignore($this->route('user'))],
            'password' => ['required', 'string', 'min:8'],
            'role'     => ['nullable', 'string', 'in:admin,editor,viewer'],
        ];
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreCategoryRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "name": ["required", "string", "max:255", "unique:categories,name"],
        "slug": ["required", "string", "max:255", "unique:categories,slug"],
        "description": ["nullable", "string"],
        "parent_id": ["nullable", "integer", "exists:categories,id"]
    },
    "unique_ignore_route_param": "category"
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;
use Illuminate\\Validation\\Rule;

class StoreCategoryRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'name'        => ['required', 'string', 'max:255', Rule::unique('categories', 'name')->ignore($this->route('category'))],
            'slug'        => ['required', 'string', 'max:255', Rule::unique('categories', 'slug')->ignore($this->route('category'))],
            'description' => ['nullable', 'string'],
            'parent_id'   => ['nullable', 'integer', 'exists:categories,id'],
        ];
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreArticleRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "title": ["required", "string", "max:255"],
        "slug": ["required", "string", "max:255", "unique:articles,slug"],
        "body": ["required", "string"],
        "status": ["nullable", "string", "in:draft,published,archived"],
        "category_id": ["required", "integer", "exists:categories,id"]
    },
    "unique_ignore_route_param": "article"
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;
use Illuminate\\Validation\\Rule;

class StoreArticleRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'title'       => ['required', 'string', 'max:255'],
            'slug'        => ['required', 'string', 'max:255', Rule::unique('articles', 'slug')->ignore($this->route('article'))],
            'body'        => ['required', 'string'],
            'status'      => ['nullable', 'string', 'in:draft,published,archived'],
            'category_id' => ['required', 'integer', 'exists:categories,id'],
        ];
    }
}
""")

# ── v5: FK-in-create controller examples ─────────────────────────────────

ex({
    "laravel_version": "13.x",
    "artifact": "controller",
    "class": "ReviewController",
    "namespace": "App\\Http\\Controllers\\Api",
    "model": "Review",
    "model_namespace": "App\\Models",
    "resource": "ReviewResource",
    "form_request": "StoreReviewRequest",
    "validation_mode": "form_request",
    "actions": {
        "index": {"paginate": 15, "eager_load": ["product"]},
        "store": {"status_code": 201, "eager_load_after": ["product"]},
        "show": {"eager_load": ["product"]},
        "update": {},
        "destroy": {"force_delete": False}
    }
}, """
<?php
namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Http\\Requests\\StoreReviewRequest;
use App\\Http\\Resources\\ReviewResource;
use App\\Models\\Review;
use Illuminate\\Http\\Request;

class ReviewController extends Controller
{
    public function index(Request $request)
    {
        $reviews = Review::query()
            ->with('product')
            ->paginate(15);

        return ReviewResource::collection($reviews);
    }

    public function store(StoreReviewRequest $request)
    {
        $review = Review::create($request->validated());

        return response()->json(new ReviewResource($review->load('product')), 201);
    }

    public function show(Review $review)
    {
        return new ReviewResource($review->load('product'));
    }

    public function update(StoreReviewRequest $request, Review $review)
    {
        $review->update($request->validated());

        return new ReviewResource($review);
    }

    public function destroy(Review $review)
    {
        $review->delete();

        return response()->noContent();
    }
}
""")

ex({
    "laravel_version": "13.x",
    "artifact": "form_request",
    "class": "StoreReviewRequest",
    "namespace": "App\\Http\\Requests",
    "authorize": True,
    "rules": {
        "product_id": ["required", "integer", "exists:products,id"],
        "rating": ["required", "integer", "min:1", "max:5"],
        "title": ["required", "string", "max:255"],
        "body": ["nullable", "string"]
    },
    "unique_ignore_route_param": None
}, """
<?php
namespace App\\Http\\Requests;

use Illuminate\\Foundation\\Http\\FormRequest;

class StoreReviewRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'product_id' => ['required', 'integer', 'exists:products,id'],
            'rating'     => ['required', 'integer', 'min:1', 'max:5'],
            'title'      => ['required', 'string', 'max:255'],
            'body'       => ['nullable', 'string'],
        ];
    }
}
""")

# ═══════════════════════════════════════════════════════════════════════════
# BUILD DATASET
# ═══════════════════════════════════════════════════════════════════════════

def build_dataset():
    os.makedirs("data_spec", exist_ok=True)

    random.seed(42)
    random.shuffle(EXAMPLES)

    split = max(1, len(EXAMPLES) // 10)
    valid_examples = EXAMPLES[:split]
    train_examples = EXAMPLES[split:]

    def to_jsonl(examples, path):
        with open(path, "w") as f:
            for ex in examples:
                spec_str = json.dumps(ex["spec"], indent=2)
                record = {
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": spec_str},
                        {"role": "assistant", "content": "<?php\n" + ex["php"].lstrip("<?php\n")}
                    ]
                }
                f.write(json.dumps(record) + "\n")
        return len(examples)

    n_train = to_jsonl(train_examples, "data_spec/train.jsonl")
    n_valid = to_jsonl(valid_examples, "data_spec/valid.jsonl")

    print(f"Spec training dataset: {n_train} train, {n_valid} valid")
    print(f"Artifacts: {', '.join(sorted(set(e['spec']['artifact'] for e in EXAMPLES)))}")

    # Token count estimate
    total_chars = sum(len(json.dumps(e["spec"])) + len(e["php"]) for e in EXAMPLES)
    est_tokens = total_chars // 4
    print(f"~{est_tokens} tokens total across {len(EXAMPLES)} examples (~{est_tokens//len(EXAMPLES)} avg)")


if __name__ == "__main__":
    build_dataset()
