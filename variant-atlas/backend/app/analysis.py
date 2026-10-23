from math import dist
from .schemas import Analysis, Criteria, Neighbors, Neighbor, VariantDetail, Workspace

def variant_detail(workspace: Workspace, vid: str) -> VariantDetail:
    variant = next((v for v in workspace.variants if v.id == vid), None)
    if variant is None:
        raise KeyError(vid)
    return VariantDetail(variant=variant,
        measurements=[m for m in workspace.measurements if m.variant_id == vid],
        evidence=[e for e in workspace.evidence if e.id in variant.evidence_ids],
        coordinate=next((p for p in workspace.structure.points if p.position == variant.position),None))

def filter_variants(workspace: Workspace, criteria: Criteria) -> Analysis:
    scores = {(m.variant_id,m.assay_id): m.value for m in workspace.measurements}
    results = []
    for v in workspace.variants:
        a = scores.get((v.id,'assay-abundance-demo'))
        b = scores.get((v.id,'assay-activity-demo'))
        reasons = []
        if a is None or b is None:
            reasons.append('Insufficient measurement: abundance or activity is missing.')
        else:
            if a < criteria.abundance_min:
                reasons.append('Abundance is below the demo minimum.')
            if b > criteria.activity_max:
                reasons.append('Activity is above the demo maximum.')
        if criteria.mapping == 'mapped' and v.mapping_status != 'mapped':
            reasons.append('Excluded by mapped-only filter.')
        if criteria.mapping == 'unmapped' and v.mapping_status == 'mapped':
            reasons.append('Excluded by unmapped-only filter.')
        if criteria.evidence == 'present' and not v.evidence_ids:
            reasons.append('No fictional evidence record is linked.')
        if criteria.evidence == 'missing' and v.evidence_ids:
            reasons.append('Excluded by missing-evidence filter.')
        matches = not reasons
        results.append(dict(variant_id=v.id,matches=matches,abundance=a,activity=b,
            mapping_status=v.mapping_status,evidence_count=len(v.evidence_ids),
            reasons=reasons or ['Meets the editable synthetic assay criteria.']))
    matching = [r for r in results if r['matches']]
    return Analysis(criteria=criteria,matching_ids=[r['variant_id'] for r in matching],
        mapped_count=sum(r['mapping_status']=='mapped' for r in matching),
        unmapped_count=sum(r['mapping_status']!='mapped' for r in matching),
        missing_measurement_count=sum(r['abundance'] is None or r['activity'] is None for r in results),results=results)

def get_spatial_neighbors(workspace: Workspace, vid: str, radius: float) -> Neighbors:
    detail = variant_detail(workspace, vid)
    if detail.coordinate is None:
        return Neighbors(variant_id=vid,radius=radius,status='unavailable',
            reason=f'No coordinate: {detail.variant.mapping_status.replace("_", " ")}.',neighbors=[])
    def xyz(p): return (p.x,p.y,p.z)
    neighbors=[]
    for v in workspace.variants:
        if v.id == vid: continue
        other=variant_detail(workspace,v.id).coordinate
        if other is None: continue
        d=dist(xyz(detail.coordinate),xyz(other))
        if d <= radius:
            neighbors.append(Neighbor(variant_id=v.id,position=v.position,distance=round(d,6)))
    return Neighbors(variant_id=vid,radius=radius,status='available',neighbors=sorted(neighbors,key=lambda n:(n.distance,n.variant_id)))
