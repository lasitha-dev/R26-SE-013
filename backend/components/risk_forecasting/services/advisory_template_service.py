"""
Advisory Template Service (Phase 3).

Provides rule-based, deterministic standard advisory template generation mapped directly
from authoritative model prediction context (disease, risk level, severity, period, district).

RULES:
1. Deterministic: No LLMs, stochastic generation, or external API calls.
2. Scientific Fidelity: Does NOT alter risk levels, probabilities, or severity thresholds.
3. Priority Mapping: LOW -> ROUTINE, MEDIUM -> IMPORTANT, HIGH -> URGENT.
"""

from typing import Dict, List, Optional, Tuple


class AdvisoryTemplateService:
    """Service generating controlled, rule-based standard advisory content."""

    @staticmethod
    def map_priority(risk_level: str) -> str:
        """Maps forecast risk level to recommended advisory priority."""
        rl = risk_level.upper()
        if rl == "HIGH":
            return "URGENT"
        elif rl == "MEDIUM":
            return "IMPORTANT"
        return "ROUTINE"

    def generate_standard_content(
        self,
        disease: str,
        district: str,
        target_year: int,
        target_month: int,
        risk_level: str,
        predicted_severity: Optional[str] = None,
        disclaimer: Optional[str] = None,
    ) -> Tuple[str, str, List[str], List[str], str, str, str]:
        """
        Generates standard advisory components.

        Returns:
            (title, forecast_summary, preventive_actions, symptoms_to_watch, contact_instruction, disclaimer, priority)
        """
        dis_upper = disease.upper()
        risk_upper = risk_level.upper()
        priority = self.map_priority(risk_upper)
        period_str = f"{target_year}-{target_month:02d}"

        if dis_upper == "FMD":
            title = f"Foot and Mouth Disease (FMD) Biosecurity Advisory - {district} ({period_str})"
            sev_info = f" with predicted {predicted_severity} severity" if predicted_severity else ""
            forecast_summary = (
                f"Statistical surveillance for {district} District during {period_str} indicates a "
                f"{risk_upper} risk of Foot and Mouth Disease (FMD){sev_info}."
            )
            preventive_actions = [
                "Restrict movement of cloven-hoofed livestock (cattle, buffalo, goats, sheep) into or out of affected farm boundaries.",
                "Disinfect livestock transport vehicles and footwear before entering farm premises using approved footbaths.",
                "Isolate any newly acquired animals for a minimum of 14 days prior to herd integration.",
                "Maintain strict biosecurity around shared watering points and grazing lands.",
            ]
            symptoms_to_watch = [
                "High fever, depression, and severe drop in milk production.",
                "Blisters or painful vesicles on tongue, gums, lips, and interdigital skin of hooves.",
                "Excessive salivation (foaming or stringy drool) and reluctance to feed.",
                "Lameness, limping, or reluctance to stand.",
            ]
            contact_instruction = (
                f"Immediately report any suspected FMD symptoms to your assigned Government Veterinary Officer "
                f"or Divisional Veterinary Office in {district} District."
            )
            final_disclaimer = disclaimer or (
                "FMD Stage 1 and Stage 2 model predictions serve as statistical decision support "
                "based on audited climate and spatial surveillance indices."
            )

        elif dis_upper == "LSD":
            title = f"Lumpy Skin Disease (LSD) Surveillance Advisory - {district} ({period_str})"
            sev_info = f" (Predicted severity suppression: {predicted_severity})" if predicted_severity else ""
            forecast_summary = (
                f"Surveillance data for {district} District during {period_str} projects a "
                f"{risk_upper} risk tier for Lumpy Skin Disease (LSD){sev_info}."
            )
            preventive_actions = [
                "Implement vector-control measures to reduce blood-feeding insects (flies, mosquitoes, ticks) around cattle sheds.",
                "Apply approved insect repellents to cattle and maintain clean, dry bedding areas.",
                "Quarantine affected or newly arrived cattle immediately.",
                "Avoid communal grazing and restrict cattle movement across district borders.",
            ]
            symptoms_to_watch = [
                "Multiple firm, raised nodular skin lesions (2–5 cm diameter) over body, head, neck, and udder.",
                "High persistent fever and enlarged superficial lymph nodes.",
                "Nasal discharge, watery eyes, and lacrimation.",
                "Edema/swelling of limbs and brisket area.",
            ]
            contact_instruction = (
                f"Contact your local Veterinary Officer in {district} District immediately if nodular skin lesions "
                f"or fever symptoms appear in your herd."
            )
            final_disclaimer = disclaimer or (
                "LSD Stage 2 binary severity predictions serve strictly as a quiet-period false-alarm suppressor "
                "(LOW vs MOD/HIGH) and are NOT statistically validated to discriminate severity during active outbreak waves."
            )

        else:
            raise ValueError(f"Unsupported disease type '{disease}'. Allowed: FMD, LSD.")

        return title, forecast_summary, preventive_actions, symptoms_to_watch, contact_instruction, final_disclaimer, priority


# Singleton instance
advisory_template_service = AdvisoryTemplateService()
