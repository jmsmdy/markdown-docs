/**
 * <md-diff-view> — Visual block+word-level diff viewer.
 *
 * Consumes the RenderedDiff JSON from /api/diff/rendered and displays it
 * as a side-by-side or inline view with:
 *   - Pale block highlight for changed/added/removed blocks
 *   - Darker word-level highlights within changed blocks
 *
 * Attributes:
 *   mode        - "side-by-side" (default) | "inline"
 *   base-label  - Label for old/left side (default: "Before")
 *   new-label   - Label for new/right side (default: "After")
 *
 * Properties:
 *   diff        - Set to a RenderedDiff object (from API)
 *
 * Usage:
 *   const view = document.createElement("md-diff-view");
 *   view.setAttribute("mode", "side-by-side");
 *   view.diff = await fetchDiff("/api/diff/rendered", { path: "README.md", ... });
 *   document.body.appendChild(view);
 */

const STYLES = /* css */ `
  :host {
    display: block;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    --color-added:    var(--md-diff-added,    rgba(0,   200, 80,  0.18));
    --color-removed:  var(--md-diff-removed,  rgba(220, 50,  50,  0.18));
    --color-block:    var(--md-diff-block,    rgba(255, 200, 0,   0.15));
    --color-word:     var(--md-diff-word,     rgba(255, 140, 0,   0.45));
    --color-border:   var(--md-border,        #d0d7de);
  }

  /* ── Header / toolbar ── */
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.4em 0.75em;
    background: var(--md-code-bg, #f6f8fa);
    border: 1px solid var(--color-border);
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    font-size: 0.8em;
    color: var(--md-muted, #57606a);
    gap: 1em;
  }

  .toolbar .labels {
    display: flex;
    gap: 1em;
    font-weight: 600;
  }

  .toolbar .label-base { color: var(--md-diff-removed-text, #cf222e); }
  .toolbar .label-new  { color: var(--md-diff-added-text,   #1a7f37); }

  .toolbar .toggle-group {
    display: flex;
    gap: 4px;
  }

  .toolbar button {
    padding: 2px 8px;
    font-size: 0.85em;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--md-bg, #fff);
    cursor: pointer;
    color: var(--md-text, #24292f);
  }

  .toolbar button.active {
    background: var(--md-link, #0969da);
    color: white;
    border-color: transparent;
  }

  /* ── Main diff container ── */
  .diff-body {
    border: 1px solid var(--color-border);
    border-radius: 0 0 6px 6px;
    overflow: hidden;
  }

  /* Side-by-side layout: gutter | left | gutter | right */
  .side-by-side .diff-row {
    display: grid;
    grid-template-columns: 2em 1fr 2em 1fr;
    border-bottom: 1px solid var(--color-border);
  }

  .side-by-side .diff-row:last-child { border-bottom: none; }

  .diff-cell {
    padding: 0.5em 0.75em;
    min-width: 0;
    overflow-x: auto;
  }

  /* Divider between old and new halves in side-by-side */
  .side-by-side .diff-cell:nth-child(3),
  .side-by-side .diff-cell:nth-child(4) {
    border-left: 1px solid var(--color-border);
  }

  /* Inline layout */
  .inline .diff-row {
    border-bottom: 1px solid var(--color-border);
  }

  .inline .diff-row:last-child { border-bottom: none; }

  .inline .diff-cell { padding: 0.5em 0.75em; }

  /* ── Block kinds ── */
  .diff-row.unchanged { background: var(--md-bg, #fff); }
  .diff-row.unchanged .diff-cell { color: var(--md-text, #24292f); }

  .diff-row.added     { background: var(--color-added); }
  .diff-row.removed   { background: var(--color-removed); }
  .diff-row.changed   { background: var(--color-block); }

  /* Word-level marks emitted by backend */
  .diff-cell mark.md-diff-added {
    background: var(--color-word);
    border-radius: 2px;
    padding: 0 1px;
  }

  .diff-cell mark.md-diff-removed {
    background: var(--color-removed);
    text-decoration: line-through;
    border-radius: 2px;
    padding: 0 1px;
    opacity: 0.85;
  }

  /* ── Content styles inside diff cells ── */
  /* Use * scoped under :host to ensure all cells get these styles
     regardless of nth-child position in the grid */
  table {
    display: table !important;
    border-collapse: collapse;
    width: 100%;
    font-size: 0.9em;
    margin: 0.25em 0;
  }

  th, td {
    display: table-cell !important;
    border: 1px solid var(--color-border);
    padding: 0.3em 0.6em;
    text-align: left;
  }

  tr     { display: table-row !important; }
  thead  { display: table-header-group !important; }
  tbody  { display: table-row-group !important; }

  thead tr {
    background: var(--md-code-bg, #f6f8fa);
    font-weight: 600;
  }

  tbody tr:nth-child(even) {
    background: rgba(0,0,0,0.02);
  }

  /* Inline code */
  code {
    background: var(--md-code-bg, #f6f8fa);
    border: 1px solid var(--color-border);
    border-radius: 3px;
    padding: 0.1em 0.35em;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 0.875em;
  }

  /* Blockquote */
  blockquote {
    margin: 0.25em 0;
    padding: 0 0.75em;
    border-left: 3px solid var(--color-border);
    color: var(--md-muted, #57606a);
  }

  /* Paragraphs and headings */
  p  { margin: 0.25em 0; }
  h1, h2, h3, h4, h5, h6 {
    margin: 0.25em 0;
    font-weight: 600;
    line-height: 1.3;
  }

  /* Lists */
  ul, ol {
    margin: 0.25em 0;
    padding-left: 1.5em;
  }

  /* Links */
  a { color: var(--md-link, #0969da); }

  /* Gutter indicators */
  .diff-cell.gutter {
    text-align: center;
    font-size: 0.85em;
    font-weight: bold;
    padding: 0.5em 0.25em;
    user-select: none;
    color: var(--md-muted, #57606a);
    border-right: 1px solid var(--color-border);
    background: var(--md-code-bg, #f6f8fa);
  }

  .diff-row.added   .gutter { color: #1a7f37; }
  .diff-row.removed .gutter { color: #cf222e; }
  .diff-row.changed .gutter { color: #9a6700; }

  /* Empty state */
  .empty {
    padding: 2em;
    text-align: center;
    color: var(--md-muted, #57606a);
    font-size: 0.9em;
  }

  /* Stats bar */
  .stats {
    font-size: 0.78em;
    color: var(--md-muted, #57606a);
  }

  .stats .added-count  { color: #1a7f37; font-weight: 600; }
  .stats .removed-count { color: #cf222e; font-weight: 600; }

  /* ── Mermaid diagram diff ── */
  .diff-row.mermaid {
    background: var(--color-block);
    border-bottom: 1px solid var(--color-border);
    padding: 0;
    display: block;
  }

  .side-by-side .diff-row.mermaid {
    grid-template-columns: 1fr;
    display: block;
  }

  .mermaid-diff-container {
    width: 100%;
  }

  .mermaid-diff-header {
    display: flex;
    align-items: center;
    gap: 0.5em;
    padding: 0.4em 0.75em;
    font-size: 0.8em;
    font-weight: 600;
    color: #9a6700;
    background: rgba(255, 200, 0, 0.08);
    border-bottom: 1px solid var(--color-border);
  }

  .mermaid-diff-icon {
    font-size: 0.9em;
  }

  .mermaid-diff-panes {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
  }

  .mermaid-diff-pane {
    padding: 0.5em;
    min-height: 80px;
    display: flex;
    flex-direction: column;
  }

  .mermaid-diff-old {
    border-right: 1px solid var(--color-border);
    background: rgba(220, 50, 50, 0.04);
  }

  .mermaid-diff-new {
    background: rgba(0, 200, 80, 0.04);
  }

  .mermaid-diff-empty {
    background: var(--md-code-bg, #f6f8fa);
    opacity: 0.6;
  }

  .mermaid-diff-label {
    font-size: 0.7em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.2em 0.5em;
    margin-bottom: 0.4em;
    color: var(--md-muted, #57606a);
  }

  .mermaid-diff-old .mermaid-diff-label { color: #cf222e; }
  .mermaid-diff-new .mermaid-diff-label { color: #1a7f37; }
  .mermaid-diff-empty .mermaid-diff-label {
    color: var(--md-muted, #57606a);
    font-style: italic;
    text-transform: none;
    letter-spacing: normal;
  }

  .mermaid-diff-content {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: auto;
  }

  .mermaid-diff-content md-mermaid {
    margin: 0;
    border: none;
    background: transparent;
    width: 100%;
  }

  /* Annotated (highlighted) diagram view */
  .mermaid-diff-annotated {
    padding: 1em;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: auto;
  }

  .mermaid-diff-annotated md-mermaid {
    margin: 0;
    border: none;
    background: transparent;
    width: 100%;
    max-width: 100%;
  }

  /* Toggle buttons in mermaid header */
  .mermaid-toggle-group {
    display: flex;
    gap: 4px;
    margin-left: auto;
  }

  .mermaid-toggle {
    padding: 2px 8px;
    font-size: 0.85em;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--md-bg, #fff);
    cursor: pointer;
    color: var(--md-text, #24292f);
  }

  .mermaid-toggle.active {
    background: #9a6700;
    color: white;
    border-color: transparent;
  }

  .mermaid-toggle:hover:not(.active) {
    background: var(--md-code-bg, #f6f8fa);
  }
`;

