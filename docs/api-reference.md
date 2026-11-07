# API Reference

The backend exposes a REST API at `/api/`. Interactive Swagger docs are available at `/api/docs` and ReDoc at `/api/redoc` when the server is running.

## Base URL

```
http://localhost:8000/api/
```

## Documents

### List Documents

```
GET /api/documents
```

Returns all markdown files in the configured docs directory.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `branch` | string (optional) | Branch to list from. Defaults to current branch. |

**Response:**

```json
{
  "documents": ["README.md", "guide/setup.md", "guide/usage.md"],
  "branch": "docs-my-edits"
}
```

---

### Get Document

```
GET /api/documents/{path}
```

Returns the raw markdown content of a document.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Relative path from docs_dir (e.g. `guide/setup.md`) |

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `branch` | string (optional) | Branch to read from |
| `render` | boolean (optional) | If true, also return rendered HTML |

**Response:**

```json
{
  "path": "guide/setup.md",
  "content": "# Setup\n\nFollow these steps...",
  "html": "<h1>Setup</h1><p>Follow these steps...</p>",
  "branch": "main",
  "commit_sha": "a1b2c3d4..."
}
```

The `html` field is only present when `render=true`.

---

### Save Document

```
PUT /api/documents/{path}
```

Writes content to the file and creates a git commit on the specified branch.

**Request Body:**

```json
{
  "path": "guide/setup.md",
  "content": "# Setup\n\nUpdated content...",
  "branch": "docs-my-edits",
  "commit_message": "docs: rewrite setup guide"
}
```

The `commit_message` is optional — defaults to `docs: update <path>`.

**Response:**

```json
{
  "path": "guide/setup.md",
  "branch": "docs-my-edits",
  "commit_sha": "e5f6a7b8...",
  "commit_message": "docs: rewrite setup guide"
}
```

---

### Render Markdown

```
POST /api/documents/render
```

Renders raw markdown to HTML without saving. Used by the live preview.

**Request Body:**

```json
{
  "content": "# Hello\n\nWorld",
  "path": "document.md"
}
```

The `path` is used for relative link resolution only.

**Response:**

```json
{
  "html": "<h1>Hello</h1>\n<p>World</p>",
  "path": "document.md"
}
```

---

## Branches

### List Branches

```
GET /api/branches
```

Returns all local branches with metadata.

**Response:**

```json
{
  "branches": [
    {
      "name": "docs-api-rewrite",
      "is_doc_branch": true,
      "is_current": true,
      "commit_sha": "a1b2c3d4...",
      "commit_message": "docs: update endpoints",
      "commit_date": "2025-01-15T10:30:00+00:00",
      "ahead": 3,
      "behind": 0
    },
    {
      "name": "main",
      "is_doc_branch": false,
      "is_current": false,
      "commit_sha": "e5f6a7b8...",
      "commit_message": "Initial commit",
      "commit_date": "2025-01-10T09:00:00+00:00",
      "ahead": 0,
      "behind": 0
    }
  ],
  "current": "docs-api-rewrite",
  "default": "main",
  "prefix": "docs-"
}
```

---

### Create Branch

```
POST /api/branches
```

Creates a new doc-edit branch.

**Request Body:**

```json
{
  "name": "api-rewrite",
  "base_branch": "main",
  "switch_to": true
}
```

- `name` — without the prefix (prefix is prepended automatically)
- `base_branch` — optional, defaults to the configured default branch
- `switch_to` — optional, defaults to true

**Response:**

```json
{
  "branch": "docs-api-rewrite",
  "base_commit": "e5f6a7b8..."
}
```

**Error (409):** Branch already exists.

---

### Switch Branch

```
POST /api/branches/{branch_name}/switch
```

Checks out an existing branch.

**Response:**

```json
{
  "current": "docs-api-rewrite"
}
```

---

### Merge Branch

```
POST /api/branches/{branch_name}/merge
```

Squash-merges a doc branch into the target branch.

**Request Body:**

```json
{
  "source_branch": "docs-api-rewrite",
  "target_branch": "main",
  "squash": true,
  "commit_message": "docs: merge api-rewrite"
}
```

**Response (success):**

```json
{
  "merged": true,
  "commit_sha": "f9a0b1c2...",
  "conflicts": []
}
```

**Response (failure):**

```json
{
  "merged": false,
  "commit_sha": null,
  "conflicts": ["No changes to merge"]
}
```

---

### List Branch Changes

```
GET /api/branches/{branch_name}/changes
```

Lists files changed on a branch relative to the default branch.

**Response:**

```json
{
  "branch": "docs-api-rewrite",
  "base": "main",
  "changed_files": ["api/endpoints.md", "api/models.md"]
}
```

---

## Diff

### Source Diff

```
POST /api/diff/source
```

Returns a unified text diff between two versions of a document.

**Request Body:**

```json
{
  "path": "guide/setup.md",
  "base_branch": "main",
  "compare_branch": "docs-my-edits"
}
```

Both branch fields are optional — defaults to the configured default branch and current branch respectively.

**Response:**

```json
{
  "path": "guide/setup.md",
  "base_branch": "main",
  "compare_branch": "docs-my-edits",
  "hunks": [
    {
      "old_start": 3,
      "old_lines": 5,
      "new_start": 3,
      "new_lines": 7,
      "content": " unchanged line\n-old line\n+new line\n+added line\n"
    }
  ],
  "old_content": "...",
  "new_content": "..."
}
```

---

### Rendered Diff

```
POST /api/diff/rendered
```

Returns a block+word level visual diff as structured HTML.

**Request Body:**

```json
{
  "path": "guide/setup.md",
  "base_branch": "main",
  "compare_branch": "docs-my-edits"
}
```

**Response:**

```json
{
  "path": "guide/setup.md",
  "base_branch": "main",
  "compare_branch": "docs-my-edits",
  "blocks": [
    {
      "kind": "unchanged",
      "old_html": "<h1>Setup</h1>",
      "new_html": "<h1>Setup</h1>",
      "diff_html": null
    },
    {
      "kind": "changed",
      "old_html": "<div class=\"md-diff-block ...\"><p>Old text</p></div>",
      "new_html": "<div class=\"md-diff-block ...\"><p>New text</p></div>",
      "diff_html": "<p><mark class=\"md-diff-removed\">Old</mark><mark class=\"md-diff-added\">New</mark> text</p>"
    },
    {
      "kind": "mermaid",
      "old_html": "<md-mermaid>graph TD\n    A-->B</md-mermaid>",
      "new_html": "<md-mermaid>graph TD\n    A-->B\n    A-->C</md-mermaid>",
      "diff_html": "<md-mermaid>graph TD\n    A[A]\n    B[B]\n    C[C]\n    A --> B\n    A --> C\n\n    style C fill:#c6efce,stroke:#27ae60,stroke-width:2px</md-mermaid>"
    }
  ],
  "mode": "both"
}
```

Block kinds:

| Kind | Description |
|------|-------------|
| `unchanged` | Block is identical in both versions |
| `added` | Block only exists in the new version |
| `removed` | Block only exists in the old version |
| `changed` | Block exists in both but content differs |
| `mermaid` | Mermaid diagram block (has special rendering) |

---

## Meta

### Health Check

```
GET /api/health
```

```json
{"status": "ok"}
```

### Server Configuration

```
GET /api/config
```

Returns the effective runtime configuration.

```json
{
  "repo_path": "/home/user/my-repo",
  "docs_dir": "docs",
  "branch_prefix": "docs-",
  "default_branch": "main",
  "diff_mode": "both"
}
```
