import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from .analysis import filter_variants, get_spatial_neighbors
from .decisions import decision_notes
from .schemas import InvestigationRequest, Investigation, Step
from .llm import explanation_payload, ExplanationError
from .llm.mock import MockExplainer
from .llm.openrouter import OpenRouterExplainer

def now(): return datetime.now(timezone.utc).isoformat()

async def investigate(repository, settings, request: InvestigationRequest, observer=None) -> Investigation:
    async def event(worker, status, summary, **kwargs):
        if observer:
            await observer(worker, status, summary, **kwargs)
    steps=[]
    def step(name,detail,status='completed'):
        steps.append(Step(name=name,status=status,detail=detail,completed_at=now()))
    await event('data-retrieval','running','Loading variants, assay metadata, structure and fictional source records.')
    workspace=repository.workspace()
    await event('data-retrieval','completed',f'Loaded {len(workspace.variants)} variant records and {len(workspace.assays)} assay datasets.',
        artifact=dict(id='artifact-data',name='Workspace records',summary='Versioned synthetic source records.',
            refs=[workspace.id,workspace.protein.id,*[a.id for a in workspace.assays]],
            data=dict(dataset_version=workspace.dataset_version,variants=len(workspace.variants),assays=len(workspace.assays),
                evidence=len(workspace.evidence),structure_points=len(workspace.structure.points))),
        metrics=dict(variants=len(workspace.variants),assays=len(workspace.assays)),dataset_version=workspace.dataset_version)
    step('Validate input','Thresholds validated on the artificial zero-to-one scale.')
    await event('assay-analysis','running','Applying the declared assay criteria; missing measurements remain missing.',input_refs=['artifact-data'])
    analysis=filter_variants(workspace,request.criteria)
    ids=analysis.matching_ids if request.selected_ids is None else list(dict.fromkeys(request.selected_ids))
    if not set(ids)<=set(analysis.matching_ids):
        raise ValueError('Selected IDs must belong to the current matching candidate set.')
    if len(ids) > request.candidate_budget:
        raise ValueError(f'Shortlist contains {len(ids)} variants but candidate capacity is {request.candidate_budget}. Curate the shortlist explicitly; no automatic importance ranking is applied.')
    step('Filter variants',f'{len(analysis.matching_ids)} matching candidates; {len(ids)} included in this investigation.')
    await event('assay-analysis','completed',f'{len(analysis.matching_ids)} variants meet the filters; {analysis.missing_measurement_count} have insufficient measurements.',
        artifact=dict(id='artifact-filter-results',name='Assay filter results',summary='Deterministic selection and exclusion reasons.',refs=ids,data=analysis.model_dump(mode='json')),
        metrics=dict(matching_variants=len(analysis.matching_ids),selected_variants=len(ids),missing_measurements=analysis.missing_measurement_count))
    await event('structure-mapping','running','Checking mapped coordinates and calculating spatial neighbours.',input_refs=['artifact-filter-results'])
    mapped=sum(v.mapping_status=='mapped' for v in workspace.variants if v.id in ids)
    spatial=[get_spatial_neighbors(workspace,vid,12).model_dump(mode='json') for vid in ids]
    step('Check coverage',f'{mapped} mapped, {len(ids)-mapped} unmapped selected candidates; missing measurements were not coerced to zero.')
    await event('structure-mapping','completed',f'{mapped} selected candidates mapped; {len(ids)-mapped} lack coordinates.',
        artifact=dict(id='artifact-mapping',name='Mapping and neighbours',summary='Calculated geometry in demo coordinate units; radius 12.',refs=ids,
            data=dict(mapped=mapped,unmapped=len(ids)-mapped,neighbors=spatial)),metrics=dict(mapped=mapped,unmapped=len(ids)-mapped))
    if len(ids)>mapped:
        await event('structure-mapping','warning','Unmapped candidates remain in the shortlist. Structural proximity does not establish shared function.',input_refs=[v.id for v in workspace.variants if v.id in ids and v.mapping_status!='mapped'])
    await event('evidence-review','running','Collecting supplied fictional evidence and checking source-to-variant links.',input_refs=['artifact-filter-results','artifact-mapping'])
    payload=explanation_payload(workspace,analysis,ids)
    payload['research_question'] = request.research_question
    payload['candidate_budget'] = request.candidate_budget
    sources=[e['id'] for e in payload['evidence']]
    step('Collect evidence',f'{len(sources)} fictional source records linked by stable IDs.')
    await event('evidence-review','completed',f'Collected {len(sources)} fictional source records; real assay compatibility is not established.',
        artifact=dict(id='artifact-evidence',name='Supplied evidence',summary='Fictional records, not publications or biological validation.',refs=sources,
            data=dict(records=payload['evidence'])),metrics=dict(source_records=len(sources)))
    narrative=None
    error=None
    provider='none'
    model=None
    mode='deterministic'
    if request.explanation_mode=='none':
        step('Explain supplied evidence','Explanation disabled; deterministic results only.','skipped')
        await event('brief-synthesis','skipped','Optional explanation disabled; deterministic decision notes remain available.',input_refs=['artifact-evidence'])
    else:
        provider='mock' if request.explanation_mode=='fixture' else settings.llm_provider
        model='fixture-extractive-v1' if provider=='mock' else settings.openrouter_model or None
        await event('brief-synthesis','running',f'Awaiting {provider} explanation of supplied evidence. No intermediate model progress is inferred.',input_refs=['artifact-evidence','artifact-filter-results'])
        try:
            if provider=='mock': explainer=MockExplainer()
            elif provider=='openrouter': explainer=OpenRouterExplainer(settings)
            else: raise ExplanationError('Unsupported LLM provider. Choose mock or openrouter in the backend environment.')
            narrative=await explainer.explain(payload)
            mode='fixture' if provider=='mock' else 'openrouter'
            step('Explain supplied evidence',f'{provider}: validated structured explanation; findings restricted to supplied source text.')
            await event('brief-synthesis','completed','Structured explanation returned and passed the provider-adapter reference and claim checks.',
                artifact=dict(id='artifact-narrative',name='Validated explanation',summary='Source-linked narrative; hypotheses remain unverified.',refs=sources,data=narrative.model_dump(mode='json')))
        except ExplanationError as exc:
            error=str(exc)
            mode='llm_error'
            step('Explain supplied evidence',error,'failed')
            await event('brief-synthesis','failed',error)
    await event('verification','running','Checking selected identifiers, numeric outputs and source references before saving.',input_refs=['artifact-filter-results','artifact-evidence'])
    # Adapter already validated any narrative. Verify the assembled deterministic references independently.
    assert set(ids)<=set(analysis.matching_ids)
    assert set(sources)<={e.id for e in workspace.evidence}
    step('Verify shortlist','Selected IDs remain a subset of the deterministic result. Evidence references and supplied claims checked; scientific correctness still requires researcher review.')
    await event('verification','completed','Deterministic identifier and evidence checks passed. Scientific correctness still requires researcher review.',
        artifact=dict(id='artifact-verification',name='Verification report',summary='Identifier and deterministic output checks.',refs=ids+sources,
            data=dict(selected_ids_valid=True,evidence_ids_valid=True,narrative_validated=narrative is not None,narrative_error=error)),
        metrics=dict(selected_ids=len(ids),sources=len(sources)))
    if error:
        await event('verification','warning','Explanation failed. Only the deterministic partial brief is available; model claims were not accepted.')
    step('Save investigation','Criteria, numeric tool outputs, sources, provider, mode and completed steps saved with this record.')
    result=Investigation(id='inv-'+uuid4().hex,title=request.title.strip() or 'Untitled investigation',created_at=now(),
        dataset_version=workspace.dataset_version,research_question=request.research_question,
        candidate_budget=request.candidate_budget,decision_notes=decision_notes(workspace,analysis,ids),
        evidence_snapshot=[e for e in workspace.evidence if e.id in sources],
        variant_snapshot=[v for v in workspace.variants if v.id in ids],
        criteria=request.criteria,selected_ids=ids,source_ids=sources,
        analysis=analysis,narrative=narrative,result_mode=mode,provider=provider,model=model,explanation_error=error,steps=steps)
    # Yield once before persistence so an already-requested cancellation can win.
    await asyncio.sleep(0)
    repository.save(result)
    await event('coordinator','output', 'Review brief saved with its original criteria, evidence and model identity.',
        artifact=dict(id='artifact-brief',name='Review brief',summary='Saved shortlist, decision notes and Markdown export.',refs=[result.id,*ids],data=dict(investigation_id=result.id,selected_ids=ids,result_mode=mode)))
    return result