const GUTTER_SYMBOLS = {
  unchanged: " ",
  added:     "+",
  removed:   "−",
  changed:   "~",
  mermaid:   "◆",
};

class MdDiffView extends HTMLElement {
  static get observedAttributes() {
    return ["mode", "base-label", "new-label"];
  }

  constructor() {
    super();
    this._diff = null;
    this._mode = "side-by-side";
    this.attachShadow({ mode: "open" });
  }

  /** @param {Object} diff - RenderedDiff from the API */
  set diff(value) {
    this._diff = value;
    this._render();
  }

  get diff() { return this._diff; }

  attributeChangedCallback(name, _, newVal) {
    if (name === "mode") this._mode = newVal || "side-by-side";
    if (this.shadowRoot && this._diff) this._render();
  }

  connectedCallback() {
    this._mode = this.getAttribute("mode") || "side-by-side";
    this._render();
  }

  _render() {
    const shadow = this.shadowRoot;
    shadow.innerHTML = "";

    const style = document.createElement("style");
    style.textContent = STYLES;
    shadow.appendChild(style);

    if (!this._diff || !this._diff.blocks) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "No diff loaded.";
      shadow.appendChild(empty);
      return;
    }

    const blocks = this._diff.blocks;
    const addedCount   = blocks.filter(b => b.kind === "added"   || b.kind === "changed").length;
    const removedCount = blocks.filter(b => b.kind === "removed" || b.kind === "changed").length;

