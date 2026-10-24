import './brand-logo.css';

/** Shared lockup prepared from the user-supplied Bramha Atlas logo. */
export default function BrandLogo({caption='RESEARCH WORKSPACE',compact=false}:{caption?:string;compact?:boolean}) {
  return <span className={`bramha-brand${compact?' bramha-brand-compact':''}`}>
    <span className="bramha-logo-panel">
      <svg viewBox="48 27 1869 765" role="img" aria-label="Bramha Atlas" preserveAspectRatio="xMidYMid meet">
        <title>Bramha Atlas</title>
        <image href="/branding/bramha-atlas-logo.png" width="1945" height="808"/>
      </svg>
    </span>
    {caption&&<small className="bramha-logo-caption">{caption}</small>}
  </span>;
}
