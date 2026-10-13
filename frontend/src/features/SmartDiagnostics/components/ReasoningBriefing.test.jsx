/**
 * ReasoningBriefing.test.jsx — Component tests for the Tier 3 LLM briefing.
 * ============================================================================
 *
 * Tests rendering across all 4 states (idle, loading, done, error),
 * markdown parsing (bold, lists, headings), section card generation,
 * and edge cases (no parseable sections, footer disclaimer).
 *
 * No network access or real LLM calls required.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import ReasoningBriefing from './ReasoningBriefing';

// ═══════════════════════════════════════════════════════════════════════════
// Test fixtures — sample LLM markdown output
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Simulated 5-section LLM clinical briefing matching the system prompt format.
 */
const MOCK_FULL_REPORT = `## 1. Primary Diagnostic Assessment & Certainty Level
The AI system identifies **Lumpy Skin Disease** with **High** certainty (91.5% confidence).

## 2. Pathological & Morphological Rationale
- Firm cutaneous nodules detected across the thoracic region
- Nodule distribution is consistent with Capripoxvirus morphology

## 3. Differential Diagnosis Analysis
The runner-up class is **Cattle (Healthy)** at 3.0%.

## 4. Immediate Biosecurity & Triage Protocol
- Quarantine the affected animal within a 3km radius
- Notify regional veterinary authorities

## 5. Recommended Confirmatory Laboratory Tests
- Skin biopsy with histopathology
- PCR for Capripoxvirus DNA detection
`;

const MOCK_RAW_TEXT = 'This is a plain text report without any ## headings.';


// ═══════════════════════════════════════════════════════════════════════════
// Idle state
// ═══════════════════════════════════════════════════════════════════════════

