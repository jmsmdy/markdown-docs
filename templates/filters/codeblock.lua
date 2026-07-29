-- templates/filters/codeblock.lua
-- Pandoc Lua filter: converts fenced code blocks to web component elements.
--
-- ```mermaid       →  <md-mermaid>...</md-mermaid>
-- ```python        →  <md-code-block lang="python">...</md-code-block>
-- ``` (no lang)    →  <md-code-block>...</md-code-block>

function CodeBlock(el)
  local lang = ""
  if el.classes and #el.classes > 0 then
    lang = el.classes[1]
  end

  -- Escape HTML entities in the raw code
  local code = el.text
  code = code:gsub("&", "&amp;")
  code = code:gsub("<", "&lt;")
  code = code:gsub(">", "&gt;")

  if lang == "mermaid" then
    return pandoc.RawBlock("html",
      "<md-mermaid>" .. code .. "</md-mermaid>"
    )
  else
    local lang_attr = ""
    if lang ~= "" then
      lang_attr = ' lang="' .. lang .. '"'
    end
    return pandoc.RawBlock("html",
      "<md-code-block" .. lang_attr .. ">" .. code .. "</md-code-block>"
    )
  end
end
