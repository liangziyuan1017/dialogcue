"""Final trainable emotion label set (11 classes).

Action-oriented ontology for debt-collection state tracking and script recommendation.
Each label maps to a collector response strategy (S1–S11).

Sources:
  - raw_to_trainable_emotion_mapping.yaml / data_relabelled_emotion.csv
"""

TAG_LABELS = {
    "distress": {
        "domain": "Distress",
        "description": (
            "Customer is in real hardship but has not given up: financial pressure, "
            "helplessness, exhaustion, or overwhelming stress; needs empathy and "
            "practical relief options"
        ),
    },
    "despair": {
        "domain": "Despair",
        "description": (
            "Customer shows hopelessness, resignation, or extreme distress including "
            "suicidal ideation; requires risk awareness, emotional de-escalation, "
            "and avoidance of additional pressure"
        ),
    },
    "complaint": {
        "domain": "Complaint",
        "description": (
            "Customer is dissatisfied with facts, rules, or outcomes: grievances, "
            "unfairness, disappointment, resentment, or broad frustration about "
            "the situation; needs explanation of rules and response to concerns"
        ),
    },
    "irritation": {
        "domain": "Irritation",
        "description": (
            "Customer is annoyed or bothered by collection contact itself: impatience, "
            "sarcasm, dismissiveness, or fatigue with repeated calls; needs cooling "
            "down, fewer interruptions, and faster focus on essentials"
        ),
    },
    "hostility": {
        "domain": "Hostility",
        "description": (
            "Customer is actively aggressive or threatening: anger, abuse, insults, "
            "contempt, accusations, or defiance; requires risk control, boundary "
            "setting, and prevention of escalation"
        ),
    },
    "anxiety": {
        "domain": "Anxiety",
        "description": (
            "Customer worries about future risks or outcomes: fear, uncertainty, "
            "hesitation, or concern about consequences; needs clarity, consequence "
            "explanation, and reduced perceived risk"
        ),
    },
    "distrust": {
        "domain": "Distrust",
        "description": (
            "Customer does not trust the institution, policy, or collector: skepticism, "
            "suspicion, feeling deceived or targeted; needs trust-building, "
            "transparency, and evidence-based explanation"
        ),
    },
    "confusion": {
        "domain": "Confusion",
        "description": (
            "Customer cannot understand current information: confusion, disbelief, "
            "questioning, or seeking confirmation; needs clear explanation, examples, "
            "and verification of understanding"
        ),
    },
    "defensive": {
        "domain": "Defensive",
        "description": (
            "Customer protects self-image or avoids blame: defensiveness, avoidance, "
            "resistance, denial, or victimhood framing; needs reduced accusation, "
            "lowered defensiveness, and gradual progression"
        ),
    },
    "negotiation": {
        "domain": "Negotiation",
        "description": (
            "Customer actively seeks conditional adjustment or bargaining: pleading, "
            "insistence, challenges, probing, urgency, or conditional repayment "
            "offers; needs structured negotiation, policy boundaries, and plan "
            "evaluation"
        ),
    },
    "engagement": {
        "domain": "Engagement",
        "description": (
            "Customer shows cooperation, positive intent, or face-saving effort: "
            "agreement, willingness, gratitude, earnest repayment desire, sincerity, "
            "self-justification, or rational problem-solving; needs recognition of "
            "effort, reinforced responsibility, and forward execution"
        ),
    },
}
