import React from 'react';
import PropTypes from 'prop-types';
import { GlossaryTerm } from './GlossaryTerm';
import { RISK_TIER_GUIDE, SEVERITY_GUIDE } from './forecastPresentation';

const DOT = {
  usual: 'bg-slate-400',
  medium: 'bg-amber-400',
  high: 'bg-red-400',
  low: 'bg-emerald-400',
  none: 'bg-slate-500',
};

function Heading({ children }) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <span className="material-symbols-outlined text-base text-emerald-400" aria-hidden="true">lightbulb</span>
      <span className="text-[13px] font-semibold text-white">{children}</span>
    </div>
  );
}
Heading.propTypes = { children: PropTypes.node };

function Row({ dot, label, children }) {
  return (
    <li className="flex items-start gap-2">
      <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${DOT[dot]}`} aria-hidden="true" />
      <span><strong className="font-semibold text-white">{label}</strong> <span className="text-slate-400">{children}</span></span>
    </li>
  );
}
Row.propTypes = { dot: PropTypes.string, label: PropTypes.string, children: PropTypes.node };

export function RiskTierGuide() {
  return (
    <>
      <Heading>How Risk Tier works</Heading>
      <p className="mb-3 text-slate-300">The chance of an outbreak this month, compared with a normal year for this district.</p>
      <ul className="mb-3 space-y-1.5">
        <Row dot="usual" label="USUAL LEVEL">under {RISK_TIER_GUIDE.medium}&times; the normal chance. Nothing unusual.</Row>
        <Row dot="medium" label="MEDIUM">{RISK_TIER_GUIDE.medium}&times; to {RISK_TIER_GUIDE.high}&times; the normal chance. Stay alert.</Row>
        <Row dot="high" label="HIGH">{RISK_TIER_GUIDE.high}&times; or more, or a {RISK_TIER_GUIDE.highChancePercent}% chance or more. Act now.</Row>
      </ul>
      <p className="rounded-lg border border-slate-700/70 bg-slate-800/60 px-3 py-2 text-slate-400">
        Example: normal chance 3%, forecast 29.5% &rarr; about 10&times; normal &rarr; <strong className="text-red-300">HIGH</strong>.
      </p>
    </>
  );
}

export function SeverityGuide() {
  return (
    <>
      <Heading>How Severity is decided</Heading>
      <p className="mb-3 text-slate-300">If an outbreak happens, how serious it is. It follows the cases and deaths recorded in the application; when none are recorded it follows the district&apos;s past outbreaks.</p>
      <ul className="mb-3 space-y-1.5">
        <Row dot="low" label="LOW">fewer than {SEVERITY_GUIDE.medium} points.</Row>
        <Row dot="medium" label="MEDIUM">{SEVERITY_GUIDE.medium} to {SEVERITY_GUIDE.high - 1} points.</Row>
        <Row dot="high" label="HIGH">{SEVERITY_GUIDE.high} points or more.</Row>
        <Row dot="none" label="No cases">the district reports, but no cases or deaths were recorded.</Row>
        <Row dot="none" label="No data">the district does not report and has no outbreak history.</Row>
      </ul>
      <p className="rounded-lg border border-slate-700/70 bg-slate-800/60 px-3 py-2 text-slate-400">
        Points = cases + {SEVERITY_GUIDE.deathWeight} &times; deaths. One death counts as much as {SEVERITY_GUIDE.deathWeight} cases.
      </p>
    </>
  );
}

export function FollowUpGuide() {
  return (
    <>
      <Heading>When a follow-up is required</Heading>
      <p className="mb-2 text-slate-300">A follow-up is marked <strong className="text-amber-300">Required</strong> when both are true:</p>
      <ul className="space-y-1.5">
        <Row dot="medium" label="The Risk Tier is MEDIUM or HIGH.">{''}</Row>
        <Row dot="usual" label="There is no approved advisory yet.">{''}</Row>
      </ul>
    </>
  );
}

export function RiskTierTerm({ label = 'Risk Tier', align }) {
  return <GlossaryTerm term={label} align={align}><RiskTierGuide /></GlossaryTerm>;
}
RiskTierTerm.propTypes = { label: PropTypes.string, align: PropTypes.string };

export function SeverityTerm({ label = 'Severity', align }) {
  return <GlossaryTerm term={label} align={align}><SeverityGuide /></GlossaryTerm>;
}
SeverityTerm.propTypes = { label: PropTypes.string, align: PropTypes.string };

export function FollowUpTerm({ label = 'Follow-up', align }) {
  return <GlossaryTerm term={label} align={align}><FollowUpGuide /></GlossaryTerm>;
}
FollowUpTerm.propTypes = { label: PropTypes.string, align: PropTypes.string };

/** The numbered calculation behind a MEDIUM or HIGH risk, shown when hovering the light bulb. */
export function RiskCalculationCard({ reason }) {
  return (
    <>
      <Heading>How this risk was worked out</Heading>
      <ol className="space-y-2.5">
        {reason.steps.map((step, index) => (
          <li key={step.title} className="flex items-start gap-2.5">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-[11px] font-bold text-emerald-300">{index + 1}</span>
            <span>
              <strong className="block text-[12px] font-semibold text-white">{step.title}</strong>
              <span className="text-slate-400">{step.text}</span>
            </span>
          </li>
        ))}
      </ol>
    </>
  );
}
RiskCalculationCard.propTypes = { reason: PropTypes.object.isRequired };
