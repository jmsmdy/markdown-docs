/**
 * <md-branch-bar> — Branch selector and status strip.
 *
 * Displays the current branch, lets users switch between doc branches,
 * create a new branch, and kick off a merge/review.
 *
 * Events dispatched:
 *   branch-switch  — { detail: { branch: string } }
 *   branch-create  — { detail: { name: string } }
 *   branch-merge   — { detail: { source: string, target: string } }
 *   branch-refresh — (no detail, requests a branch list reload)
 *
 * Properties:
 *   branches  - Array of BranchInfo objects from /api/branches
 *   current   - Current branch name string
 *   prefix    - Branch prefix string (e.g. "docs-")
 *   default   - Default/trunk branch name
 */

const STYLES = /* css */ `
  :host {
    display: flex;
    align-items: center;
    gap: 0.5em;
    padding: 0.4em 0.75em;
    background: var(--md-bar-bg, #f6f8fa);
    border-bottom: 1px solid var(--md-border, #d0d7de);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 0.85em;
    flex-wrap: wrap;
    min-height: 2.5em;
  }

  .icon { font-size: 1.1em; }

  select {
    padding: 0.2em 0.5em;
    border: 1px solid var(--md-border, #d0d7de);
    border-radius: 4px;
    background: var(--md-bg, #fff);
    font-size: inherit;
    font-family: inherit;
    color: var(--md-text, #24292f);
    cursor: pointer;
    max-width: 280px;
  }

  .badge {
    font-size: 0.75em;
    padding: 1px 6px;
    border-radius: 9px;
    font-weight: 600;
    white-space: nowrap;
  }

  .badge-doc  { background: #ddf4ff; color: #0969da; border: 1px solid #b6e3ff; }
  .badge-main { background: #dafbe1; color: #1a7f37; border: 1px solid #aceebb; }

  .ahead-behind {
    color: var(--md-muted, #57606a);
    font-size: 0.85em;
    white-space: nowrap;
  }

  .spacer { flex: 1; }

  .btn {
    padding: 0.2em 0.7em;
    border: 1px solid var(--md-border, #d0d7de);
    border-radius: 4px;
    background: var(--md-bg, #fff);
    font-size: inherit;
    font-family: inherit;
    cursor: pointer;
    color: var(--md-text, #24292f);
    white-space: nowrap;
    transition: background 0.1s;
  }

  .btn:hover { background: var(--md-code-bg, #f0f3f6); }

  .btn-primary {
    background: var(--md-link, #0969da);
    color: white;
    border-color: transparent;
  }

  .btn-primary:hover { background: #0860ca; }

  .btn-danger {
    color: var(--md-error, #cf222e);
    border-color: var(--md-error, #cf222e);
  }

  .btn-danger:hover { background: #fff0f0; }

  /* New branch dialog */
  .new-branch-form {
    display: flex;
    gap: 0.4em;
    align-items: center;
  }

  .new-branch-form input {
    padding: 0.2em 0.5em;
    border: 1px solid var(--md-border, #d0d7de);
    border-radius: 4px;
    font-size: inherit;
    font-family: inherit;
    width: 180px;
  }

  .prefix-hint {
    font-family: monospace;
    color: var(--md-muted, #57606a);
    font-size: 0.9em;
  }
`;

class MdBranchBar extends HTMLElement {
  constructor() {
    super();
    this._branches = [];
    this._current = "";
    this._prefix = "docs-";
    this._default = "main";
    this._showNewBranch = false;
    this.attachShadow({ mode: "open" });
  }

  set branches(val) { this._branches = val || []; this._render(); }
  set current(val)  { this._current = val || "";  this._render(); }
  set prefix(val)   { this._prefix = val || "docs-"; this._render(); }
  set default(val)  { this._default = val || "main"; this._render(); }

  get branches() { return this._branches; }
  get current()  { return this._current; }

  connectedCallback() { this._render(); }

