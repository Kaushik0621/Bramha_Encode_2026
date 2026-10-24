"""Build a labelled display projection from audited experimental C-alpha coordinates.

No coordinates are changed or interpolated. Consecutive accepted residues only
are connected. This is a fallback trace, never a mutant fold or a ribbon model.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
audit_path = ROOT / "data/manifests/pten-mapping-audit.json"
audit = json.loads(audit_path.read_text())
rows = audit["structure"]["mappings"]
if isinstance(rows, dict):
    rows = list(rows.values())
rows = [r for r in rows if r["status"] == "mapped" and r.get("coordinate")]
# A fixed orthographic x/z projection of accepted reference coordinates.
points = [
    (
        r,
        r["coordinate"]["x"] + 0.25 * r["coordinate"]["y"],
        -r["coordinate"]["z"] + 0.28 * r["coordinate"]["y"],
    )
    for r in rows
]
xmin, xmax = min(x for _, x, _ in points), max(x for _, x, _ in points)
ymin, ymax = min(y for _, _, y in points), max(y for _, _, y in points)
scale = min(500 / (xmax - xmin), 460 / (ymax - ymin))
project = lambda x, y: (
    300 + (x - (xmin + xmax) / 2) * scale,
    270 + (y - (ymin + ymax) / 2) * scale,
)
svg = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 540" role="img" aria-labelledby="title desc">',
    '<title id="title">PTEN 1D5R experimental reference trace</title>',
    '<desc id="desc">Derived two-dimensional C-alpha trace of accepted mappings. Gaps are unconnected. No mutant geometry is predicted.</desc>',
]
for (a, x, y), (b, u, v) in zip(points, points[1:]):
    if b["reference_position"] != a["reference_position"] + 1:
        continue
    px, py = project(x, y)
    qx, qy = project(u, v)
    svg.append(
        f'<path d="M{px:.2f},{py:.2f} L{qx:.2f},{qy:.2f}" fill="none" stroke="#70b8b6" stroke-width="3.5" stroke-linecap="round" opacity=".8"/>'
    )
for r, x, y in points:
    if r["reference_position"] == 124:
        px, py = project(x, y)
        svg.append(
            f'<circle cx="{px:.2f}" cy="{py:.2f}" r="7" fill="#e6b87e"/><circle cx="{px:.2f}" cy="{py:.2f}" r="15" fill="none" stroke="#e6b87e" opacity=".45"/>'
        )
svg.append("</svg>")
out = ROOT / "frontend/public/reference"
out.mkdir(parents=True, exist_ok=True)
(out / "pten-1d5r-trace.svg").write_text("\n".join(svg) + "\n")
(out / "provenance.json").write_text(
    json.dumps(
        {
            "asset": "pten-1d5r-trace.svg",
            "kind": "derived orthographic C-alpha trace",
            "source": "1D5R experimental structure, audited canonical mappings",
            "dataset_version": audit["dataset_version"],
            "mapping_audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
            "accepted_coordinates": len(points),
            "projection": "x + 0.25*y; -z + 0.28*y; uniform display scale",
            "gap_policy": "connect consecutive accepted canonical positions only",
            "replacement": "python scripts/build_reference_fallback.py; live renderer loads /api/structures/1D5R",
            "placeholder": False,
        },
        indent=2,
    )
    + "\n"
)
print(f"Built derived fallback from {len(points)} accepted reference coordinates.")