describe('ReasoningBriefing', () => {
  // Use fake timers so setTimeout-based animations don't interfere
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('test_reasoningbriefing_idle_renders_nothing', () => {
    const { container } = render(
      <ReasoningBriefing
        reasoning={null}
        reasoningStatus="idle"
        reasoningError={null}
      />
    );
    // Component returns null in idle state
    expect(container.innerHTML).toBe('');
  });


  // ═══════════════════════════════════════════════════════════════════════
  // Loading state
  // ═══════════════════════════════════════════════════════════════════════

  it('test_reasoningbriefing_loading_shows_skeleton', () => {
    render(
      <ReasoningBriefing
        reasoning={null}
        reasoningStatus="loading"
        reasoningError={null}
      />
    );

    expect(screen.getByText(/Generating Clinical Briefing/)).toBeInTheDocument();
    expect(screen.getByText(/Qwen 2.5 is synthesising/)).toBeInTheDocument();
  });


  // ═══════════════════════════════════════════════════════════════════════
  // Error state
  // ═══════════════════════════════════════════════════════════════════════

  it('test_reasoningbriefing_error_shows_fallback_ui', () => {
    render(
      <ReasoningBriefing
        reasoning={null}
        reasoningStatus="error"
        reasoningError="Connection refused: LM Studio unreachable"
      />
    );

    expect(screen.getByText('Clinical Reasoning Unavailable')).toBeInTheDocument();
    expect(screen.getByText(/Tier 1/)).toBeInTheDocument();
  });

  it('test_reasoningbriefing_error_shows_technical_details', () => {
    render(
      <ReasoningBriefing
        reasoning={null}
        reasoningStatus="error"
        reasoningError="Connection refused: LM Studio unreachable"
      />
    );

    // The error message should be inside a <details> summary element
    expect(screen.getByText('Technical details')).toBeInTheDocument();
    expect(screen.getByText(/Connection refused/)).toBeInTheDocument();
  });


  // ═══════════════════════════════════════════════════════════════════════
  // Done state — section card rendering
  // ═══════════════════════════════════════════════════════════════════════

  it('test_reasoningbriefing_done_renders_section_cards', () => {
    render(
      <ReasoningBriefing
        reasoning={MOCK_FULL_REPORT}
        reasoningStatus="done"
        reasoningError={null}
      />
    );

    // Fast-forward all animation timers so cards become visible
    vi.advanceTimersByTime(2000);

    // The 5-section report should produce 5 section heading elements
    // Each section has a title rendered as an <h4>
    const briefing = screen.getByTestId('reasoning-briefing');
    const headings = within(briefing).getAllByRole('heading', { level: 4 });
    expect(headings.length).toBe(5);
  });

  it('test_reasoningbriefing_done_renders_section_titles', () => {
    render(
      <ReasoningBriefing
        reasoning={MOCK_FULL_REPORT}
        reasoningStatus="done"
        reasoningError={null}
      />
    );

    vi.advanceTimersByTime(2000);

    // Spot-check key section titles
    expect(screen.getByText(/Primary Diagnostic Assessment/)).toBeInTheDocument();
    expect(screen.getByText(/Biosecurity/)).toBeInTheDocument();
    expect(screen.getByText(/Laboratory Tests/)).toBeInTheDocument();
  });

  it('test_reasoningbriefing_done_renders_bold_as_strong', () => {
    render(
      <ReasoningBriefing
        reasoning={MOCK_FULL_REPORT}
        reasoningStatus="done"
        reasoningError={null}
      />
    );

    vi.advanceTimersByTime(2000);

    // **Lumpy Skin Disease** should render as <strong>
    const briefing = screen.getByTestId('reasoning-briefing');
    const strongElements = briefing.querySelectorAll('strong');
    const strongTexts = Array.from(strongElements).map(el => el.textContent);
    expect(strongTexts).toContain('Lumpy Skin Disease');
  });

  it('test_reasoningbriefing_done_renders_list_items', () => {
    render(
      <ReasoningBriefing
        reasoning={MOCK_FULL_REPORT}
        reasoningStatus="done"
        reasoningError={null}
      />
    );

    vi.advanceTimersByTime(2000);

    // List items from the markdown should render as <li>
    const briefing = screen.getByTestId('reasoning-briefing');
    const listItems = briefing.querySelectorAll('li');
    expect(listItems.length).toBeGreaterThanOrEqual(4);
  });


  // ═══════════════════════════════════════════════════════════════════════
  // Done state — edge cases
  // ═══════════════════════════════════════════════════════════════════════

  it('test_reasoningbriefing_done_no_sections_shows_raw_pre', () => {
    render(
      <ReasoningBriefing
        reasoning={MOCK_RAW_TEXT}
        reasoningStatus="done"
        reasoningError={null}
      />
    );

    vi.advanceTimersByTime(2000);

    // Without ## headings, the fallback <pre> should render raw text
    const briefing = screen.getByTestId('reasoning-briefing');
    const preElement = briefing.querySelector('pre');
    expect(preElement).not.toBeNull();
    expect(preElement.textContent).toContain('plain text report');
  });

  it('test_reasoningbriefing_footer_disclaimer_visible', () => {
    render(
      <ReasoningBriefing
        reasoning={MOCK_FULL_REPORT}
        reasoningStatus="done"
        reasoningError={null}
      />
    );

    vi.advanceTimersByTime(3000);

    expect(
      screen.getByText(/verified by a qualified veterinarian/)
    ).toBeInTheDocument();
  });

  it('cleans leading SEVERITY META headers and does not render them as section cards', () => {
    const rawReportWithMeta = `### SEVERITY META: Grade=Mild | Prognosis=Guarded | Description=Minimal lesions

## 1. Clinical Severity & Pathological Assessment
Lesion coverage indicates mild early presentation.

## 2. Primary Diagnostic Assessment & Certainty Level
High certainty.`;

    render(
      <ReasoningBriefing
        reasoning={rawReportWithMeta}
        reasoningStatus="done"
        reasoningError={null}
      />
    );

    vi.advanceTimersByTime(3000);

    expect(screen.queryByText(/SEVERITY META/i)).not.toBeInTheDocument();
    expect(screen.getByText(/1\. Clinical Severity/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Primary Diagnostic Assessment/i)).toBeInTheDocument();
  });

  it('renders synthesized severity top banner when severityAssessment is provided', () => {
    const severityAssessment = {
      grade: 'Moderate',
      prognosis: 'Recoverable',
      description: 'Multifocal eruptive nodules detected.',
    };

    render(
      <ReasoningBriefing
        reasoning={MOCK_FULL_REPORT}
        reasoningStatus="done"
        reasoningError={null}
        severityAssessment={severityAssessment}
      />
    );

    vi.advanceTimersByTime(3000);

    expect(screen.getByText(/Synthesized Severity Grade & Prognosis/i)).toBeInTheDocument();
    expect(screen.getByText(/Multifocal eruptive nodules detected/i)).toBeInTheDocument();
    expect(screen.getByText('Moderate')).toBeInTheDocument();
    expect(screen.getByText('Recoverable')).toBeInTheDocument();
  });
});

