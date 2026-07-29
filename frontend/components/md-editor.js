/**
 * <md-editor> — Split-pane markdown editor with live preview.
 *
 * Left pane: raw markdown textarea (plain, no framework, no bundler).
 * Right pane: live rendered HTML preview, updated debounced as you type.
 * Rendering is done server-side via /api/documents/render (pandoc).
 *
 * Attributes:
 *   path          - Document path (used for relative link resolution)
 *   branch        - Current branch name
 *   autosave      - Autosave interval in seconds (0 = off)
 *   readonly      - If present, hides editor pane (view-only mode)
 *
 * Properties:
 *   content       - Get/set the raw markdown string
 *
 * Events dispatched:
 *   content-change  — { detail: { content, path, branch } } — on each edit
 *   save-request    — { detail: { content, path, branch, message? } } — on Ctrl+S
 *   autosave        — { detail: { content, path, branch } } — on autosave timer
 */

import { debounce, escapeHtml, api } from "../lib/utils.js";

const STYLES = /* css */ `
  :host {
    display: flex;
    flex-direction: column;
    height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --editor-bg: var(--md-editor-bg, #ffffff);
    --editor-border: var(--md-border, #d0d7de);
  }

  /* ── Toolbar ── */
  .editor-toolbar {
    display: flex;
    align-items: center;
    gap: 0.5em;
    padding: 0.3em 0.6em;
    background: var(--md-code-bg, #f6f8fa);
    border-bottom: 1px solid var(--editor-border);
    font-size: 0.8em;
    flex-shrink: 0;
  }

  .editor-toolbar .path-label {
    font-weight: 600;
    color: var(--md-muted, #57606a);
    font-family: monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .editor-toolbar .view-toggle {
    display: flex;
    border: 1px solid var(--editor-border);
    border-radius: 4px;
    overflow: hidden;
  }

  .editor-toolbar .view-toggle button {
    padding: 2px 8px;
    border: none;
    background: none;
    cursor: pointer;
    font-size: inherit;
    font-family: inherit;
    color: var(--md-text, #24292f);
  }

  .editor-toolbar .view-toggle button.active {
    background: var(--md-link, #0969da);
    color: white;
  }

  .editor-toolbar .save-btn {
    padding: 2px 10px;
    border: 1px solid var(--md-link, #0969da);
    border-radius: 4px;
    background: var(--md-link, #0969da);
    color: white;
    cursor: pointer;
    font-size: inherit;
    font-family: inherit;
  }

  .editor-toolbar .save-btn:hover { background: #0860ca; }
  .editor-toolbar .save-btn.saving { opacity: 0.6; cursor: default; }

  .editor-toolbar .status {
    font-size: 0.85em;
    color: var(--md-muted, #57606a);
    white-space: nowrap;
  }

  .editor-toolbar .status.saved    { color: #1a7f37; }
  .editor-toolbar .status.modified { color: #9a6700; }
  .editor-toolbar .status.error    { color: #cf222e; }

  /* ── Split pane container ── */
  .pane-container {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* ── Editor pane ── */
  .editor-pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    border-right: 1px solid var(--editor-border);
  }

  textarea {
    flex: 1;
    resize: none;
    border: none;
    outline: none;
    padding: 1em;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 0.875em;
    line-height: 1.7;
    tab-size: 2;
    color: var(--md-text, #24292f);
    background: var(--editor-bg);
    word-wrap: break-word;
    overflow-wrap: break-word;
    white-space: pre-wrap;
    overflow-y: auto;
  }

  /* ── Preview pane ── */
  .preview-pane {
    flex: 1;
    overflow-y: auto;
    min-width: 0;
    background: var(--editor-bg);
  }

  .preview-inner {
    padding: 1.5em 2em;
    max-width: 760px;
    margin: 0 auto;
  }

  /* Loading skeleton */
  .preview-loading {
    padding: 2em;
    text-align: center;
    color: var(--md-muted, #57606a);
    font-size: 0.9em;
  }

  .preview-error {
    padding: 1em;
    background: #fff0f0;
    border-left: 3px solid #cf222e;
    color: #cf222e;
    font-family: monospace;
    font-size: 0.85em;
    margin: 1em;
    white-space: pre-wrap;
  }

  /* View mode classes */
  :host([layout="editor"]) .preview-pane { display: none; }
  :host([layout="editor"]) .editor-pane  { border-right: none; }
  :host([layout="preview"]) .editor-pane { display: none; }
  :host([layout="preview"]) .preview-pane { border-left: none; }
  :host([readonly]) .editor-pane { display: none; }
  :host([readonly]) .preview-pane { flex: 1; }
`;