    // ── Toolbar ────────────────────────────────────────────────────────────
    const toolbar = document.createElement("div");
    toolbar.className = "toolbar";

    const labels = document.createElement("div");
    labels.className = "labels";
    labels.innerHTML = `
      <span class="label-base">− ${this.getAttribute("base-label") || "Before"}</span>
      <span class="label-new">+ ${this.getAttribute("new-label") || "After"}</span>
    `;

    const stats = document.createElement("span");
    stats.className = "stats";
    stats.innerHTML = `
      <span class="added-count">+${addedCount}</span> /
      <span class="removed-count">−${removedCount}</span> blocks changed
    `;

    const toggleGroup = document.createElement("div");
    toggleGroup.className = "toggle-group";
    ["side-by-side", "inline"].forEach(m => {
      const btn = document.createElement("button");
      btn.textContent = m.replace("-", " ");
      btn.dataset.mode = m;
      if (m === this._mode) btn.classList.add("active");
      btn.addEventListener("click", () => {
        this._mode = m;
        this.setAttribute("mode", m);
        this._render();
      });
      toggleGroup.appendChild(btn);
    });

    toolbar.appendChild(labels);
    toolbar.appendChild(stats);
    toolbar.appendChild(toggleGroup);
    shadow.appendChild(toolbar);

    // ── Diff body ──────────────────────────────────────────────────────────
    const body = document.createElement("div");
    body.className = `diff-body ${this._mode}`;

    for (const block of blocks) {
      body.appendChild(this._renderBlock(block));
    }

