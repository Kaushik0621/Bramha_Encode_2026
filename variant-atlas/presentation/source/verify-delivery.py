from pathlib import Path
import json,re,hashlib,zipfile
from datetime import datetime, timezone
from pptx import Presentation
import pymupdf
root=Path(__file__).resolve().parents[1]
ppt=Presentation(root/'Bramha-Atlas-Pitch.pptx')
pdf=pymupdf.open(root/'Bramha-Atlas-Pitch.pdf')
scene=json.loads((root/'source/scene.json').read_text())
norm=lambda x:re.sub(r'\s+','',x).replace('\u00ad','')
missing=[]
for i,sc in enumerate(scene):
 page=norm(pdf[i].get_text())
 for obj in sc['objects']:
  if obj['kind']=='text' and norm(obj['text']) not in page:missing.append({'slide':i+1,'text':obj['text']})
charts=[sh.chart for s in ppt.slides for sh in s.shapes if sh.has_chart]
ref=json.loads((root/'source/reference-check.json').read_text())
expected={v['protein_hgvs'].removeprefix('p.'):v for v in ref['variants']}
for series in charts[0].series:
 assert abs(series.values[0]-expected[series.name]['abundance'])<1e-14
 assert abs(float(series._element.xpath('./c:xVal/c:numRef/c:numCache/c:pt/c:v')[0].text)-expected[series.name]['activity'])<1e-14
assert len(ppt.slides)==len(pdf)==len(scene)==19
for i,slide in enumerate(ppt.slides,1):
 for sh in slide.shapes:
  assert sh.left>=0 and sh.top>=0 and sh.left+sh.width<=ppt.slide_width+10 and sh.top+sh.height<=ppt.slide_height+10,(i,sh.name)
assert len(ppt.slides[5].shapes)>300
assert all(any(sh.shape_type==5 for sh in ppt.slides[i].shapes) for i in [2,7,9])
assert len(charts)==1
assert all(s.has_notes_slide and len(s.notes_slide.notes_text_frame.text)>200 for s in ppt.slides)
assert not missing,missing
browser=json.loads((root/'demo-browser-check.json').read_text())
assert not browser['errors'] and not browser['model_start_requests'] and not browser['mobile_overflow']
result={
 'checked_at':datetime.now(timezone.utc).isoformat(),
 'pptx_slides':len(ppt.slides),'pdf_pages':len(pdf),
 'aspect_ratio':'16:9','native_chart_count':len(charts),
 'native_chart_measurements_match_reference':True,
 'speaker_notes_present_on_all_slides':True,
 'visible_text_found_in_native_pdf':True,
 'out_of_bounds_shapes':[],
 'editable_3d_diagram_slides':[3,6,8,10,14],
 'scientific_3d_trace':'307 accepted experimental C-alpha coordinates; rigid view projection; unobserved gaps not connected',
 'render_engine':'Microsoft PowerPoint for Mac — native PDF export',
 'visual_review':'All 19 slides rendered; dimensional workflow, actual-coordinate molecular trace, agent network and layered architecture inspected.',
 'demo_browser':'Saved baseline/follow-up links verified; no model-start request; desktop, mobile and dark-theme entry captured.',
 'frontend_build':'npm run build passed; existing large scientific-library chunk advisory remains.',
 'market_model':'Customer and market arithmetic checked; sourced company reference pool; time, fit and price assumptions explicit.',
 'scientific_scope':'Saved public-data artifact inspection and exact chart comparison; no new biological validation or live model call.',
 'remaining_limitations':['Argon scientific execution remains unverified.','Selected PTEN example demonstrates a criterion change, not autonomous limitation-driven hypothesis revision.','Pricing, pilot size and revenue arithmetic are assumptions.','Project investigations remain local; public corpus is stored in Atlas.']}
(root/'verification.json').write_text(json.dumps(result,indent=2))
manifest=[]
for p in sorted(root.rglob('*')):
 if p.is_file() and 'previous-2d' not in p.parts and '__pycache__' not in p.parts and not p.name.startswith('~$') and p.name not in ['asset-manifest.json','Bramha-Atlas-Presentation.zip']:
  manifest.append({'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(root/'asset-manifest.json').write_text(json.dumps({'files':manifest,'image_usage':'source/asset-usage.json','claim_sources':'claim-source-ledger.json'},indent=2))
print('19 slides/pages, notes, exact native chart data, PDF text and browser checks passed.')
