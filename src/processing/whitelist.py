"""VMC topic and supplier whitelist loader and prompt builder."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_WHITELIST_PATH = Path("data/vmc_whitelist.json")


def load_vmc_whitelist(whitelist_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the VMC whitelist configuration.
    
    If the file cannot be loaded or is missing, returns an empty structure.
    """
    path = whitelist_path or DEFAULT_WHITELIST_PATH
    if not path.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        candidate = repo_root / path
        if candidate.is_file():
            path = candidate

    if not path.is_file():
        logger.warning("VMC whitelist file not found at %s", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to parse VMC whitelist from %s: %s", path, e)
        return {}


def format_vmc_whitelist_prompt(whitelist_path: Optional[Path] = None) -> str:
    """Format the VMC whitelist into a prompt-friendly markdown block.
    
    This ensures that any modifications made by the user to data/vmc_whitelist.json
    are dynamically and cleanly injected into the AI system prompt.
    """
    data = load_vmc_whitelist(whitelist_path)
    if not data:
        return ""

    topics = data.get("topics", {})
    suppliers = data.get("suppliers", {})
    noise = data.get("noise_reduction", {})
    categories = data.get("daily_categories", [])

    lines = [
        "## VMC / Chassis Motion Control Topic & Supplier Whitelist (Configurable)",
        "",
        "### 1. Topic Whitelist",
        f"- **P0 Core Topics (+5)**: {', '.join(topics.get('p0_core', []))}",
        f"- **P1 Strongly Related Topics (+3)**: {', '.join(topics.get('p1_strongly_related', []))}",
        f"- **P2 Methods/Tools/AI (+1)**: {', '.join(topics.get('p2_methods_tools_ai', []))}",
        f"- **P3 Broad / Context-required (0 unless combined with P0/P1)**: {', '.join(topics.get('p3_broad_context_required', []))}",
        "",
        "### 2. Supplier Whitelist",
        f"- **P0 Core VMC Suppliers (+4)**: {', '.join(suppliers.get('p0_core', []))}",
        f"- **P1 Tier-1 Chassis/Brake/Steer/Suspension (+2)**: {', '.join(suppliers.get('p1_tier1', []))}",
        f"- **P2 Tools/Simulation/Software (+1)**: {', '.join(suppliers.get('p2_tools_software_services', []))}",
        f"- **P3 OEM Technical Sources (0 unless combined with P0/P1 Topic)**: {', '.join(suppliers.get('p3_oem', []))}",
        "",
        "### 3. Relevance Guidance",
        "A substantive P0 OR P1 topic is sufficient for relevance; no supplier or second topic is required.",
        "P2 methods/tools are relevant when explicitly applied to vehicle dynamics or chassis control.",
        "Recognize semantic equivalents and Chinese/English synonyms. Whitelist weights guide relevance; they are not a literal additive score.",
        "Apply the profile's own quality rubric. Relevant incremental updates and papers can score 4-6; do not require a breakthrough.",
        "",
        "### 4. Noise Reduction & Penalty Rules",
        f"- **Penalize (Score <= 2.0) only when the primary subject is non-technical marketing/consumer noise**: {', '.join(noise.get('penalize_keywords', []))}",
        "- Incidental noise keywords must not veto substantive chassis technology, production applications, engineering tests, or standards.",
        f"- **Context Requirement**: Items on {', '.join(noise.get('protected_keywords', []))} are ONLY accepted if combined with VMC chassis context ({', '.join(noise.get('required_vmc_context', []))}). Otherwise, penalize to noise (Score <= 2.0).",
        "",
        "### 5. Standard Output Tags",
        "You MUST choose 2 to 4 tags strictly from the following 16 standard categories for the `tags` field:",
    ]

    for cat in categories:
        cid = cat.get("id", "")
        czh = cat.get("zh", "")
        desc = cat.get("description", "")
        lines.append(f"- `#{cid}` ({czh}): {desc}")

    return "\n".join(lines)
