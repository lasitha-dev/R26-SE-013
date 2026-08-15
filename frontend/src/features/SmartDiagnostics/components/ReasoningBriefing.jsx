import React, { useEffect, useState } from 'react';

/**
 * Section configuration — maps each of the 5 LLM briefing sections
 * to an icon and accent colour for visual differentiation.
 */
const SECTION_META = [
  { icon: 'verified', accent: 'border-primary', label: 'Diagnostic Assessment' },
  { icon: 'biotech', accent: 'border-secondary', label: 'Morphological Rationale' },
  { icon: 'compare_arrows', accent: 'border-tertiary', label: 'Differential Diagnosis' },
  { icon: 'shield', accent: 'border-error', label: 'Biosecurity Protocol' },
  { icon: 'science', accent: 'border-[#f59e0b]', label: 'Laboratory Tests' },
];

/**
 * Parse a lightweight subset of Markdown into React elements.
 * Handles: **bold**, ### sub-headings, - list items, and paragraphs.
 */
function parseMarkdownContent(text) {
  if (!text) return null;

  const lines = text.split('\n');
  const elements = [];
  let listItems = [];
  let key = 0;

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={key++} className="space-y-1.5 ml-1 mt-2">
          {listItems.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-on-surface-variant leading-relaxed">
              <span className="material-symbols-outlined text-primary text-[14px] shrink-0 mt-1">
                check_circle
              </span>
              <span dangerouslySetInnerHTML={{ __html: formatInline(item) }} />
            </li>
          ))}
        </ul>
      );
      listItems = [];
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      continue;
    }

    // Sub-headings (### or ####)
    if (trimmed.startsWith('###')) {
      flushList();
      const headingText = trimmed.replace(/^#+\s*/, '');
      elements.push(
        <h5
          key={key++}
          className="text-xs font-bold text-primary uppercase tracking-widest mt-4 mb-1"
          dangerouslySetInnerHTML={{ __html: formatInline(headingText) }}
        />
      );
      continue;
    }

    // List items
    if (/^\d+\.\s/.test(trimmed) || trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const content = trimmed.replace(/^(\d+\.\s|- |\* )/, '');
      listItems.push(content);
      continue;
    }

    // Indented sub-list items (e.g. "   - Specimen Type: ...")
    if (/^\s+[-*]\s/.test(line)) {
      const content = line.trim().replace(/^[-*]\s/, '');
      listItems.push(content);
      continue;
    }

    // Paragraph text
    flushList();
    elements.push(
      <p
        key={key++}
        className="text-sm text-on-surface-variant leading-relaxed mt-1"
        dangerouslySetInnerHTML={{ __html: formatInline(trimmed) }}
      />
    );
  }

  flushList();
  return elements;
}

/** Convert inline Markdown (**bold**, `code`) to HTML. */
function formatInline(text) {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-on-surface font-semibold">$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="text-primary bg-primary/10 px-1 py-0.5 rounded text-xs font-mono">$1</code>');
}

/**
 * Split the LLM Markdown report into its 5 sections by `## ` headings.
 * Returns an array of { title, content } objects.
 */
