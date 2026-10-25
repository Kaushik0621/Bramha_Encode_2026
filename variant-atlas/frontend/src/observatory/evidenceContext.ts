import type {Claim,Study} from './types';
import type {CoordinateChain} from '../workspace/StructureViewer';
export type EvidenceKind='gene'|'variant'|'cell'|'compound'|'process'|'effect';
export interface EvidenceTerm {key:string;label:string;kind:EvidenceKind;color:string;hex:number}
export const categories:Record<EvidenceKind,{label:string;color:string;hex:number}>={gene:{label:'Gene / protein',color:'#a78bfa',hex:0xa78bfa},variant:{label:'Variant / sequence change',color:'#fb7185',hex:0xfb7185},cell:{label:'Cell / tissue context',color:'#38bdf8',hex:0x38bdf8},compound:{label:'Compound / substance',color:'#fbbf24',hex:0xfbbf24},process:{label:'Biological process',color:'#2dd4bf',hex:0x2dd4bf},effect:{label:'Reported change',color:'#fb923c',hex:0xfb923c}};
export const escapePattern=(text:string)=>text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
export function literalMatch(text:string,label:string){return new RegExp('(?<![\\p{L}\\p{N}_])'+escapePattern(label)+'(?![\\p{L}\\p{N}_])','iu').test(text);}
const lexicon:Record<Exclude<EvidenceKind,'variant'|'effect'>,string[]>={gene:['PTEN','TP53','p53','CREBBP','CBP','SLC7A11','GPX4','FSP1','GCH1','DHODH','BRCA1','BRCA2','EGFR','KRAS','BRAF','AKT','mTOR','NFE2L2','NRF2'],cell:['tumour microenvironment','tumor microenvironment','cancer cells','tumour cells','tumor cells','stromal cells','immune cells','hepatocellular carcinoma','breast cancer','lung cancer','glioblastoma','liver','brain','membrane','TME'],compound:['sorafenib','glutathione','erastin','RSL3','iron','lipids','CoQ10','BH4'],process:['ferroptosis','apoptosis','lipid peroxidation','oxidative stress','therapeutic resistance','cell death','iron metabolism']};
export function termsForClaim(claim:Claim,studies:Study[],chains:CoordinateChain[]):EvidenceTerm[]{
 // Labels are literal matches in a saved observation, not inferred biological entities or outcomes.
 const text=claim.text;const out=new Map<string,EvidenceTerm>();const add=(label:string,kind:EvidenceKind)=>{if(!literalMatch(text,label))return;const key=kind+':'+label.toLowerCase();out.set(key,{...categories[kind],key,label,kind});};
 for(const [kind,labels] of Object.entries(lexicon))for(const label of labels)add(label,kind as EvidenceKind);
 for(const s of studies)for(const gene of s.genes)add(gene,'gene');
 for(const chain of chains)for(const alias of chain.aliases)if(alias.length>=2)add(alias,'gene');
 for(const m of text.matchAll(/\bp\.[A-Z][a-z]{0,2}\d+[A-Z*][a-z]{0,2}\b|\bc\.\d+[ACGT]>[ACGT]\b/g))add(m[0],'variant');
 for(const m of text.matchAll(/\b(?:inhibit(?:ion|ed|s|ing)?|deplet(?:ion|ed|es|ing)?|increas(?:e|ed|es|ing)|decreas(?:e|ed|es|ing)|reduc(?:tion|ed|es|ing)|enhanc(?:ement|ed|es|ing)|loss of function|gain of function|preserved abundance)\b/gi))add(m[0],'effect');
 return [...out.values()].sort((a,b)=>a.kind.localeCompare(b.kind)||b.label.length-a.label.length);
}
export function matchingChains(term:EvidenceTerm|null,chains:CoordinateChain[]){if(!term||term.kind!=='gene')return [];return chains.filter(c=>c.aliases.some(alias=>alias.toLowerCase()===term.label.toLowerCase())||c.description.toLowerCase()===term.label.toLowerCase());}
export function markedSegments(text:string,terms:EvidenceTerm[]):{text:string;term?:EvidenceTerm}[]{const sorted=[...terms].sort((a,b)=>b.label.length-a.label.length);if(!sorted.length)return [{text}];const pattern=new RegExp('(?<![\\p{L}\\p{N}_])(?:'+sorted.map(t=>escapePattern(t.label)).join('|')+')(?![\\p{L}\\p{N}_])','giu');const out:{text:string;term?:EvidenceTerm}[]=[];let cursor=0;for(const match of text.matchAll(pattern)){const index=match.index!;if(index>cursor)out.push({text:text.slice(cursor,index)});out.push({text:match[0],term:sorted.find(t=>t.label.toLowerCase()===match[0].toLowerCase())});cursor=index+match[0].length;}if(cursor<text.length)out.push({text:text.slice(cursor)});return out;}
