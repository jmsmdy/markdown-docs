/**
 * <md-mermaid> — Mermaid diagram renderer.
 *
 * Mermaid.js is loaded lazily from CDN only when this component appears.
 * If loading fails, the raw diagram source is shown in a code block instead.
 *
 * Attributes:
 *   (none — diagram source is the text content / default slot)
 *
 * Usage (emitted by pandoc Lua filter for ```mermaid code blocks):
 *   <md-mermaid>graph TD; A-->B;</md-mermaid>
 */

const MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";

let mermaidModule = null;
let mermaidInitialized = false;
let mermaidLoadPromise = null;

async function getMermaid() {
  if (mermaidModule) return mermaidModule;
  if (mermaidLoadPromise) return mermaidLoadPromise;

  mermaidLoadPromise = import(MERMAID_CDN)
    .then((mod) => {
      mermaidModule = mod.default;
      if (!mermaidInitialized) {
        mermaidModule.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "loose",
        });
        mermaidInitialized = true;
      }
      return mermaidModule;
    })
    .catch(() => null);    // graceful fallback

  return mermaidLoadPromise;
}

let _diagramCounter = 0;

const STYLES = /* css */ `
  :host {
    display: block;
    margin: 1em 0;
    padding: 1em;
    background: var(--md-mermaid-bg, #fafbfc);
    border: 1px solid var(--md-border, #d0d7de);
    border-radius: 6px;
    overflow-x: auto;
    text-align: center;
  }

  .mermaid-error {
    font-family: monospace;
    font-size: 0.8em;
    color: var(--md-error, #cf222e);
    text-align: left;
    white-space: pre-wrap;
  }

  .mermaid-fallback pre {
    margin: 0;
    font-family: monospace;
    font-size: 0.8em;
    text-align: left;
    white-space: pre-wrap;
    color: var(--md-muted, #57606a);
  }

  svg {
    max-width: 100%;
    height: auto;
  }
`;

class MdMermaid extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;
    this._source = this.textContent.trim();
    this.attachShadow({ mode: "open" });
    this._render();
  }

  _render() {
    const shadow = this.shadowRoot;
    shadow.innerHTML = "";

    const style = document.createElement("style");
    style.textContent = STYLES;
    shadow.appendChild(style);

    const container = document.createElement("div");
    container.className = "mermaid-container";
    shadow.appendChild(container);

    this._renderDiagram(container);
  }

  async _renderDiagram(container) {
    const source = this._source;
    if (!source) return;

    const mermaid = await getMermaid();
    if (!mermaid) {
      // Fallback: show source in a code block
      container.innerHTML = `
        <div class="mermaid-fallback">
          <pre>${this._escapeHtml(source)}</pre>
        </div>`;
      return;
    }

    try {
      const id = `md-mermaid-${++_diagramCounter}`;
      const { svg } = await mermaid.render(id, source);
      container.innerHTML = svg;
    } catch (err) {
      container.innerHTML = `
        <div class="mermaid-error">⚠ Diagram error:\n${this._escapeHtml(String(err))}</div>
        <div class="mermaid-fallback"><pre>${this._escapeHtml(source)}</pre></div>`;
    }
  }

  _escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
}

customElements.define("md-mermaid", MdMermaid);
