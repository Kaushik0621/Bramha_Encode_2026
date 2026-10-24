"""Cache allowlisted source assets, reporting blocked downloads without fabricating success."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import httpx

root = Path(__file__).resolve().parents[1]
manifest = root / "backend/app/blood/sources.json"
sources = json.loads(manifest.read_text())
for source in sources:
    urls = [source["url"]]
    if source["id"] == "abo-reference":
        urls += ["https://www.ncbi.nlm.nih.gov/books/NBK2267/pdf/"]
    if source["id"] == "rhd-reference":
        urls += ["https://www.ncbi.nlm.nih.gov/books/NBK2269/pdf/ch07Rh.pdf"]
    source.pop("asset",None)
    source["download_status"] = "unavailable"
    if source["id"] in ("rowe-2007","kenya-2023","india-2011"):
        pmc={"rowe-2007":"PMC2077280","kenya-2023":"PMC10522014","india-2011":"PMC3215225"}[source["id"]]
        urls.append("https://www.ebi.ac.uk/europepmc/webservices/rest/"+pmc+"/fullTextXML")
    for url in urls:
        try:
            response = httpx.get(url, follow_redirects=True, timeout=30)
            response.raise_for_status()
            if (
                "Checking your browser" in response.text[:30000]
                or len(response.content) < 5000
            ):
                raise ValueError("Source challenge or incomplete download")
            digest = hashlib.sha256(response.content).hexdigest()
            path = (
                root
                / "data/assets/blood"
                / (
                    digest
                    + (".pdf" if response.content.startswith(b"%PDF") else ".xml" if "fullTextXML" in url else ".html")
                )
            )
            path.write_bytes(response.content)
            source["asset"] = {
                "sha256": digest,
                "path": str(path.relative_to(root)),
                "bytes": len(response.content),
                "format": "PDF" if response.content.startswith(b"%PDF") else "XML" if "fullTextXML" in url else "HTML",
                "retrieval_url": str(response.url),
            }
            source["download_status"] = "cached"
            break
        except (ValueError, httpx.HTTPError):
            pass
    source["download_checked_at"] = datetime.now(timezone.utc).isoformat()
    print(source["id"], source["download_status"])
manifest.write_text(json.dumps(sources, indent=2))
