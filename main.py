# main.py
from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

app = FastAPI(title="imgTagWrapperId Extractor API", version="1.1.0")

UA_DEFAULT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/115 Safari/537.36")

class ExtractRequest(BaseModel):
    url: HttpUrl
    userAgent: str | None = None
    timeoutMs: int = 15000

class ExtractResponse(BaseModel):
    originalUrl: str
    finalUrl: str | None = None
    status: str
    notes: str | None = None

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/extract", response_model=ExtractResponse)
async def extract(req: ExtractRequest):
    headers = {
        "User-Agent": req.userAgent or UA_DEFAULT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Connection": "close",
    }
    timeout = httpx.Timeout(req.timeoutMs / 1000.0)

    try:
        async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=timeout) as client:
            res = await client.get(str(req.url))
            # Casos típicos de bloqueo
            if res.status_code in (401, 403, 451):
                return ExtractResponse(originalUrl=str(req.url), status="ACCESO_RESTRINGIDO", notes=f"HTTP {res.status_code}")
            if res.status_code >= 500:
                return ExtractResponse(originalUrl=str(req.url), status="ERROR_CARGA", notes=f"HTTP {res.status_code}")

            html = res.text
    except httpx.RequestError as e:
        return ExtractResponse(originalUrl=str(req.url), status="ERROR_CARGA", notes=str(e))

    soup = BeautifulSoup(html, "html.parser")

    # Tomar el PRIMER <div id="imgTagWrapperId">
    div = soup.find("div", id="imgTagWrapperId")
    if not div:
        return ExtractResponse(originalUrl=str(req.url), status="NO_ENCONTRADO", notes="No existe div#imgTagWrapperId")

    # Dentro, tomar el PRIMER <img> anidado (a cualquier profundidad)
    img = div.find("img")
    if not img or not img.get("src"):
        return ExtractResponse(originalUrl=str(req.url), status="NO_ENCONTRADO", notes="Sin <img> o sin src")

    src = img.get("src")
    final_url = urljoin(str(req.url), src)  # resolver relativo→absoluto
    return ExtractResponse(originalUrl=str(req.url), finalUrl=final_url, status="OK")
