import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';

/**
 * Section configuration — maps each of the 6 LLM briefing sections
 * to an icon, accent border colour, and subtle background tint.
 */
const SECTION_META = [
  { icon: 'psychology', accent: 'border-rose-500', bg: 'bg-rose-500/5', label: 'Clinical Severity & Staging' },
  { icon: 'verified', accent: 'border-primary', bg: 'bg-primary/5', label: 'Diagnostic Assessment' },
  { icon: 'biotech', accent: 'border-secondary', bg: 'bg-secondary/5', label: 'Morphological Rationale' },
  { icon: 'compare_arrows', accent: 'border-tertiary', bg: 'bg-surface-container-high/40', label: 'Differential Diagnosis' },
  { icon: 'shield', accent: 'border-error', bg: 'bg-error/5', label: 'Biosecurity Protocol' },
  { icon: 'science', accent: 'border-[#f59e0b]', bg: 'bg-[#f59e0b]/5', label: 'Laboratory Tests' },
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
        <ul key={key++} className="space-y-2 ml-1 mt-2.5">
          {listItems.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2.5 text-xs md:text-sm text-on-surface-variant leading-relaxed">
              <span className="material-symbols-outlined text-primary text-base shrink-0 mt-0.5" style={{ fontVariationSettings: "'FILL' 1" }}>
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
          className="text-2xs font-bold text-primary uppercase tracking-widest mt-4 mb-1.5 font-mono"
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
        className="text-xs md:text-sm text-on-surface-variant leading-relaxed mt-1"
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
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-on-surface font-bold">$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="text-primary bg-primary/10 px-1.5 py-0.5 rounded text-2xs font-mono">$1</code>');
}

/**
 * Split the LLM Markdown report into its sections by `## ` headings.
 * Returns an array of { title, content } objects.
 */
function splitSections(markdown) {
  if (!markdown) return [];

  // Clean any residual metadata tags or non-section preamble
  let cleanMd = markdown
    .replace(/(?:\[|###?\s*|\*\*)*SEVERITY_?META:[^\n]+/gi, '')
    .replace(/^#+\s*SEVERITY[^\n]+/gim, '')
    .trim();

  const firstHeadingIdx = cleanMd.search(/^##\s+/m);
  if (firstHeadingIdx !== -1) {
    cleanMd = cleanMd.substring(firstHeadingIdx);
  }

  const sections = [];
  const parts = cleanMd.split(/^##\s+/m).filter(Boolean);

  for (const part of parts) {
    const newlineIdx = part.indexOf('\n');
    if (newlineIdx === -1) continue;

    const title = part.substring(0, newlineIdx).trim();
    const content = part.substring(newlineIdx + 1).trim();

    // Ignore any non-section remnants
    if (!title || title.toLowerCase().includes('severity meta')) continue;

    sections.push({ title, content });
  }

  return sections;
}


// ═══════════════════════════════════════════════════════════════════════════
// Loading Skeleton with Shimmer
// ═══════════════════════════════════════════════════════════════════════════

function LoadingSkeleton() {
  const [dots, setDots] = useState('');

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '' : prev + '.'));
    }, 450);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4">
      {/* Header indicator */}
      <div className="flex items-center gap-3 p-3 rounded-lg bg-surface-container/60 border border-primary/20">
        <div className="p-2 bg-primary/10 rounded-lg shrink-0">
          <span className="material-symbols-outlined text-primary animate-spin" style={{ animationDuration: '3s' }}>
            neurology
          </span>
        </div>
        <div>
          <p className="text-xs md:text-sm font-bold text-on-surface flex items-center gap-1">
            Generating Clinical Briefing{dots}
          </p>
          <p className="text-3xs md:text-2xs text-on-surface-variant mt-0.5 font-mono">
            Qwen 2.5 is synthesising diagnostic context, differential rules, and triage protocol
          </p>
        </div>
      </div>

      {/* Shimmer skeleton cards */}
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="rounded-xl border border-outline-variant/10 p-5 bg-surface-container-low relative overflow-hidden"
          style={{ opacity: 1 - (i - 1) * 0.2 }}
        >
          <div className="h-4 w-1/3 rounded mb-3 shimmer-box" />
          <div className="space-y-2.5">
            <div className="h-3 w-full rounded shimmer-box" />
            <div className="h-3 w-5/6 rounded shimmer-box" />
            <div className="h-3 w-2/3 rounded shimmer-box" />
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
    <div className="flex items-start gap-4 p-5 rounded-xl bg-error/5 border border-error/20">
      <div className="p-2.5 bg-error/10 rounded-xl shrink-0">
        <span className="material-symbols-outlined text-error text-2xl">cloud_off</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-on-surface mb-1">
          Clinical Reasoning Unavailable
        </p>
        <p className="text-xs text-on-surface-variant leading-relaxed mb-3">
          The LLM reasoning engine (LM Studio) could not be reached. The Tier 1 &amp; 2
          detection and classification results above remain fully valid and clinically usable.
        </p>
        {error && (
          <details className="text-2xs text-on-surface-variant">
            <summary className="cursor-pointer hover:text-on-surface font-medium underline">
              Technical details
            </summary>
            <pre className="mt-2 p-3 bg-surface-container rounded-lg text-3xs font-mono overflow-x-auto whitespace-pre-wrap border border-outline-variant/20">
              {error}
            </pre>
          </details>
        )}
        <div className="mt-3.5 pt-3 border-t border-outline-variant/10 space-y-1">
          <p className="text-2xs text-on-surface-variant font-semibold">Troubleshooting:</p>
          <ul className="text-2xs text-on-surface-variant space-y-1 ml-4 list-disc">
            <li>Verify LM Studio is running and the local server is started</li>
            <li>Confirm model weights are loaded (e.g. qwen2.5-vl-3b-instruct)</li>
            <li>Check API endpoint: <code className="text-primary font-mono">http://127.0.0.1:1234/v1</code></li>
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
 * @param {string|null} props.reasoning          - Markdown report from the LLM
 * @param {string}      props.reasoningStatus    - 'idle' | 'loading' | 'done' | 'error'
 * @param {string|null} props.reasoningError     - Error message if status === 'error'
 * @param {object|null} [props.severityAssessment] - Parsed LLM severity metadata
 */
export default function ReasoningBriefing({ reasoning, reasoningStatus, reasoningError, severityAssessment }) {
  const [visibleCards, setVisibleCards] = useState(0);

  // Parse sections from the Markdown report
  const sections = reasoningStatus === 'done' && reasoning ? splitSections(reasoning) : [];

  // Animate section cards appearing sequentially
  useEffect(() => {
    if (reasoningStatus !== 'done' || sections.length === 0) {
      setVisibleCards(0);
      return;
    }

    const timers = [];
    for (let i = 1; i <= sections.length; i++) {
      const timer = setTimeout(() => setVisibleCards(i), i * 200);
      timers.push(timer);
    }
    return () => timers.forEach(clearTimeout);
  }, [reasoningStatus, sections.length]);

  // Don't render anything in idle state
  if (reasoningStatus === 'idle') return null;

  return (
    <div
      className="bg-surface-container-low rounded-2xl p-5 md:p-8 border border-outline-variant/15 shadow-card-subtle transition-all duration-700"
      data-testid="reasoning-briefing"
    >
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-outline-variant/10">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-primary/10 rounded-xl border border-primary/20">
            <span className="material-symbols-outlined text-primary text-xl md:text-2xl">
              neurology
            </span>
          </div>
          <div>
            <h3 className="text-base md:text-lg font-bold text-on-surface tracking-tight">
              AI Clinical Briefing
            </h3>
            <span className="text-2xs font-bold text-primary tracking-widest uppercase font-mono">
              04 Tier 3 — LLM Reasoning Engine
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-full bg-surface-container text-tertiary border border-outline-variant/20 text-3xs font-mono font-medium">
            Capripox / Bovine Clinical Protocol
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
          {/* Synthesized Clinical Evaluation Callout */}
          {severityAssessment && severityAssessment.grade && (
            <div className="mb-4 p-3.5 md:p-4 rounded-xl bg-surface-container/70 border border-primary/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm animate-fadeIn">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="p-1.5 rounded-lg bg-primary/10 border border-primary/20 text-primary shrink-0">
                  <span className="material-symbols-outlined text-base">verified</span>
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] font-mono font-bold text-primary uppercase tracking-wider">
                    Synthesized Severity Grade &amp; Prognosis
                  </p>
                  <p className="text-xs text-on-surface font-medium truncate">
                    {severityAssessment.description || `Clinical condition evaluated as ${severityAssessment.grade}.`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="px-2 py-0.5 rounded-md bg-rose-500/15 border border-rose-500/30 text-rose-300 text-3xs font-mono font-bold uppercase">
                  {severityAssessment.grade}
                </span>
                {severityAssessment.stage && (
                  <span className="px-2 py-0.5 rounded-md bg-primary/15 border border-primary/30 text-primary text-3xs font-mono font-bold uppercase">
                    {severityAssessment.stage}
                  </span>
                )}
              </div>
            </div>
          )}

          {sections.map((section, idx) => {
            const meta = SECTION_META[idx] || SECTION_META[0];
            return (
              <div
                key={idx}
                className={`
                  rounded-xl border-l-4 ${meta.accent} ${meta.bg}
                  p-4 md:p-5 border border-outline-variant/10
                  transition-all duration-500 hover:border-outline-variant/25
                  ${idx < visibleCards ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}
                `}
              >
                {/* Section heading */}
                <div className="flex items-center gap-2.5 mb-2.5">
                  <div className="w-6 h-6 rounded-md bg-surface-container flex items-center justify-center border border-outline-variant/20">
                    <span className="material-symbols-outlined text-sm text-primary">
                      {meta.icon}
                    </span>
                  </div>
                  <h4
                    className="text-xs md:text-sm font-bold text-on-surface"
                    dangerouslySetInnerHTML={{ __html: formatInline(section.title) }}
                  />
                </div>

                {/* Section content */}
                <div className="pl-8">
                  {parseMarkdownContent(section.content)}
                </div>
              </div>
            );
          })}

          {/* Footer Disclaimer */}
          <div className={`
            flex items-center gap-2.5 pt-4 mt-6 border-t border-outline-variant/10
            transition-all duration-500
            ${visibleCards >= sections.length ? 'opacity-100' : 'opacity-0'}
          `}>
            <span className="material-symbols-outlined text-base text-primary/80 shrink-0">verified_user</span>
            <p className="text-2xs text-on-surface-variant">
              This briefing was generated by an AI model and should be verified by a qualified veterinarian before clinical action.
            </p>
          </div>
        </div>
      )}

      {/* Edge case: done but no parseable sections */}
      {reasoningStatus === 'done' && sections.length === 0 && reasoning && (
        <div className="p-4 bg-surface-container/60 rounded-xl border border-outline-variant/10">
          <pre className="text-xs text-on-surface-variant whitespace-pre-wrap leading-relaxed font-sans">
            {reasoning}
          </pre>
        </div>
      )}
    </div>
  );
}

ReasoningBriefing.propTypes = {
  reasoning: PropTypes.string,
  reasoningStatus: PropTypes.oneOf(['idle', 'loading', 'done', 'error']).isRequired,
  reasoningError: PropTypes.string,
  severityAssessment: PropTypes.object,
};
