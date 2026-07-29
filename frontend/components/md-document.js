/**
 * <md-document> — Top-level rendered document container.
 *
 * Wraps pandoc-generated HTML in a styled shadow root.
 * Provides baseline typography that intentionally mirrors GitHub/GitLab docs.
 *
 * Usage (inserted by pandoc template):
 *   <md-document>
 *     <!-- pandoc HTML body here -->
 *   </md-document>
 */

const STYLES = /* css */ `
  :host {
    display: block;
    max-width: 860px;
    margin: 0 auto;
    padding: 2rem 2.5rem;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    font-size: 16px;
    line-height: 1.65;
    color: var(--md-text, #24292f);
    background: var(--md-bg, #ffffff);
    -webkit-font-smoothing: antialiased;
  }

  /* Headings */
  ::slotted(h1), ::slotted(h2), ::slotted(h3),
  ::slotted(h4), ::slotted(h5), ::slotted(h6) {
    font-weight: 600;
    line-height: 1.25;
    margin-top: 1.8em;
    margin-bottom: 0.6em;
    color: var(--md-heading, #1a1a2e);
  }

  ::slotted(h1) { font-size: 2em;   border-bottom: 1px solid var(--md-border, #d0d7de); padding-bottom: 0.3em; }
  ::slotted(h2) { font-size: 1.5em; border-bottom: 1px solid var(--md-border, #d0d7de); padding-bottom: 0.3em; }
  ::slotted(h3) { font-size: 1.25em; }
  ::slotted(h4) { font-size: 1em; }
  ::slotted(h5) { font-size: 0.875em; }
  ::slotted(h6) { font-size: 0.85em; color: var(--md-muted, #57606a); }

  /* Paragraphs */
  ::slotted(p) {
    margin-top: 0;
    margin-bottom: 1em;
  }

  /* Links */
  ::slotted(a) {
    color: var(--md-link, #0969da);
    text-decoration: none;
  }
  ::slotted(a:hover) {
    text-decoration: underline;
  }

  /* Lists */
  ::slotted(ul), ::slotted(ol) {
    margin-top: 0;
    margin-bottom: 1em;
    padding-left: 2em;
  }

  /* Blockquote */
  ::slotted(blockquote) {
    margin: 0 0 1em;
    padding: 0 1em;
    color: var(--md-muted, #57606a);
    border-left: 4px solid var(--md-border, #d0d7de);
  }

  /* Tables */
  ::slotted(table) {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 1em;
    overflow: auto;
    display: block;
  }

  /* Horizontal rule */
  ::slotted(hr) {
    border: none;
    border-top: 1px solid var(--md-border, #d0d7de);
    margin: 2em 0;
  }

  /* Images */
  ::slotted(img) {
    max-width: 100%;
    height: auto;
  }
`;

class MdDocument extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;
    const shadow = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = STYLES;
    const slot = document.createElement("slot");
    shadow.appendChild(style);
    shadow.appendChild(slot);
  }
}

customElements.define("md-document", MdDocument);