  _render() {
    const shadow = this.shadowRoot;
    shadow.innerHTML = "";

    const style = document.createElement("style");
    style.textContent = STYLES;
    shadow.appendChild(style);

    // ── Branch icon ────────────────────────────────────────────────────────
    const icon = document.createElement("span");
    icon.className = "icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "⎇";
    shadow.appendChild(icon);

    // ── Branch select ──────────────────────────────────────────────────────
    const select = document.createElement("select");
    select.setAttribute("aria-label", "Current branch");

    const allBranches = this._branches.length
      ? this._branches
      : [{ name: this._current, is_doc_branch: false }];

    for (const b of allBranches) {
      const opt = document.createElement("option");
      opt.value = b.name;
      opt.textContent = b.name;
      if (b.name === this._current) opt.selected = true;
      select.appendChild(opt);
    }

    select.addEventListener("change", () => {
      const name = select.value;
      this.dispatchEvent(new CustomEvent("branch-switch", {
        bubbles: true, composed: true, detail: { branch: name },
      }));
    });

    shadow.appendChild(select);

    // ── Status badge ───────────────────────────────────────────────────────
    const isDoc = this._current.startsWith(this._prefix);
    if (isDoc) {
      const badge = document.createElement("span");
      badge.className = "badge badge-doc";
      badge.textContent = "doc branch";
      shadow.appendChild(badge);
    } else {
      const badge = document.createElement("span");
      badge.className = "badge badge-main";
      badge.textContent = this._current === this._default ? "main" : "branch";
      shadow.appendChild(badge);
    }

    // ── Ahead/behind ───────────────────────────────────────────────────────
    const curBranch = this._branches.find(b => b.name === this._current);
    if (curBranch && (curBranch.ahead > 0 || curBranch.behind > 0)) {
      const ab = document.createElement("span");
      ab.className = "ahead-behind";
      ab.textContent = `↑${curBranch.ahead} ↓${curBranch.behind}`;
      ab.title = `${curBranch.ahead} ahead, ${curBranch.behind} behind ${this._default}`;
      shadow.appendChild(ab);
    }

    // ── Spacer ─────────────────────────────────────────────────────────────
    const spacer = document.createElement("div");
    spacer.className = "spacer";
    shadow.appendChild(spacer);

    // ── Action buttons ─────────────────────────────────────────────────────
    if (this._showNewBranch) {
      this._appendNewBranchForm(shadow);
    } else {
      // New branch button
      const newBtn = document.createElement("button");
      newBtn.className = "btn";
      newBtn.textContent = "+ New branch";
      newBtn.addEventListener("click", () => {
        this._showNewBranch = true;
        this._render();
      });
      shadow.appendChild(newBtn);

      // Review & merge button (only for doc branches)
      if (isDoc) {
        const mergeBtn = document.createElement("button");
        mergeBtn.className = "btn btn-primary";
        mergeBtn.textContent = "Review & merge…";
        mergeBtn.addEventListener("click", () => {
          this.dispatchEvent(new CustomEvent("branch-merge", {
            bubbles: true, composed: true,
            detail: { source: this._current, target: this._default },
          }));
        });
        shadow.appendChild(mergeBtn);
      }
    }

    // ── Refresh button ─────────────────────────────────────────────────────
    const refreshBtn = document.createElement("button");
    refreshBtn.className = "btn";
    refreshBtn.setAttribute("aria-label", "Refresh branch list");
    refreshBtn.textContent = "↺";
    refreshBtn.addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("branch-refresh", {
        bubbles: true, composed: true,
      }));
    });
    shadow.appendChild(refreshBtn);
  }

  _appendNewBranchForm(shadow) {
    const form = document.createElement("div");
    form.className = "new-branch-form";

    const hint = document.createElement("span");
    hint.className = "prefix-hint";
    hint.textContent = this._prefix;
    form.appendChild(hint);

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "branch-name";
    input.setAttribute("aria-label", "New branch name (without prefix)");
    form.appendChild(input);

    const okBtn = document.createElement("button");
    okBtn.className = "btn btn-primary";
    okBtn.textContent = "Create";
    okBtn.addEventListener("click", () => {
      const name = input.value.trim();
      if (!name) return;
      this._showNewBranch = false;
      this.dispatchEvent(new CustomEvent("branch-create", {
        bubbles: true, composed: true, detail: { name },
      }));
    });

    const cancelBtn = document.createElement("button");
    cancelBtn.className = "btn";
    cancelBtn.textContent = "Cancel";
    cancelBtn.addEventListener("click", () => {
      this._showNewBranch = false;
      this._render();
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") okBtn.click();
      if (e.key === "Escape") cancelBtn.click();
    });

    form.appendChild(okBtn);
    form.appendChild(cancelBtn);
    shadow.appendChild(form);

    // Focus the input on next tick
    requestAnimationFrame(() => input.focus());
  }
}

customElements.define("md-branch-bar", MdBranchBar);
