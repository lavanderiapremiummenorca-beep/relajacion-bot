# -*- coding: utf-8 -*-
"""
Escribe el guion del dia con IA (Gemini) siguiendo PROMPT-MAESTRO.md.
Se activa solo si existe GEMINI_API_KEY. Si falla algo, devuelve None
y el sistema usa el banco de guiones (scripts.json) como reserva.
Devuelve un dict con el mismo formato que usa generate.py.
"""
import os, sys, json, datetime, random, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("GEMINI_MODEL", "").strip()  # vacio = autodetectar modelo valido
# Candidatos por si ListModels no responde (de mas nuevo a mas compatible).
_MODEL_CANDIDATES = [
    "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash",
    "gemini-2.5-flash-lite", "gemini-2.0-flash-001", "gemini-1.5-flash",
]
BGS = ["blue", "green", "orange", "purple", "teal", "red"]

# Temas y formatos que rotan por dia para no repetir (anti "contenido inautentico")
TEMAS = [
    "la respiracion 4-7-8",
    "la respiracion cuadrada",
    "relajar los hombros y la mandibula",
    "la tecnica 5-4-3-2-1",
    "una rutina para dormir mejor",
    "la luz azul y el sueno",
    "el habito de la gratitud",
    "la pausa consciente de un minuto",
    "el escaneo corporal",
    "caminar de forma consciente",
    "desconectar del movil",
    "como acompanar la ansiedad",
    "alargar la exhalacion para calmarte",
    "la temperatura ideal para dormir",
    "soltar la tension del cuerpo",
    "el poder de parar un momento",
    "aceptar los pensamientos sin luchar",
    "crear un rincon de calma",
    "la respiracion antes de dormir",
    "reducir el ritmo del dia"
]
FORMATOS = [
    "mito vs realidad", "un dato sorprendente con ejemplo numerico",
    "el error comun que casi todos cometen", "top 3 rapido",
    "esto no te lo cuentan", "comparativa antes vs despues",
    "una pregunta que pica la curiosidad y su respuesta",
]

SCHEMA_INSTRUCCION = """
Devuelve UNICAMENTE un JSON valido (sin texto alrededor) con esta forma exacta:
{
  "title": "titulo honesto y con gancho, max 90 caracteres, puede llevar 1 emoji y #shorts",
  "description": "1-2 frases de valor + CTA. Anade al final: 'Contenido de bienestar, no sustituye ayuda profesional.'",
  "hashtags": ["Shorts", "relajacion", "bienestar", "calma"],  // 3 a 5, sin '#', el primero SIEMPRE 'Shorts'
  "bg": "uno de: blue, green, orange, purple, teal, red",
  "broll": "2-4 palabras EN INGLES para metraje de archivo (ej: 'calm nature water')",
  "ai_disclosure": false,
  "lines": [
    {"voice": "frase corta que se narra (con numeros en palabras: 'cien euros', no '100')",
     "cap": "subtitulo MUY corto en pantalla (2-4 palabras, puede llevar cifras)"}
  ]
}
Reglas del guion:
- Entre 10 y 13 lineas. Cada 'voice' es una frase corta y natural (el video debe durar 20-40 s).
- La PRIMERA linea es el gancho: sin saludos ni intro, engancha en el primer segundo.
- La ULTIMA linea es el CTA: invita a seguir ("Sigueme para tu momento de calma diario") o a comentar.
- 'cap' nunca lleva emojis (la fuente no los dibuja). 'voice' escribe los numeros con letras.
- Espanol, tono suave, calmado y pausado. Transmite paz, sin prisa.
"""

def _run_seed():
    try:
        return int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    except ValueError:
        return 0

def _pick(lst, salt=0):
    y = datetime.date.today().timetuple().tm_yday
    return lst[(y + _run_seed() + salt) % len(lst)]

