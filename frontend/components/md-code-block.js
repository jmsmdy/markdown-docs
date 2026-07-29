/**
 * <md-code-block> — Syntax-highlighted code block with copy button.
 *
 * Pandoc replaces <pre><code class="language-X"> with this element.
 * Highlight.js is loaded lazily from a CDN only when needed.
 *
 * Attributes:
 *   lang   - Language identifier (e.g. "python", "javascript")
 *
 * Slot:
 *   Default slot receives the raw code text.
 *
 * Usage (emitted by pandoc via Lua filter):
 *   <md-code-block lang="python">def hello(): pass</md-code-block>
 *
 * Fallback: if highlight.js fails to load, the code still renders
 * correctly in a <pre><code> block without syntax colors.
 */

const HLJS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js";
const HLJS_CSS_URL = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css";

let hljsPromise = null;
let hljsCssText = "";

function loadHljs() {
  if (hljsPromise) return hljsPromise;
  hljsPromise = Promise.all([
    // Load the JS
    new Promise((resolve) => {
      if (window.hljs) { resolve(window.hljs); return; }
      const script = document.createElement("script");
      script.src = HLJS_CDN;
      script.onload = () => resolve(window.hljs);
      script.onerror = () => resolve(null);
      document.head.appendChild(script);
    }),
    // Fetch the CSS text for shadow DOM injection
    fetch(HLJS_CSS_URL)
      .then(r => r.text())
      .catch(() => ""),
  ]).then(([hljs, css]) => {
    hljsCssText = css;
    return hljs;
  });
  return hljsPromise;
}

const STYLES = /* css */ `
  :host {
    display: block;
    margin: 1em 0;
    position: relative;
    border-radius: 6px;
    overflow: hidden;
    background: var(--md-code-bg, #f6f8fa);
    border: 1px solid var(--md-border, #d0d7de);
  }

  .lang-badge {
    position: absolute;
    top: 0.4em;
    left: 0.75em;
    font-size: 0.7em;
    font-family: monospace;
    color: var(--md-muted, #57606a);
    text-transform: lowercase;
    pointer-events: none;
    user-select: none;
  }

  .copy-btn {
    position: absolute;
    top: 0.4em;
    right: 0.5em;
    padding: 2px 8px;
    font-size: 0.7em;
    background: var(--md-bg, #ffffff);
    border: 1px solid var(--md-border, #d0d7de);
    border-radius: 4px;
    cursor: pointer;
    color: var(--md-muted, #57606a);
    opacity: 0;
    transition: opacity 0.15s;
    z-index: 2;
  }

  :host(:hover) .copy-btn {
    opacity: 1;
  }

  .copy-btn:active,
  .copy-btn.copied {
    background: var(--md-copy-ok, #dafbe1);
    color: #1a7f37;
    border-color: #82cb9a;
  }

  pre {
    margin: 0;
    padding: 1em 1em 1em 1em;
    overflow-x: auto;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 0.875em;
    line-height: 1.6;
    tab-size: 2;
  }

  code {
    background: none;
    padding: 0;
    font-family: inherit;
    font-size: inherit;
    white-space: pre;
  }

  /* Ensure hljs colors work inside shadow DOM */
  .hljs { background: transparent !important; }
`;

class MdCodeBlock extends HTMLElement {
  static get observedAttributes() { return ["lang"]; }

  connectedCallback() {
    if (this.shadowRoot) return;
    this._rawCode = this.textContent;
    this.attachShadow({ mode: "open" });
    this._render();
  }

  attributeChangedCallback() {
    if (this.shadowRoot) this._render();
  }

  _render() {
    const lang = (this.getAttribute("lang") || "").toLowerCase();
    const shadow = this.shadowRoot;
    shadow.innerHTML = "";

    // Styles
    const style = document.createElement("style");
    style.textContent = STYLES;
    shadow.appendChild(style);

    // Language badge
    if (lang) {
      const badge = document.createElement("span");
      badge.className = "lang-badge";
      badge.textContent = lang;
      shadow.appendChild(badge);
    }

    // Copy button
    const copyBtn = document.createElement("button");
    copyBtn.className = "copy-btn";
    copyBtn.setAttribute("aria-label", "Copy code");
    copyBtn.textContent = "copy";
    copyBtn.addEventListener("click", () => this._copy(copyBtn));
    shadow.appendChild(copyBtn);

    // Pre/code block
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    if (lang) code.className = `language-${lang}`;
    code.textContent = this._rawCode || this.textContent;
    pre.appendChild(code);
    shadow.appendChild(pre);

    // Async syntax highlighting
    this._highlight(code, lang);
  }

  async _highlight(codeEl, lang) {
    const hljs = await loadHljs();
    if (!hljs) return;

    // Inject hljs CSS into this shadow root (can't reach from document.head)
    const shadow = this.shadowRoot;
    if (hljsCssText && !shadow.querySelector("style[data-hljs]")) {
      const hljsStyle = document.createElement("style");
      hljsStyle.setAttribute("data-hljs", "");
      hljsStyle.textContent = hljsCssText;
      shadow.insertBefore(hljsStyle, shadow.firstChild);
    }

    try {
      if (lang && hljs.getLanguage(lang)) {
        const result = hljs.highlight(codeEl.textContent, { language: lang });
        codeEl.innerHTML = result.value;
      } else {
        hljs.highlightElement(codeEl);
      }
    } catch {
      // Highlight failure is non-fatal — code still displays as plain text
    }
  }

  async _copy(btn) {
    const text = this._rawCode || this.textContent;
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = "✓ copied";
      btn.classList.add("copied");
      setTimeout(() => {
        btn.textContent = "copy";
        btn.classList.remove("copied");
      }, 2000);
    } catch {
      btn.textContent = "error";
    }
  }
}

customElements.define("md-code-block", MdCodeBlock);