def markdown_export(inv: Investigation, workspace) -> str:
    def clean(text): return str(text).replace('\n',' ').replace('\r',' ')
    selected=set(inv.selected_ids)
    lines=[f'# {clean(inv.title)}','', '**Synthetic data — demonstration only.**',
        '**Illustrative geometry — not a biological structure.**','',
        f'- Investigation: {inv.id}',f'- Created: {inv.created_at}',f'- Dataset version: {inv.dataset_version}',
        f'- Result mode: {inv.result_mode}',f'- Provider: {inv.provider}',f'- Model: {inv.model or "none"}',
        '', '## Research decision', clean(inv.research_question),
        f'- Candidate capacity: {inv.candidate_budget}; included: {len(inv.selected_ids)}.',
        '- Inclusion follows declared criteria and researcher curation; no universal ranking or information-gain calculation.',
        '', '## Editable demo criteria',f'- Abundance >= {inv.criteria.abundance_min:.2f}',f'- Activity <= {inv.criteria.activity_max:.2f}',
        f'- Mapping filter: {inv.criteria.mapping}',f'- Evidence filter: {inv.criteria.evidence}',
        '- Arbitrary synthetic criteria, not clinical cutoffs or validated prioritization.',
        '', '## Verified numeric shortlist', '| Variant | Position | Abundance | Activity | Geometry |', '|---|---:|---:|---:|---|']
    variants={v.id:v for v in (inv.variant_snapshot or workspace.variants)}
    for row in inv.analysis.results:
        if row.variant_id in selected:
            v=variants[row.variant_id]
            lines.append(f'| {v.id} | {v.position} | {row.abundance} | {row.activity} | {v.mapping_status} |')
    if not selected: lines.append('No variants were included in this investigation.')
    lines+=['','## Per-variant decision notes']
    for note in inv.decision_notes:
        lines += [f'### {note.variant_id}', '**Supplied synthetic observations**']
        lines += [f'- {m.assay_id}: {m.value}' for m in note.observations]
        lines += ['**Calculated inclusion rationale**', note.selection_reason,
                  '**Unresolved question**', note.unresolved_question,
                  '**Alternative explanation — unverified**', note.alternative_explanation,
                  '**Proposed follow-up approach — unverified, researcher review required**', note.follow_up_approach,
                  '**Fictional evidence references:** ' + (', '.join(note.evidence_ids) or 'None'),
                  '**Missing information and limitations**']
        lines += [f'- {limitation}' for limitation in note.limitations]
    lines+=['','## Excluded or not included variants']
    for row in inv.analysis.results:
        if row.variant_id not in selected:
            why = 'Matches the filters but was not included by researcher curation.' if row.matches else ' '.join(row.reasons)
            lines.append(f'- {row.variant_id}: {why}')
    lines+=['','## Fictional evidence']
    for e in (inv.evidence_snapshot or workspace.evidence):
        if e.id in inv.source_ids: lines.extend([f'### {e.id}: {e.title}',e.text,''])
    if inv.narrative:
        lines+=['## Explanation',inv.narrative.summary,'']
        for f in inv.narrative.findings:
            lines.append(f'- {f.text} [variants: {", ".join(f.variant_ids)}; sources: {", ".join(f.evidence_ids)}]')
        lines+=['','## Unverified hypotheses']+[f'- Unverified: {h.text}' for h in inv.narrative.hypotheses]
        lines+=['','## Follow-up questions']+[f'- {q}' for q in inv.narrative.follow_up_questions]
    if inv.explanation_error: lines+=['','## Explanation error',inv.explanation_error]
    lines+=['','## Completed workflow']+[f'- {s.name}: {s.status}. {s.detail} ({s.completed_at})' for s in inv.steps]
    lines+=['','## Limitations', '- All variants, scores, sequence and evidence are fictional.',
        '- Structural proximity is calculated context, not proof of function or disease.',
        '- No real PTEN data, clinical classification, treatment or experiment validation.',
        '- This is a deterministic workflow with optional explanation; human review is required.']
    if inv.narrative: lines += [f'- {x}' for x in inv.narrative.limitations]
    return '\n'.join(lines)+'\n'
