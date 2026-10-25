from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
with zipfile.ZipFile(root/'Bramha-Atlas-Presentation.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(root.rglob('*')):
  if p.is_file() and 'previous-2d' not in p.parts and '__pycache__' not in p.parts and not p.name.startswith('~$') and p.name!='Bramha-Atlas-Presentation.zip':
   z.write(p,Path('Bramha-Atlas-Presentation')/p.relative_to(root))
print('Packaged the revised 3D presentation and reproducible sources.')