    shadow.appendChild(body);
  }

  _renderBlock(block) {
    const row = document.createElement("div");
    row.className = `diff-row ${block.kind}`;

    if (block.kind === "mermaid") {
      this._appendMermaidBlock(row, block);
    } else if (this._mode === "side-by-side") {
      this._appendCell(row, block, "left");
      this._appendCell(row, block, "right");
    } else {
      this._appendInline(row, block);
    }

    return row;
  }

  _appendCell(row, block, side) {
    const gutter = document.createElement("div");
    gutter.className = "diff-cell gutter";
    gutter.textContent = GUTTER_SYMBOLS[block.kind] || " ";

    const cell = document.createElement("div");
    cell.className = "diff-cell";

    let content = "";
    const { kind } = block;

    if (kind === "unchanged") {
      // Both sides show the same content
      content = block.new_html || block.old_html || "";
    } else if (kind === "added") {
      content = side === "right" ? (block.new_html || "") : "";
    } else if (kind === "removed") {
      content = side === "left" ? (block.old_html || "") : "";
    } else if (kind === "changed") {
      if (side === "left") {
        content = block.old_html || "";
      } else {
        // Right side: show word-level diff if available, otherwise new html
        content = block.diff_html || block.new_html || "";
      }
    }

    cell.innerHTML = content;
    row.appendChild(gutter);
    row.appendChild(cell);
  }

  _appendInline(row, block) {
    const gutter = document.createElement("div");
    gutter.className = "diff-cell gutter";
    gutter.textContent = GUTTER_SYMBOLS[block.kind] || " ";

    const cell = document.createElement("div");
    cell.className = "diff-cell";

    let content = "";
    if (block.kind === "unchanged") {
      content = block.new_html || block.old_html || "";
    } else if (block.kind === "added") {
      content = block.new_html || "";
    } else if (block.kind === "removed") {
      content = block.old_html || "";
    } else if (block.kind === "changed") {
      content = block.diff_html || block.new_html || "";
    }
    cell.innerHTML = content;

    row.appendChild(gutter);
    row.appendChild(cell);
  }

  /**
   * Render a mermaid diagram diff block.
   * If an annotated (structural diff) diagram is available, show it as the
   * primary view with a toggle to switch to side-by-side. Otherwise, fall
   * back to side-by-side only.
   */
  _appendMermaidBlock(row, block) {
    row.classList.add("mermaid-diff");

    const container = document.createElement("div");
    container.className = "mermaid-diff-container";

    const changeType = block.old_html && block.new_html ? "changed" : block.old_html ? "removed" : "added";
    const hasAnnotated = !!block.diff_html;

    // Header with toggle
    const header = document.createElement("div");
    header.className = "mermaid-diff-header";

    const title = document.createElement("span");
    title.innerHTML = `<span class="mermaid-diff-icon">◆</span> Diagram ${changeType}`;
    header.appendChild(title);

    // Toggle buttons (only if we have both views)
    if (hasAnnotated && block.old_html && block.new_html) {
      const toggleGroup = document.createElement("div");
      toggleGroup.className = "mermaid-toggle-group";

      const annotatedBtn = document.createElement("button");
      annotatedBtn.textContent = "Highlighted";
      annotatedBtn.className = "mermaid-toggle active";
      annotatedBtn.addEventListener("click", () => {
        annotatedView.style.display = "";
        sideBySideView.style.display = "none";
        annotatedBtn.classList.add("active");
        sideBySideBtn.classList.remove("active");
      });

      const sideBySideBtn = document.createElement("button");
      sideBySideBtn.textContent = "Side by side";
      sideBySideBtn.className = "mermaid-toggle";
      sideBySideBtn.addEventListener("click", () => {
        annotatedView.style.display = "none";
        sideBySideView.style.display = "";
        sideBySideBtn.classList.add("active");
        annotatedBtn.classList.remove("active");
      });

      toggleGroup.appendChild(annotatedBtn);
      toggleGroup.appendChild(sideBySideBtn);
      header.appendChild(toggleGroup);
    }

    container.appendChild(header);

    // Annotated view (primary) — single diagram with highlighted nodes/edges
    let annotatedView = null;
    if (hasAnnotated) {
      annotatedView = document.createElement("div");
      annotatedView.className = "mermaid-diff-annotated";
      annotatedView.innerHTML = block.diff_html;
      container.appendChild(annotatedView);
    }

    // Side-by-side view (secondary or fallback)
    let sideBySideView = document.createElement("div");
    sideBySideView.className = "mermaid-diff-panes";
    if (hasAnnotated) {
      sideBySideView.style.display = "none";
    }

    // Old (left) pane
    const leftPane = document.createElement("div");
    leftPane.className = `mermaid-diff-pane mermaid-diff-old${!block.old_html ? " mermaid-diff-empty" : ""}`;

    const leftLabel = document.createElement("div");
    leftLabel.className = "mermaid-diff-label";
    leftLabel.textContent = block.old_html ? "Before" : "(not present)";
    leftPane.appendChild(leftLabel);

    const leftContent = document.createElement("div");
    leftContent.className = "mermaid-diff-content";
    if (block.old_html) {
      leftContent.innerHTML = block.old_html;
    }
    leftPane.appendChild(leftContent);

    // New (right) pane
    const rightPane = document.createElement("div");
    rightPane.className = `mermaid-diff-pane mermaid-diff-new${!block.new_html ? " mermaid-diff-empty" : ""}`;

    const rightLabel = document.createElement("div");
    rightLabel.className = "mermaid-diff-label";
    rightLabel.textContent = block.new_html ? "After" : "(removed)";
    rightPane.appendChild(rightLabel);

    const rightContent = document.createElement("div");
    rightContent.className = "mermaid-diff-content";
    if (block.new_html) {
      rightContent.innerHTML = block.new_html;
    }
    rightPane.appendChild(rightContent);

    sideBySideView.appendChild(leftPane);
    sideBySideView.appendChild(rightPane);
    container.appendChild(sideBySideView);
    row.appendChild(container);
  }
}

customElements.define("md-diff-view", MdDiffView);
