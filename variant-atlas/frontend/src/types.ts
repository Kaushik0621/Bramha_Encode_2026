export type MappingStatus = 'mapped' | 'missing_coordinates' | 'outside_structure_coverage';
export interface Point {position:number;x:number;y:number;z:number}
export interface Variant {id:string;protein_id:string;position:number;ref:string;alt:string;synthetic:true;mapping_status:MappingStatus;evidence_ids:string[]}
export interface Measurement {variant_id:string;assay_id:string;value:number|null;synthetic:true}
export interface Evidence {id:string;title:string;text:string;variant_ids:string[];synthetic:true;kind:'fictional_record'}
export interface Structure {id:string;protein_id:string;label:string;coordinate_units:string;points:Point[];synthetic:true}
export interface Workspace {id:string;name:string;dataset_version:string;synthetic:true;protein:{id:string;name:string;sequence:string;length:number};variants:Variant[];measurements:Measurement[];assays:{id:string;name:string;property:'abundance'|'activity';scale:string}[];evidence:Evidence[];structure:Structure}
export interface Criteria {abundance_min:number;activity_max:number;mapping:'all'|'mapped'|'unmapped';evidence:'all'|'present'|'missing'}
export interface VariantResult {variant_id:string;matches:boolean;abundance:number|null;activity:number|null;mapping_status:MappingStatus;evidence_count:number;reasons:string[]}
export interface Analysis {criteria:Criteria;matching_ids:string[];mapped_count:number;unmapped_count:number;missing_measurement_count:number;results:VariantResult[]}
export interface Neighbors {variant_id:string;radius:number;status:'available'|'unavailable';reason:string|null;neighbors:{variant_id:string;position:number;distance:number}[]}
export interface Narrative {summary:string;findings:{variant_ids:string[];text:string;evidence_ids:string[]}[];hypotheses:{text:string;status:'unverified'}[];follow_up_questions:string[];limitations:string[]}
export interface DecisionNote {variant_id:string;observations:Measurement[];selection_reason:string;evidence_ids:string[];unresolved_question:string;alternative_explanation:string;follow_up_approach:string;hypothesis_status:'unverified';limitations:string[]}
export interface Investigation {id:string;title:string;created_at:string;dataset_version:string;research_question:string;candidate_budget:number;decision_notes:DecisionNote[];evidence_snapshot:Evidence[];variant_snapshot:Variant[];criteria:Criteria;selected_ids:string[];source_ids:string[];analysis:Analysis;narrative:Narrative|null;result_mode:'fixture'|'openrouter'|'deterministic'|'llm_error';provider:string;model:string|null;explanation_error:string|null;steps:{name:string;status:'completed'|'failed'|'skipped';detail:string;completed_at:string}[]}
export interface InvestigationSummary {id:string;title:string;created_at:string;selected_count:number;result_mode:string}
export interface Health {status:'ok'|'error';storage:string;storage_ready:boolean;storage_error:string|null;llm_provider:string;llm_model:string|null;llm_configured:boolean;dataset_mode:'synthetic'}
