import React from 'react';

// Sanitize link URLs to prevent XSS (javascript:, data:, vbscript:)
function sanitizeUrl(url) {
  if (!url) return null;
  const clean = url.trim().toLowerCase();
  if (clean.startsWith('https://') || clean.startsWith('http://') || clean.startsWith('/')) {
    return url.trim();
  }
  return null;
}

// Helper to render inline markdown: **bold**, *italic*, `code`, [link](url)
function renderInline(text) {
  if (!text) return null;

  // Split by inline markdown tokens: `code`, **bold**, *italic*, [link](url)
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\)|<br\s*\/?>)/g;
  const parts = text.split(regex);

  return parts.map((part, index) => {
    if (!part) return null;

    if (part === '<br>' || part === '<br/>' || part === '<br />') {
      return <br key={index} />;
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return (
        <code key={index} className="chat-inline-code">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      return (
        <strong key={index} className="chat-strong">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      return (
        <em key={index} className="chat-em">
          {part.slice(1, -1)}
        </em>
      );
    }
    // Markdown link: [label](url)
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      const label = linkMatch[1];
      const rawUrl = linkMatch[2];
      const safeHref = sanitizeUrl(rawUrl);
      if (safeHref) {
        return (
          <a
            key={index}
            href={safeHref}
            target="_blank"
            rel="noopener noreferrer"
            className="chat-link"
            style={{ color: 'var(--accent, #2563eb)', textDecoration: 'underline' }}
          >
            {label}
          </a>
        );
      }
      // If URL scheme is untrusted, render label as safe plain text
      return <span key={index}>{label}</span>;
    }
    return part;
  });
}

/**
 * MarkdownContent renders structured markdown content:
 * - Bold (**text**), Italics (*text*), Inline Code (`code`)
 * - Bullet lists (*, -) and Numbered lists (1., 2.)
 * - Tables (| col1 | col2 |)
 * - Blockquotes (> quote)
 * - Headings (###, ##, #)
 * - Clean paragraphs
 */

// Clean LaTeX / math artifacts (\text{}, \times, $$, &&, etc.) into clean plain-text formula formatting
function cleanFormulasAndLatex(text) {
  if (!text) return '';
  let cleaned = text;

  // Clean LaTeX environments: \begin{...}, \end{...}
  cleaned = cleaned.replace(/\\(begin|end)\{[a-zA-Z0-9_*]+\}/g, '');

  // Clean alignment markers &&, &, \\
  cleaned = cleaned.replace(/\s*&&\s*/g, ' ');
  cleaned = cleaned.replace(/\\\\\s*/g, '\n');

  // Clean \text{...} or /text{...}
  cleaned = cleaned.replace(/[/\\]text\{([^}]+)\}/g, '$1');

  // Math operators
  cleaned = cleaned.replace(/\\times\b/g, '×');
  cleaned = cleaned.replace(/\\cdot\b/g, '·');
  cleaned = cleaned.replace(/\\div\b/g, '÷');
  cleaned = cleaned.replace(/\\approx\b/g, '≈');
  cleaned = cleaned.replace(/\\le(q)?\b/g, '≤');
  cleaned = cleaned.replace(/\\ge(q)?\b/g, '≥');
  cleaned = cleaned.replace(/\\neq\b/g, '≠');
  cleaned = cleaned.replace(/\\min\b/g, 'min');
  cleaned = cleaned.replace(/\\max\b/g, 'max');

  // Strip math delimiters $$ ... $$ or $ ... $
  cleaned = cleaned.replace(/\$\$([\s\S]+?)\$\$/g, '$1');
  cleaned = cleaned.replace(/\$([^$\n]+?)\$/g, '$1');

  // Fractions: \frac{a}{b} -> (a / b)
  cleaned = cleaned.replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '($1 / $2)');

  // Always format currency as 'Rs. ' instead of rupee symbol
  cleaned = cleaned.replace(/[\u20B9₹]\s*/g, 'Rs. ');

  // Remove private-use unicode font bullet glyphs (e.g. \uf0b7, \uf0a7, ) from Word/PDF imports
  cleaned = cleaned.replace(/[\uf000-\uf0ff]/g, '');

  return cleaned;
}

