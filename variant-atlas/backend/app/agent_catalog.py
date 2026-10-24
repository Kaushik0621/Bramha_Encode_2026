"""Product-facing specifications for the roles implemented by the action engine."""
from .tools.registry import NAMES

ROLE_SPECS = [
    (
        "coordinator",
        "Research lead",
        "Plans the exploration and delegates scoped reviews.",
        "A research question, selected substitutions and declared criteria.",
        "Ranked paths, tool choices, handoffs and a checked brief or abstention.",
        [
            "discover_tools",
            "spawn_specialist",
            "request_reconciliation",
            "inspect_run_budget",
        ],
        "Start here when a question needs several kinds of evidence.",
    ),
    (
        "identity",
        "Sequence identity reviewer",
        "Checks that a substitution belongs to the pinned reference sequence.",
        "Protein substitution IDs and the reference sequence version.",
        "Accepted identities, mismatches and identity limitations.",
        ["resolve_reference_sequence", "validate_variant_identity"],
        "Use before interpreting a newly selected substitution.",
    ),
    (
        "assay",
        "Measurement reviewer",
        "Explains activity and abundance measurements in their experimental context.",
        "Selected variants, assay metadata and measurement records.",
        "Observed profiles, missing measurements and comparison limits.",
        [
            "inspect_assay",
            "check_score_direction",
            "assess_comparability",
            "join_measurements",
            "filter_measurements",
        ],
        "Use when activity and abundance tell different stories.",
    ),
    (
        "structure",
        "Spatial evidence reviewer",
        "Locates selected positions in the experimental reference structure.",
        "Accepted mappings, coordinates and selected substitutions.",
        "Coordinate coverage, reference distances and unsupported spatial claims.",
        [
            "load_structure_metadata",
            "align_structure_reference",
            "map_variant_residues",
            "calculate_residue_distances",
            "find_spatial_neighbors",
        ],
        "Use to ask whether measured substitutions are near each other in reference space.",
    ),
    (
        "evidence",
        "Research evidence reviewer",
        "Finds permitted source passages and functional annotations.",
        "A scoped research question and pinned sources.",
        "Source-linked passages, observations and unresolved evidence gaps.",
        [
            "fetch_source_snapshot",
            "retrieve_functional_annotations",
            "search_methods_text",
            "retrieve_passage",
        ],
        "Use to connect an observation to methods and existing source evidence.",
    ),
    (
        "verifier",
        "Evidence and numbers verifier",
        "Checks citations and numeric claims against saved artifacts.",
        "Draft findings and exact artifact references.",
        "Mechanical check results; scientific truth still requires review.",
        [
            "validate_evidence_references",
            "validate_numeric_claims",
            "validate_shortlist",
        ],
        "Use before treating a draft as a reviewable result.",
    ),
    (
        "reconciliation",
        "Review reconciler",
        "Compares specialist outputs and retains disagreements.",
        "Artifacts handed off from independent reviewers.",
        "Agreements, disagreements and limitations for the research lead.",
        [
            "assess_comparability",
            "validate_evidence_references",
            "validate_numeric_claims",
        ],
        "Use when measurement and spatial interpretations do not agree.",
    ),
]
SPECIALIST_ROLES = [r[0] for r in ROLE_SPECS if r[0] != "coordinator"]


def catalog(settings, runs):
    profiles = []
    for role, title, purpose, inputs, outputs, tools, when in ROLE_SPECS:
        active = [
            {
                "run_id": r["run_id"],
                "task_id": t["id"],
                "status": t["status"],
                "question": t["question"],
            }
            for r in runs
            for t in r.get("tasks", [])
            if t["role"] == role
            and t["status"] in ("queued", "running")
            and r["status"] in ("queued", "running")
        ]
        profiles.append(
            {
                "id": role,
                "title": title,
                "purpose": purpose,
                "inputs": inputs,
                "outputs": outputs,
                "when_to_use": when,
                "recommended_tools": tools,
                "active_tasks": active,
                "execution": "Live model-selected actions; a role is not running until delegated.",
                "permissions": "Child tool permissions must be a subset of the parent; permissions are saved on each task.",
                "limits": {"max_steps": 12, "max_seconds": 180}
                if role != "coordinator"
                else {"max_steps": 12, "max_seconds": settings.max_run_seconds},
                "limits_note": "Task limits also share the investigation-wide request, tool, depth and concurrency budgets.",
                "cannot": [
                    "Cannot invent an assay value or accepted coordinate.",
                    "Cannot establish clinical effects or generate a validated mutant fold.",
                ],
            }
        )
    return {
        "agents": profiles,
        "tool_count": len(NAMES),
        "brain": {
            "provider": "google" if settings.google_api_key else settings.llm_provider,
            "model": settings.argon_model
            if settings.google_api_key
            else settings.openrouter_model,
            "argon_verified": False,
        },
        "concurrency": settings.max_concurrent_workers,
        "scope": "Human PTEN workspace; synthetic workspace is separately labeled.",
    }
