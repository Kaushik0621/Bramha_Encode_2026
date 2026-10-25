import {useId} from 'react';
import {useTheme} from './Theme';
import './brand-logo.css';

/** One source drawing keeps the contours identical in both display palettes. */
export default function BrandLogo({caption='RESEARCH WORKSPACE',compact=false,emblemOnly=false}:{caption?:string;compact?:boolean;emblemOnly?:boolean}){
 const {theme}=useTheme();const id='brand-'+useId().replace(/:/g,'');
 return <span className={'bramha-brand'+(compact?' bramha-brand-compact':'')+(emblemOnly?' bramha-brand-symbol':'')}>
  <svg className="bramha-emblem" viewBox={compact?'55 20 975 835':'0 0 1088 1445'} role="img" aria-label={emblemOnly?'Bramha Atlas':'Bramha Atlas emblem'}>
   <title>Bramha Atlas · Three perspectives, one investigation</title>
   <defs><filter id={id} colorInterpolationFilters="sRGB"><feColorMatrix type="matrix" values="-.13 0 0 0 .95  -.47 0 0 0 .91  -.63 0 0 0 .84  0 0 0 1 0"/></filter></defs>
   <image href="/branding/bramha-emblem.png" width="1088" height="1445" filter={theme==='dark'?`url(#${id})`:undefined}/>
  </svg>
  {!emblemOnly&&<span className="bramha-wordmark"><span className="bramha-wordmark-name">Bramha <span>Atlas</span></span>{caption&&<small className="bramha-logo-caption">{caption}</small>}</span>}
 </span>;
}
