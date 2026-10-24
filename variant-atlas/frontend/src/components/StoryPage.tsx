// Short explainer opened from the header brand: the problem, the workflow and the limits, in under a minute of reading.
const steps=[
  {n:'01',title:'Bring the evidence together',text:'Public PTEN measurements are loaded with their sources: an activity assay (a yeast fitness proxy), a protein-abundance assay (VAMP-seq) and the 1D5R experimental structure. Every value keeps its origin and uncertainty.'},
  {n:'02',title:'Declare your criteria',text:'You set explicit thresholds, for example "abundance stays high, activity drops". Every variant shows exactly why it is in or out. Missing data stays missing, never silently zero.'},
  {n:'03',title:'See it in 3D',text:'Matching variants light up on the protein structure, so you can see which ones cluster together in space and which cannot be placed.'},
  {n:'04',title:'Investigate with an agent',text:'An AI research agent plans checks, calls analysis tools and writes a review brief. Its numbers are verified against the data; anything it cannot support is rejected, not invented.'},
  {n:'05',title:'You make the decision',text:'You get a shortlist that fits your experiment budget, with the open question and a follow-up idea for each variant. Export it, save it, revisit it later.'},
];
export default function StoryPage(){
  return <div className="story-page">
    <header className="story-header"><a className="brand" href="/?page=story"><div className="brand-mark" aria-hidden="true"><span/><span/><span/></div><div><b>Variant<span>Atlas</span></b><small>THE STORY</small></div></a></header>
    <main className="story-main">
      <section className="story-hero">
        <span className="eyebrow">WHY THIS EXISTS</span>
        <h1>200 mutations.<br/><em>Budget for 10 experiments.</em></h1>
        <p>A genetics team studying a disease gene often has far more candidate mutations than lab time. The hard part is not finding data. It is combining evidence from different experiments, seeing where it is missing, and defending which ten to test next.</p>
      </section>
      <section className="story-steps" aria-label="How Variant Atlas works">
        {steps.map(s=><article key={s.n} className="story-step"><span className="story-step-n">{s.n}</span><h2>{s.title}</h2><p>{s.text}</p></article>)}
      </section>
      <section className="story-limits">
        <h2>What it is not</h2>
        <ul>
          <li>Not a clinical tool and not a diagnosis. It supports research planning only.</li>
          <li>The AI explains and checks; it does not decide. The researcher stays responsible for the choice.</li>
          <li>Hypotheses and follow-up ideas are labelled as unverified until tested in the lab.</li>
        </ul>
      </section>
      <section className="story-cta">
        <a className="button primary" href="/">Open the real PTEN workspace</a>
        <a className="button" href="/?workspace=fixture">Try the synthetic demo</a>
      </section>
    </main>
  </div>;
}