class MdEditor extends HTMLElement {
  static get observedAttributes() {
    return ["path", "branch", "autosave", "readonly", "layout"];
  }

  constructor() {
    super();
    this._content = "";
    this._lastSaved = "";
    this._renderTimer = null;
    this._autosaveTimer = null;
    this._layout = "split";
    this.attachShadow({ mode: "open" });

    this._debouncedPreview = debounce(this._updatePreview.bind(this), 400);
  }

  set content(val) {
    this._content = val ?? "";
    this._lastSaved = this._content;
    const ta = this.shadowRoot?.querySelector("textarea");
    if (ta) ta.value = this._content;
    this._debouncedPreview();
  }

  get content() {
    return this.shadowRoot?.querySelector("textarea")?.value ?? this._content;
  }

  attributeChangedCallback(name, _, newVal) {
    if (name === "layout") this._layout = newVal || "split";
    if (name === "autosave") this._setupAutosave(parseInt(newVal || "0"));
    if (this.shadowRoot.childElementCount) this._render();
  }

  connectedCallback() {
    this._layout = this.getAttribute("layout") || "split";
    this._render();
    this._setupAutosave(parseInt(this.getAttribute("autosave") || "0"));
  }

  disconnectedCallback() {
    clearInterval(this._autosaveTimer);
  }

  _setupAutosave(intervalSecs) {
    clearInterval(this._autosaveTimer);
    if (intervalSecs > 0) {
      this._autosaveTimer = setInterval(() => {
        const current = this.content;
        if (current !== this._lastSaved) {
          this.dispatchEvent(new CustomEvent("autosave", {
            bubbles: true, composed: true,
            detail: {
              content: current,
              path: this.getAttribute("path"),
              branch: this.getAttribute("branch"),
            },
          }));
        }
      }, intervalSecs * 1000);
    }
  }

  _render() {
    const shadow = this.shadowRoot;
    shadow.innerHTML = "";

    const style = document.createElement("style");
    style.textContent = STYLES;
    shadow.appendChild(style);

    // ── Toolbar ────────────────────────────────────────────────────────────
    const toolbar = document.createElement("div");
    toolbar.className = "editor-toolbar";

    const pathLabel = document.createElement("span");
    pathLabel.className = "path-label";
    pathLabel.textContent = this.getAttribute("path") || "untitled.md";
    toolbar.appendChild(pathLabel);

    const statusEl = document.createElement("span");
    statusEl.className = "status";
    statusEl.textContent = "saved";
    toolbar.appendChild(statusEl);
    this._statusEl = statusEl;

    // Layout toggle
    const toggle = document.createElement("div");
    toggle.className = "view-toggle";
    [["editor", "✎"], ["split", "⊠"], ["preview", "👁"]].forEach(([mode, label]) => {
      const btn = document.createElement("button");
      btn.textContent = label;
      btn.title = mode;
      btn.setAttribute("aria-label", mode);
      if (mode === this._layout) btn.classList.add("active");
      btn.addEventListener("click", () => {
        this._layout = mode;
        this.setAttribute("layout", mode);
        shadow.querySelectorAll(".view-toggle button")
          .forEach(b => b.classList.toggle("active", b.title === mode));
      });
      toggle.appendChild(btn);
    });
    toolbar.appendChild(toggle);

    if (!this.hasAttribute("readonly")) {
      const saveBtn = document.createElement("button");
      saveBtn.className = "save-btn";
      saveBtn.textContent = "Save";
      saveBtn.addEventListener("click", () => this._requestSave());
      toolbar.appendChild(saveBtn);
      this._saveBtn = saveBtn;
    }

    shadow.appendChild(toolbar);

    // ── Pane container ─────────────────────────────────────────────────────
    const panes = document.createElement("div");
    panes.className = "pane-container";

    // Editor pane
    const editorPane = document.createElement("div");
    editorPane.className = "editor-pane";
    const ta = document.createElement("textarea");
    ta.value = this._content;
    ta.setAttribute("spellcheck", "true");
    ta.setAttribute("aria-label", "Markdown editor");
    ta.addEventListener("input", () => this._onInput(ta));
    ta.addEventListener("keydown", (e) => this._onKeydown(e));
    editorPane.appendChild(ta);
    panes.appendChild(editorPane);

    // Preview pane
    const previewPane = document.createElement("div");
    previewPane.className = "preview-pane";
    const previewInner = document.createElement("div");
    previewInner.className = "preview-inner";
    previewInner.innerHTML = '<div class="preview-loading">Loading preview…</div>';
    previewPane.appendChild(previewInner);
    panes.appendChild(previewPane);

    this._previewEl = previewInner;
    shadow.appendChild(panes);

    // Initial preview render
    if (this._content) this._updatePreview();
  }

