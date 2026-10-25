/** Product branding is separate from the execution provenance retained by the API. */
export function modelHeadline(provider?:string,model?:string){
 if(provider==='fixture'||provider==='mock')return 'Local test model';
 if(provider==='none')return 'Scientific tools';
 if(provider==='google'&&model?.toLowerCase().includes('argon'))return 'Argon model';
 if(provider==='google')return 'Argon workflow · companion model';
 if(provider)return 'Argon workflow · fallback active';
 return 'Argon research workflow';
}
