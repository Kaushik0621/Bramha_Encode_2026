"""Planning-level decision notes from explicit tools, never an importance ranking."""
from .schemas import Analysis, DecisionNote, Workspace

def decision_notes(workspace: Workspace, analysis: Analysis, selected_ids: list[str]) -> list[DecisionNote]:
    rows = {r.variant_id: r for r in analysis.results}
    notes = []
    for vid in selected_ids:
        v = next(v for v in workspace.variants if v.id == vid)
        r = rows[vid]
        reason = (f'Demo abundance {r.abundance:.2f} ≥ {analysis.criteria.abundance_min:.2f} and '
                  f'demo activity {r.activity:.2f} ≤ {analysis.criteria.activity_max:.2f}; '
                  'matches the declared filters and is included in the researcher-selected shortlist.')
        limits = ['Synthetic observations only; no biological mechanism is established.',
                  'The shared artificial assay scale does not demonstrate compatibility of real experiments.']
        if v.mapping_status != 'mapped':
            limits.append(f'Geometry unavailable: {v.mapping_status.replace("_", " ")}. Assay-based inclusion remains valid for this demo.')
        if not v.evidence_ids:
            limits.append('No fictional evidence record is linked; evidence completeness is unresolved.')
        notes.append(DecisionNote(variant_id=vid,
            observations=[m for m in workspace.measurements if m.variant_id == vid],
            selection_reason=reason, evidence_ids=v.evidence_ids,
            unresolved_question='Could differences in protein abundance, measured function, or assay context explain this supplied profile?',
            alternative_explanation='Assay variability, model-system differences or unmatched conditions could explain the pattern; the measurements alone do not distinguish them.',
            follow_up_approach='Discuss reviewing assay identity and conditions, then comparing independently repeated abundance and activity measurements with suitable controls. This is a planning suggestion, not a laboratory protocol.',
            limitations=limits))
    return notes
