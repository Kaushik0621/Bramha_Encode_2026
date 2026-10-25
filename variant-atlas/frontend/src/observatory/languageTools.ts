export interface ResearchLanguage {code:string;name:string;native:string;publications?:number;native_text_studies?:number}
const aliases:Record<string,string>={eng:'en',chi:'zh',zho:'zh',jpn:'ja',rus:'ru',spa:'es',fre:'fr',fra:'fr',ger:'de',deu:'de',por:'pt',kor:'ko',ara:'ar',ita:'it'};
export const languageCode=(value:string)=>aliases[value]||value;
export function languageLabel(value:string){const code=languageCode(value);if(code==='und')return 'Unlabelled acquired text';try{return new Intl.DisplayNames(['en'],{type:'language'}).of(code)||value;}catch{return value;}}
export const sourceLanguages=[{code:'zh',name:'Chinese',native:'中文'},{code:'ja',name:'Japanese',native:'日本語'},{code:'ru',name:'Russian',native:'Русский'},{code:'es',name:'Spanish',native:'Español'},{code:'pt',name:'Portuguese',native:'Português'},{code:'fr',name:'French',native:'Français'},{code:'de',name:'German',native:'Deutsch'},{code:'ko',name:'Korean',native:'한국어'}];
