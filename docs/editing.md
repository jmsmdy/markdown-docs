# Editing Documents

## The Editor Interface

The editor is a split-pane view:

- **Left pane** — raw markdown textarea
- **Right pane** — live rendered HTML preview (updated as you type, via pandoc)

A toolbar above the panes shows:

- The current file path
- Save status (`saved` / `modified` / `error`)
- Layout toggle (editor only / split / preview only)
- Save button

## Layout Modes

Toggle between three layouts using the toolbar buttons:

| Mode | Shows |
|------|-------|
| ✎ Editor | Raw markdown only |
| ⊠ Split | Side-by-side editor + preview (default) |
| 👁 Preview | Rendered preview only |

## Saving

### Manual Save

- Press **Ctrl+S** (or **Cmd+S** on macOS)
- Or click the **Save** button in the toolbar

Each save creates a git commit on the current branch with the message `docs: update <filename>`.

### Autosave

Autosave runs every 30 seconds by default (configurable via `editor.autosave_interval` in `markdown-docs.yaml`). It only triggers if the content has changed since the last save.

Autosave commits use the message `docs: autosave <filename>`.

Set `autosave_interval: 0` to disable autosave.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+S / Cmd+S | Save and commit |
| Tab | Insert 2 spaces (configurable via `editor.tab_size`) |
| Escape | Close the diff panel (when open) |

## Creating New Documents

1. Click the **+** button in the sidebar header.
2. Enter a filename (e.g. `my-doc.md` — the `.md` extension is added automatically if omitted).
3. If you're not on a doc branch, you'll be prompted to create one first.
4. The document is created with a default heading and opened in the editor.

## Live Preview

The preview pane renders your markdown server-side using pandoc. It supports:

- Headings, paragraphs, blockquotes
- Pipe tables (GFM-style)
- Task lists (`- [x] done`, `- [ ] todo`)
- Strikethrough (`~~text~~`)
- Fenced code blocks with syntax highlighting
- Mermaid diagrams (rendered client-side via mermaid.js)
- Inline HTML
- Emoji shortcodes (`:smile:`)

The preview updates ~400ms after you stop typing (debounced).

## Markdown Flavour

The editor uses pandoc with GitLab-Flavored Markdown extensions. This matches the markdown syntax supported by GitLab, GitHub, and most modern documentation tools. See [Configuration](configuration.md) for the full list of enabled extensions.

## Working with Other Tools

Since every document is a plain markdown file in a git repository, you can edit the same files with any tool:

- VS Code with a markdown extension
- Obsidian pointed at the repo
- vim, emacs, or any text editor
- Git CLI for commits and branches

All changes appear in markdown-docs the next time you switch to or refresh the relevant branch.