  _onInput(ta) {
    const content = ta.value;
    this._markModified();
    this._debouncedPreview();
    this.dispatchEvent(new CustomEvent("content-change", {
      bubbles: true, composed: true,
      detail: {
        content,
        path: this.getAttribute("path"),
        branch: this.getAttribute("branch"),
      },
    }));
  }

  _onKeydown(e) {
    // Ctrl+S / Cmd+S → save
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      this._requestSave();
    }
    // Tab → indent with spaces
    if (e.key === "Tab") {
      e.preventDefault();
      const ta = e.target;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const spaces = "  ";
      ta.value = ta.value.slice(0, start) + spaces + ta.value.slice(end);
      ta.selectionStart = ta.selectionEnd = start + spaces.length;
    }
  }

  async _updatePreview() {
    if (!this._previewEl) return;
    const content = this.content;
    const path = this.getAttribute("path") || "document.md";

    try {
      const data = await api.post("/api/documents/render", { content, path });
      this._previewEl.innerHTML = data.html;

      // Re-register any custom elements emitted by pandoc in the preview
      this._previewEl.querySelectorAll("md-code-block, md-mermaid").forEach(el => {
        if (!el.shadowRoot) el.connectedCallback?.();
      });
    } catch (err) {
      this._previewEl.innerHTML =
        `<div class="preview-error">Preview error: ${escapeHtml(String(err))}</div>`;
    }
  }

  _requestSave() {
    if (this._saveBtn) {
      this._saveBtn.classList.add("saving");
      this._saveBtn.textContent = "Saving…";
    }
    this.dispatchEvent(new CustomEvent("save-request", {
      bubbles: true, composed: true,
      detail: {
        content: this.content,
        path: this.getAttribute("path"),
        branch: this.getAttribute("branch"),
      },
    }));
  }

  /** Called by the app shell when a save completes successfully. */
  markSaved() {
    this._lastSaved = this.content;
    if (this._saveBtn) {
      this._saveBtn.classList.remove("saving");
      this._saveBtn.textContent = "Save";
    }
    if (this._statusEl) {
      this._statusEl.className = "status saved";
      this._statusEl.textContent = "saved";
    }
  }

  /** Called by the app shell when a save fails. */
  markSaveError(message) {
    if (this._saveBtn) {
      this._saveBtn.classList.remove("saving");
      this._saveBtn.textContent = "Save";
    }
    if (this._statusEl) {
      this._statusEl.className = "status error";
      this._statusEl.textContent = `error: ${message}`;
    }
  }

  _markModified() {
    if (!this._statusEl) return;
    const current = this.content;
    const isModified = current !== this._lastSaved;
    this._statusEl.className = `status ${isModified ? "modified" : "saved"}`;
    this._statusEl.textContent = isModified ? "modified" : "saved";
  }
}

customElements.define("md-editor", MdEditor);