function splitSections(markdown) {
  if (!markdown) return [];

  const sections = [];
  const parts = markdown.split(/^## /m).filter(Boolean);

  for (const part of parts) {
    const newlineIdx = part.indexOf('\n');
    if (newlineIdx === -1) continue;

    const title = part.substring(0, newlineIdx).trim();
    const content = part.substring(newlineIdx + 1).trim();
    sections.push({ title, content });
  }

  return sections;
}


// ═══════════════════════════════════════════════════════════════════════════
// Loading Skeleton
// ═══════════════════════════════════════════════════════════════════════════

function LoadingSkeleton() {
  const [dots, setDots] = useState('');

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '' : prev + '.'));
    }, 500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4 animate-pulse">
      {/* Header skeleton */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-primary/10 rounded-lg">
          <span className="material-symbols-outlined text-primary animate-spin" style={{ animationDuration: '3s' }}>
            neurology
          </span>
        </div>
        <div>
          <p className="text-sm font-bold text-on-surface">
            Generating Clinical Briefing{dots}
          </p>
          <p className="text-xs text-on-surface-variant mt-0.5">
            Qwen 2.5 is synthesising the diagnostic report
          </p>
        </div>
      </div>

      {/* Skeleton cards */}
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="rounded-lg border border-outline-variant/10 p-4"
          style={{ opacity: 1 - i * 0.2 }}
        >
          <div className="h-3 w-1/3 bg-surface-container-highest rounded mb-3" />
          <div className="space-y-2">
            <div className="h-2.5 w-full bg-surface-container-highest/60 rounded" />
            <div className="h-2.5 w-5/6 bg-surface-container-highest/40 rounded" />
            <div className="h-2.5 w-2/3 bg-surface-container-highest/30 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════
// Error Fallback
// ═══════════════════════════════════════════════════════════════════════════

function ErrorFallback({ error }) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-lg bg-error/5 border border-error/20">
      <div className="p-2 bg-error/10 rounded-lg shrink-0">
        <span className="material-symbols-outlined text-error">cloud_off</span>
      </div>
      <div>
        <p className="text-sm font-bold text-on-surface mb-1">
          Clinical Reasoning Unavailable
        </p>
        <p className="text-xs text-on-surface-variant leading-relaxed mb-3">
          The LLM reasoning engine (LM Studio) could not be reached. The Tier 1 &amp; 2
          detection and classification results above remain fully valid.
        </p>
        {error && (
          <details className="text-xs text-on-surface-variant">
            <summary className="cursor-pointer hover:text-on-surface font-medium">
              Technical details
            </summary>
            <pre className="mt-2 p-2 bg-surface-container rounded text-[10px] overflow-x-auto whitespace-pre-wrap">
              {error}
            </pre>
          </details>
        )}
        <div className="mt-3 space-y-1">
          <p className="text-[11px] text-on-surface-variant font-medium">Troubleshooting:</p>
          <ul className="text-[11px] text-on-surface-variant space-y-0.5 ml-3 list-disc">
            <li>Verify LM Studio is running and the server is started</li>
            <li>Confirm a model is loaded (e.g. qwen2.5-vl-3b-instruct)</li>
            <li>Check the endpoint URL: http://127.0.0.1:1234/v1</li>
          </ul>
        </div>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════

/**
 * ReasoningBriefing — renders the Tier 3 LLM clinical diagnostic briefing.
 *
 * @param {object}  props
 * @param {string|null} props.reasoning       - Markdown report from the LLM
 * @param {string}      props.reasoningStatus - 'idle' | 'loading' | 'done' | 'error'
 * @param {string|null} props.reasoningError  - Error message if status === 'error'
 */
export default function ReasoningBriefing({ reasoning, reasoningStatus, reasoningError }) {
  const [visibleCards, setVisibleCards] = useState(0);

  // Parse sections from the Markdown report
  const sections = reasoningStatus === 'done' && reasoning ? splitSections(reasoning) : [];

  // Animate section cards appearing one by one
  useEffect(() => {
    if (reasoningStatus !== 'done' || sections.length === 0) {
      setVisibleCards(0);
      return;
    }

    const timers = [];
    for (let i = 1; i <= sections.length; i++) {
      const timer = setTimeout(() => setVisibleCards(i), i * 300);
      timers.push(timer);
    }
    return () => timers.forEach(clearTimeout);
  }, [reasoningStatus, sections.length]);

  // Don't render anything in idle state
  if (reasoningStatus === 'idle') return null;

  return (
    <div
      className="bg-surface-container-low rounded-xl p-4 md:p-8 border border-outline-variant/10 transition-all duration-700"
      data-testid="reasoning-briefing"
    >
      {/* Section header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-primary/10 rounded-lg">
          <span className="material-symbols-outlined text-primary">
            neurology
          </span>
        </div>
        <div>
          <h3 className="text-lg md:text-xl font-bold text-on-surface tracking-tight">
            AI Clinical Briefing
          </h3>
          <span className="text-[0.6875rem] font-bold text-primary tracking-widest uppercase">
            04 Tier 3 — LLM Reasoning Engine
          </span>
        </div>
      </div>

      {/* Loading state */}
      {reasoningStatus === 'loading' && <LoadingSkeleton />}

      {/* Error state */}
      {reasoningStatus === 'error' && <ErrorFallback error={reasoningError} />}

      {/* Success state — render section cards */}
      {reasoningStatus === 'done' && sections.length > 0 && (
        <div className="space-y-4">
          {sections.map((section, idx) => {
            const meta = SECTION_META[idx] || SECTION_META[0];
            return (
              <div
                key={idx}
                className={`
                  rounded-lg border-l-4 ${meta.accent} 
                  bg-surface-container/50 p-4 md:p-5
                  border border-outline-variant/5
                  transition-all duration-500
                  ${idx < visibleCards ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}
                `}
              >
                {/* Section heading */}
                <div className="flex items-center gap-2 mb-3">
                  <span className="material-symbols-outlined text-base text-primary">
                    {meta.icon}
                  </span>
                  <h4
                    className="text-sm font-bold text-on-surface"
                    dangerouslySetInnerHTML={{ __html: formatInline(section.title) }}
                  />
                </div>

                {/* Section content */}
                <div className="pl-7">
                  {parseMarkdownContent(section.content)}
                </div>
              </div>
            );
          })}

          {/* Footer */}
          <div className={`
            flex items-center gap-2 pt-3 border-t border-outline-variant/10
            transition-all duration-500 delay-300
            ${visibleCards >= sections.length ? 'opacity-100' : 'opacity-0'}
          `}>
            <span className="material-symbols-outlined text-sm text-on-surface-variant">info</span>
            <p className="text-[10px] text-on-surface-variant italic">
              This briefing was generated by an AI model and should be verified by a qualified veterinarian before clinical action.
            </p>
          </div>
        </div>
      )}

      {/* Edge case: done but no parseable sections */}
      {reasoningStatus === 'done' && sections.length === 0 && reasoning && (
        <div className="p-4 bg-surface-container/50 rounded-lg border border-outline-variant/5">
          <pre className="text-sm text-on-surface-variant whitespace-pre-wrap leading-relaxed">
            {reasoning}
          </pre>
        </div>
      )}
    </div>
  );
}
