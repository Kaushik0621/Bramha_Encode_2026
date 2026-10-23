from . import validate_narrative
from ..schemas import Narrative

class MockExplainer:
    async def explain(self, payload: dict) -> Narrative:
        findings=[]
        for e in payload['evidence']:
            vids=[v for v in e['variant_ids'] if v in payload['selected_ids']]
            if vids: findings.append(dict(variant_ids=vids,text=e['text'],evidence_ids=[e['id']]))
        narrative=Narrative(summary='Fixture explanation: the shortlist follows the editable demo criteria. Inspect linked fictional records and missing geometry before planning follow-up.',
            findings=findings,
            hypotheses=[dict(text='Could a repeat measurement distinguish a stable assay profile from measurement variability?',status='unverified')] if payload['selected_ids'] else [],
            follow_up_questions=['Which measurements should be repeated under a documented assay protocol?', 'What additional evidence would distinguish the competing explanations?'] if payload['selected_ids'] else ['Would changing the explicit demo criteria produce a reviewable candidate set?'],
            limitations=['Synthetic measurements and illustrative geometry', 'Fictional evidence; no actual protein effects, clinical conclusions or validated experimental priorities.'])
        return validate_narrative(narrative,payload)