def _list_models(key):
    """Pregunta a Google que modelos existen de verdad para esta clave."""
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/models"
               f"?key={key}&pageSize=200")
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
        out = []
        for m in data.get("models", []):
            if "generateContent" in (m.get("supportedGenerationMethods") or []):
                out.append(m.get("name", "").replace("models/", ""))
        return out
    except Exception:
        return []

def _model_order(key):
    """Orden a probar: modelo forzado por env -> candidatos -> los reales
    de la cuenta (priorizando 'flash')."""
    order = []
    if MODEL:
        order.append(MODEL)
    for m in _MODEL_CANDIDATES:
        if m not in order:
            order.append(m)
    disc = _list_models(key)
    for m in disc:
        if "flash" in m and m not in order:
            order.append(m)
    for m in disc:
        if m not in order:
            order.append(m)
    return order

def _post_generate(model, prompt, key):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.95, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]

def _call_gemini(prompt, key):
    """Prueba varios modelos y usa el primero que responda (sobrevive a que
    Google jubile un modelo). Solo falla si NINGUNO funciona."""
    last = None
    for model in _model_order(key):
        try:
            txt = _post_generate(model, prompt, key)
            sys.stderr.write(f"[ai] modelo usado: {model}\n")
            return txt
        except Exception as e:
            last = e
    raise RuntimeError(f"ningun modelo Gemini respondio: {last}")

def _validate(s):
    assert isinstance(s.get("lines"), list) and 6 <= len(s["lines"]) <= 16, "lineas fuera de rango"
    for ln in s["lines"]:
        assert ln.get("voice"), "linea sin voz"
        ln.setdefault("cap", "")
    s.setdefault("bg", "blue")
    if s["bg"] not in BGS:
        s["bg"] = "blue"
    hs = [h.lstrip("#") for h in s.get("hashtags", []) if h.strip()]
    if not hs or hs[0].lower() != "shorts":
        hs = ["Shorts"] + [h for h in hs if h.lower() != "shorts"]
    s["hashtags"] = hs[:5]
    assert s.get("title"), "sin titulo"
    s.setdefault("description", "Un momento de calma en 30 segundos. Contenido de bienestar, no sustituye ayuda profesional.")
    s["id"] = "ia-" + datetime.date.today().isoformat()
    s.pop("chart", None)
    return s

def generate():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        master = open(os.path.join(BASE, "PROMPT-MAESTRO.md"), encoding="utf-8").read()
    except Exception:
        master = "Eres un productor experto de YouTube Shorts de relajacion y bienestar en espanol."
    formato = random.choice(FORMATOS)
    hoy = datetime.date.today().isoformat()
    # Usamos TEMAS solo como "lo obvio a EVITAR", para empujar novedad
    evitar = ", ".join(random.sample(TEMAS, min(6, len(TEMAS)))) if TEMAS else ""
    seed = _run_seed()
    prompt = (master
              + f"\n\n---\nTAREA DE HOY ({hoy}):\n"
              + "ELIGE TU MISMO un tema NUEVO, especifico y original dentro de la tematica "
                "de ESTE canal (segun las instrucciones de arriba). Sorprendeme con un angulo "
                "fresco y concreto; evita los topicos mas manidos y ya vistos.\n"
              + (f"Para forzar variedad, HOY NO trates sobre estos (elige algo distinto): {evitar}.\n" if evitar else "")
              + f"Desarrollalo con este enfoque/formato: {formato}.\n"
              + "Debe ser un tema DISTINTO cada dia; se original.\n"
              + "Cumple TODAS las reglas de arriba (cumplimiento primero, luego viralidad).\n"
              + SCHEMA_INSTRUCCION)
    try:
        raw = _call_gemini(prompt, key)
        s = json.loads(raw)
        s = _validate(s)
        return s
    except Exception as e:
        sys.stderr.write(f"[ai] no se pudo generar con IA ({e}); se usara el banco.\n")
        return None

if __name__ == "__main__":
    import json as _j
    s = generate()
    print(_j.dumps(s, ensure_ascii=False, indent=2) if s else "None (sin GEMINI_API_KEY o error)")
