"""Typed descriptions over existing immutable tool artifacts, never model-made values."""
from typing import Literal
from pydantic import Field
from .schemas import Model

Category=Literal['data_validation','descriptive_analysis','statistical_analysis','evidence_review','model_based_prediction','simulation']
class AnalysisMethod(Model):
    name:str
    implementation:str
    implementation_version:str
class AnalysisInputs(Model):
    artifact_refs:list[str]=Field(default_factory=list)
    dataset_version:str
    parameters:dict=Field(default_factory=dict)
    variant_ids:list[str]=Field(default_factory=list)
class AnalysisChange(Model):
    type:Literal['selection','criterion','evidence','analysis_result','hypothesis','structural_model','none']='none'
    reason:str='No baseline comparison.'
    before_refs:list[str]=Field(default_factory=list)
    after_refs:list[str]=Field(default_factory=list)
class VisualBinding(Model):
    type:Literal['sequence_identity','sequence_strip','assay_context','assay_comparability','coverage_matrix','assay_scatter','structure_coverage','residue_distance','spatial_neighbors','scenario_comparison','source_passages','verification_matrix']
    artifact_ref:str
    mapping:dict=Field(default_factory=dict)
class AnalysisInterpretation(Model):
    supported_statements:list[str]=Field(default_factory=list)
    hypotheses:list[str]=Field(default_factory=list)
    limitations:list[str]=Field(default_factory=list)
class AnalysisResult(Model):
    id:str
    run_id:str
    task_id:str
    operation:str
    category:Category
    status:Literal['result_available','unavailable','failed','skipped']
    question:str
    method:AnalysisMethod
    inputs:AnalysisInputs
    baseline_result_id:str|None=None
    output_artifact_refs:list[str]
    change:AnalysisChange=Field(default_factory=AnalysisChange)
    visualizations:list[VisualBinding]
    interpretation:AnalysisInterpretation
    verification_refs:list[str]=Field(default_factory=list)
    data_mode:Literal['real','synthetic']='real'
    execution_mode:str='live'

OPERATIONS={
 'validate_variant_identity':('data_validation','Reference identity comparison','sequence_identity','Which selected substitutions match the pinned reference?'),
 'resolve_reference_sequence':('data_validation','Read pinned canonical sequence','sequence_strip','Which reference sequence and version were used?'),
 'inspect_assay':('data_validation','Read structured assay endpoint metadata','assay_context','What does this experimental endpoint measure?'),
 'assess_comparability':('data_validation','Compare pinned assay metadata','assay_comparability','Can these endpoints be interpreted on the same scale?'),
 'join_measurements':('descriptive_analysis','Join by audited substitution identity','coverage_matrix','Which original-scale measurements are available?'),
 'summarize_measurement_coverage':('data_validation','Count observed and null assay values','coverage_matrix','Which selected assay observations are missing?'),
 'filter_measurements':('descriptive_analysis','Apply declared assay-specific criteria','assay_scatter','Which selected variants meet the declared criteria?'),
 'compare_measurement_patterns':('descriptive_analysis','Compare native-scale profiles','assay_scatter','How do the measured profiles differ?'),
 'load_structure_metadata':('data_validation','Read experimental construct metadata','structure_coverage','Which experimental model supports structural context?'),
 'align_structure_reference':('data_validation','Read precomputed audited sequence-to-construct alignment','structure_coverage','Which audited reference-to-construct correspondence is accepted?'),
 'map_variant_residues':('data_validation','Look up audited residue correspondence','structure_coverage','Which selected positions have accepted coordinates?'),
 'calculate_residue_distances':('descriptive_analysis','Euclidean distance between accepted reference C-alpha coordinates','residue_distance','How far apart are these reference positions?'),
 'find_spatial_neighbors':('descriptive_analysis','Radius query over accepted reference C-alpha coordinates','spatial_neighbors','Which reference positions fall within the declared radius?'),
 'compare_analysis_scenarios':('descriptive_analysis','Recompute explicit before/after criteria','scenario_comparison','What enters or leaves the selected candidate set?'),
 'search_methods_text':('evidence_review','Retrieve pinned methods passages','source_passages','Which inspected methods passages address this question?'),
 'retrieve_passage':('evidence_review','Read exact permitted source passage','source_passages','What does the original source say?'),
 'validate_evidence_references':('data_validation','Check reference identity and scope','verification_matrix','Do the referenced artifacts and sources exist?'),
 'validate_numeric_claims':('data_validation','Compare claims with exact artifact paths','verification_matrix','Do numerical claims match saved computed values?'),
}

def instrument(run,artifact,parameters=None):
    if artifact['kind'] not in OPERATIONS:return None
    category,method,visual,question=OPERATIONS[artifact['kind']];data=artifact['data'];outcome=data.get('outcome')
    is_skipped=data.get('data',{}).get('status')=='skipped'
    result=AnalysisResult(id='analysis-'+artifact['id'],run_id=run['run_id'],task_id=artifact['task_id'],operation=artifact['kind'],category=category,status='skipped' if is_skipped else 'result_available' if outcome=='ok' else 'unavailable',question=question,method=AnalysisMethod(name='Not executed: precondition check' if is_skipped else method,implementation='app.tools.registry.Registry.execute:'+artifact['kind'],implementation_version='bramha-analysis-v1'),inputs=AnalysisInputs(dataset_version=run['dataset_version'],parameters=parameters or {},variant_ids=run['request']['selected_ids'],artifact_refs=next((t.get('input_artifact_ids',[]) for t in run['tasks'] if t['id']==artifact['task_id']),[])),output_artifact_refs=[artifact['id']],visualizations=[VisualBinding(type=visual,artifact_ref=artifact['id'])],interpretation=AnalysisInterpretation(supported_statements=[data.get('summary','Actual tool output is attached.')],limitations=data.get('limitations',[])+['This output does not establish a causal mechanism or clinical classification.']),data_mode=run.get('data_mode','real'),execution_mode=run.get('execution_mode','live'))
    validate_bindings(run,result)
    return result.model_dump(mode='json')

def validate_bindings(run,result):
    artifacts={a['id']:a for a in run['artifacts']}
    refs=result.output_artifact_refs+result.inputs.artifact_refs+[v.artifact_ref for v in result.visualizations]+result.verification_refs
    if result.run_id!=run['run_id'] or result.inputs.dataset_version!=run['dataset_version']:raise ValueError('Analysis result version mismatch.')
    for ref in refs:
        if ref not in artifacts:raise ValueError('Unknown analysis artifact reference.')
        if artifacts[ref].get('dataset_version',run['dataset_version'])!=run['dataset_version']:raise ValueError('Analysis artifact version mismatch.')
    if any(v.artifact_ref not in result.output_artifact_refs for v in result.visualizations):raise ValueError('Visual binding must reference an output of this operation.')
