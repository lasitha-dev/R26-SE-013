"""Clinical Recommendation Generator for Smart Diagnostics.

Synthesizes structured, actionable clinical recommendations (triage priority,
biosecurity & quarantine protocol, clinical monitoring & next steps) based on the
predicted disease, severity grade, and model telemetry.
"""
from __future__ import annotations

import re
from typing import Optional

from ..schemas import ClinicalRecommendation


def normalize_disease_key(name: Optional[str]) -> str:
    key = re.sub(r"[^a-z]", "", str(name or "").lower())
    if any(alias in key for alias in ("lumpyskin", "lsd")):
        return "lumpy_skin"
    if any(alias in key for alias in ("footandmouth", "fmd")):
        return "foot_and_mouth"
    if "mastitis" in key:
        return "mastitis"
    if any(alias in key for alias in ("cattle", "healthy")):
        return "healthy"
    return "unknown"


def normalize_severity_grade(grade: Optional[str]) -> str:
    g = str(grade or "").strip().lower()
    if "severe" in g:
        return "Severe"
    if "moderate" in g:
        return "Moderate"
    if "mild" in g:
        return "Mild"
    if "no visible" in g:
        return "No visible regions"
    return "Unassessable"


def generate_clinical_recommendation(
    disease_name: Optional[str],
    severity_grade: Optional[str],
    coverage_pct: Optional[float] = None,
    symptoms: Optional[str] = None,
) -> ClinicalRecommendation:
    """Generate structured clinical recommendations based on prediction and clinical severity."""
    key = normalize_disease_key(disease_name)
    grade = normalize_severity_grade(severity_grade)

    # ---------------------------------------------------------
    # Healthy Baseline
    # ---------------------------------------------------------
    if key == "healthy":
        return ClinicalRecommendation(
            triage_level="Routine Herd Maintenance",
            biosecurity_protocol=[
                "Maintain standard herd biosecurity and hygiene at feeding and watering stations.",
                "Adhere to routine regional vaccination and prophylactic deworming schedules.",
                "Ensure clean, dry bedding and well-ventilated housing environments.",
            ],
            clinical_monitoring=[
                "Conduct routine daily health observation during feeding and milking cycles.",
                "Monitor Body Condition Score (BCS) and rumination rates periodically.",
                "Record any sudden drops in feed intake or milk yield for prompt investigation.",
            ],
            treatment_considerations="No therapeutic intervention required. Continue routine preventative herd care.",
        )

    # ---------------------------------------------------------
    # Lumpy Skin Disease (LSD)
    # ---------------------------------------------------------
    if key == "lumpy_skin":
        if grade == "Severe":
            return ClinicalRecommendation(
                triage_level="Urgent Veterinary Action / Acute Isolation",
                biosecurity_protocol=[
                    "Immediate complete physical isolation of the animal in insect-screened quarantine housing.",
                    "Enforce strict biosecurity lockdown: halt all livestock movements on and off the premises.",
                    "Daily virucidal disinfection of feeding troughs, waterers, tools, and handler boots.",
                    "Implement aggressive vector control (pyrethroid pour-ons, insecticidal misting) around housing.",
                ],
                clinical_monitoring=[
                    "Intensive vital checks every 6-8 hours: rectal temperature, respiratory rate, lung auscultation.",
                    "Daily assessment of lesion ulceration, sloughing, and secondary bacterial sitfast development.",
                    "Inspect for severe brisket, limb, or submandibular edema and respiratory distress.",
                    "Notify local veterinary regulatory officers immediately for statutory disease surveillance.",
                ],
                treatment_considerations="Systemic broad-spectrum antibiotic coverage to combat secondary bacterial infections, aggressive NSAIDs (e.g. ketoprofen or meloxicam) for pyrexia/pain, and fluid support if dehydrated.",
            )
        elif grade == "Moderate":
            return ClinicalRecommendation(
                triage_level="Priority Quarantine & Active Intervention",
                biosecurity_protocol=[
                    "Segregate the affected animal in a designated quarantine stall with vector-proof netting.",
                    "Apply topical insect repellents and pour-on insecticides to the patient and pen perimeter.",
                    "Isolate all in-contact herd members for 14-day daily clinical surveillance.",
                    "Establish vehicle wheel wash and footbaths at farm entrance points.",
                ],
                clinical_monitoring=[
                    "Twice daily rectal temperature monitoring to track the febrile trajectory.",
                    "Inspect circumscribed nodular cutaneous lesions for erosion, exudate, or core necrosis.",
                    "Monitor daily feed consumption, rumination frequency, and milk production levels.",
                ],
                treatment_considerations="Veterinary-supervised anti-inflammatory therapy (NSAIDs), topical antiseptic/fly-repellent wound spray on nodular lesions to prevent myiasis, supportive multivitamins.",
            )
        else:  # Mild or default
            return ClinicalRecommendation(
                triage_level="Priority Monitoring & Precautionary Isolation",
                biosecurity_protocol=[
                    "Isolate animal in a separate sick bay to prevent vector transmission to healthy cohorts.",
                    "Deploy vector control (fly traps, mosquito/tick repellents) in all animal sheds.",
                    "Restrict introduction of new animals or equipment until containment is confirmed.",
                ],
                clinical_monitoring=[
                    "Conduct daily visual inspection of nodular lesion spread across skin, neck, and perineum.",
                    "Record body temperature daily to detect secondary febrile spikes early.",
                    "Palpate prescapular and precrural lymph nodes for bilateral enlargement.",
                ],
                treatment_considerations="Nutritional support, ad-libitum clean water access, antiseptic wound spray on localized nodules, avoid handling stress.",
            )

    # ---------------------------------------------------------
    # Foot and Mouth Disease (FMD)
    # ---------------------------------------------------------
    if key == "foot_and_mouth":
        if grade == "Severe":
            return ClinicalRecommendation(
                triage_level="Critical Emergency / Statutory Outbreak Response",
                biosecurity_protocol=[
                    "Emergency lockdown: immediately restrict all animal, milk, feed, and manure movement.",
                    "Mandatory citric acid (0.2%) or sodium carbonate (4%) disinfectant footbaths at all access points.",
                    "Full isolation of the affected housing unit; dedicated personnel with protective equipment.",
                    "Notify the Department of Animal Production & Health (DAPH) / state veterinarian immediately.",
                ],
                clinical_monitoring=[
                    "Continuous observation for recumbency, severe hoof coronitis, or claw horn sloughing.",
                    "Monitor for cardiac involvement (arrhythmias, myocarditis) especially in younger calves.",
                    "Inspect oral cavity for extensive ruptured vesicles and painful erosive stomatitis.",
                ],
                treatment_considerations="Intensive veterinary supportive therapy: systemic analgesics/NSAIDs for severe pain, topical mild antiseptic mouthwashes, soft gruel feeding, systemic antibiotics if deep pododermatitis develops.",
            )
        elif grade == "Moderate":
            return ClinicalRecommendation(
                triage_level="Urgent Veterinary Intervention & Strict Containment",
                biosecurity_protocol=[
                    "Strictly isolate the animal; FMD is extremely contagious via direct contact, aerosol, and fomites.",
                    "Disinfect all milking equipment, utensils, and footwear with approved virucidal solutions.",
                    "Do not mix milk from affected quarters or animals with bulk tank supplies.",
                    "Restrict visitors and non-essential farm traffic completely.",
                ],
                clinical_monitoring=[
                    "Inspect feet daily for interdigital cleft ulcerations and coronary band involvement.",
                    "Monitor salivation rate, appetite reduction, and lameness severity scores.",
                    "Check rectal temperature twice daily and log progression of oral/muzzle vesicles.",
                ],
                treatment_considerations="Systemic NSAIDs to alleviate oral and locomotor pain, copper sulfate or potassium permanganate footbaths, soft palatable wet rations.",
            )
        else:  # Mild or default
            return ClinicalRecommendation(
                triage_level="Immediate Quarantine & Statutory Alert",
                biosecurity_protocol=[
                    "Isolate animal immediately in quarantine pen pending veterinary confirmation.",
                    "Place virucidal disinfectant footbaths (citric acid or bleach) at barn entrances.",
                    "Cease animal transport and monitor neighboring livestock within a 3-km radius.",
                ],
                clinical_monitoring=[
                    "Examine dental pad, tongue, and interdigital clefts twice daily for emerging vesicles.",
                    "Observe for early signs of smacking lips, excessive salivation, and shifting lameness.",
                    "Record daily milk production and morning/evening rectal temperatures.",
                ],
                treatment_considerations="Provide soft green fodder and mash feeds, clean fresh water, topical antiseptic wash on suspected lesions as directed by attending vet.",
            )

    # ---------------------------------------------------------
    # Mastitis
    # ---------------------------------------------------------
    if key == "mastitis":
        if grade == "Severe":
            return ClinicalRecommendation(
                triage_level="Urgent Veterinary Emergency",
                biosecurity_protocol=[
                    "Isolate cow in dedicated sick stall; milk strictly last with dedicated unit.",
                    "Safely discard all infected milk; do not feed raw to calves or herd members.",
                    "Disinfect milking unit thoroughly with 0.5% chlorhexidine or peracetic acid wash.",
                    "Wear disposable gloves; change or disinfect between cows.",
                ],
                clinical_monitoring=[
                    "Check vital signs every 4-6 hours: heart rate, capillary refill time, rectal temperature.",
                    "Monitor for signs of acute endotoxemia/shock (cold extremities, severe depression, recumbency).",
                    "Palpate all udder quarters for severe edema, hardness, discoloration, or gangrene.",
                ],
                treatment_considerations="Emergency veterinary examination: systemic broad-spectrum antimicrobial therapy, IV hypertonic saline or balanced fluids, systemic NSAID (flunixin meglumine), frequent udder stripping with oxytocin under vet supervision.",
            )
        elif grade == "Moderate":
            return ClinicalRecommendation(
                triage_level="Priority Veterinary Care & Quarter Isolation",
                biosecurity_protocol=[
                    "Segregate animal from the main lactating group; milk last in milking order.",
                    "Perform pre- and post-milking teat disinfection with proven germicidal barrier dip.",
                    "Change bedding daily; maintain dry and clean cubicle surfaces.",
                ],
                clinical_monitoring=[
                    "Examine foremilk at each milking for clots, discoloration, and serum separation.",
                    "Palpate affected quarter for local heat, swelling, and sensitivity twice daily.",
                    "Track daily rectal temperature and milk yield recovery trajectory.",
                ],
                treatment_considerations="Intramammary antibiotic infusion based on veterinary prescription and milk culture, supportive systemic NSAID for local udder swelling, frequent quarter stripping.",
            )
        else:  # Mild or default
            return ClinicalRecommendation(
                triage_level="Routine Clinical Care & Subclinical Screening",
                biosecurity_protocol=[
                    "Milk affected cow last; ensure thorough teat cup sanitization post-milking.",
                    "Apply approved post-milking teat dip (iodine or chlorhexidine formulation).",
                    "Keep cows standing for at least 30 minutes post-milking on clean surfaces.",
                ],
                clinical_monitoring=[
                    "Conduct California Mastitis Test (CMT) or electrical conductivity checks daily.",
                    "Inspect foremilk strip cup samples for minor flakes or watery appearance.",
                    "Palpate quarter softness and completeness of milk letdown after each milking.",
                ],
                treatment_considerations="Frequent milk stripping of the affected quarter, barrier teat disinfection, supportive udder mint/massage cream, evaluate need for culture.",
            )

    # ---------------------------------------------------------
    # Fallback / Unassessable
    # ---------------------------------------------------------
    return ClinicalRecommendation(
        triage_level="Clinical Re-evaluation Required",
        biosecurity_protocol=[
            "Maintain standard precautionary isolation until clinical status is verified by a veterinarian.",
            "Sanitize housing and handler footwear as a preventative biosecurity measure.",
        ],
        clinical_monitoring=[
            "Re-examine the animal under bright, natural illumination and capture clear follow-up imagery.",
            "Schedule an on-site physical clinical examination with the reviewing veterinary practitioner.",
            "Monitor feed consumption, vitality, and body temperature daily.",
        ],
        treatment_considerations="Supportive husbandry and monitoring pending definitive on-site veterinary evaluation.",
    )