export default function MarkdownContent({ content }) {
  if (!content) return null;

  const sanitizedContent = cleanFormulasAndLatex(content);
  const lines = sanitizedContent.split('\n');
  const elements = [];
  let i = 0;

  while (i < lines.length) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // 1. Skip empty lines
    if (!trimmed) {
      i++;
      continue;
    }

    // Horizontal rule (--- or ---...--- or ------------------------------------------------------------)
    if (/^[-*_]{3,}$/.test(trimmed)) {
      elements.push(<hr key={`hr-${i}`} className="chat-divider" />);
      i++;
      continue;
    }

    // 2. Blockquotes (> ...)
    if (trimmed.startsWith('>')) {
      const quoteLines = [];
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
        i++;
      }
      elements.push(
        <blockquote key={`quote-${i}`} className="chat-blockquote">
          {quoteLines.map((ql, qIdx) => (
            <p key={qIdx} style={{ margin: qIdx > 0 ? '4px 0 0 0' : 0 }}>
              {renderInline(ql)}
            </p>
          ))}
        </blockquote>
      );
      continue;
    }

    // 3. Headings (#, ##, ###)
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h5 key={`h3-${i}`} className="chat-heading-3">
          {renderInline(trimmed.slice(4))}
        </h5>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith('## ')) {
      elements.push(
        <h4 key={`h2-${i}`} className="chat-heading-2">
          {renderInline(trimmed.slice(3))}
        </h4>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith('# ')) {
      elements.push(
        <h3 key={`h1-${i}`} className="chat-heading-1">
          {renderInline(trimmed.slice(2))}
        </h3>
      );
      i++;
      continue;
    }

    // 4. Tables (| ... |)
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        tableLines.push(lines[i].trim());
        i++;
      }
      if (tableLines.length >= 2) {
        const headerRow = tableLines[0]
          .split('|')
          .slice(1, -1)
          .map((c) => c.trim());
        // Skip separator row (tableLines[1], e.g. |---|---|)
        const bodyRows = tableLines.slice(2).map((rowStr) =>
          rowStr
            .split('|')
            .slice(1, -1)
            .map((c) => c.trim())
        );

        elements.push(
          <div key={`table-${i}`} className="chat-table-wrapper">
            <table className="chat-table">
              <thead>
                <tr>
                  {headerRow.map((h, hIdx) => (
                    <th key={hIdx}>{renderInline(h)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bodyRows.map((row, rIdx) => (
                  <tr key={rIdx}>
                    {row.map((cell, cIdx) => (
                      <td key={cIdx}>{renderInline(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        continue;
      }
    }

    // 5. Unordered lists (*, -)
    if (/^[\*\-]\s+/.test(trimmed)) {
      const listItems = [];
      while (i < lines.length && /^[\*\-]\s+/.test(lines[i].trim())) {
        const itemText = lines[i].trim()
          .replace(/^[\*\-]\s+/, '')
          .replace(/^[\u2022\u25cf\u25aa\u25cb\u2023\u2043\u2219•▪▫▶►\s]+/, '');
        listItems.push(itemText);
        i++;
      }
      elements.push(
        <ul key={`ul-${i}`} className="chat-bullet-list">
          {listItems.map((item, idx) => (
            <li key={idx} className="chat-list-item">
              {renderInline(item)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // 6. Ordered lists (1., 2.)
    if (/^\d+\.\s+/.test(trimmed)) {
      const listItems = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        listItems.push(lines[i].trim().replace(/^\d+\.\s+/, ''));
        i++;
      }
      elements.push(
        <ol key={`ol-${i}`} className="chat-ordered-list">
          {listItems.map((item, idx) => (
            <li key={idx} className="chat-list-item">
              {renderInline(item)}
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // 7. Regular Paragraph
    const pLines = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith('>') &&
      !lines[i].trim().startsWith('#') &&
      !lines[i].trim().startsWith('|') &&
      !/^[\*\-]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim())
    ) {
      pLines.push(lines[i].trim());
      i++;
    }

    if (pLines.length > 0) {
      elements.push(
        <p key={`p-${i}`} className="chat-paragraph">
          {pLines.map((line, pIdx) => (
            <React.Fragment key={pIdx}>
              {pIdx > 0 && ' '}
              {renderInline(line)}
            </React.Fragment>
          ))}
        </p>
      );
    }
  }

  return <div className="chat-markdown-body">{elements}</div>;
}
