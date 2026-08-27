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

# ESCENAS nocturnas que rotan por dia (para que cada noche sea una imagen distinta)
TEMAS = [
    "lluvia suave contra la ventana de noche",
    "una vela encendida en una habitacion a oscuras",
    "el mar en calma bajo la luna",
    "un bosque con niebla al amanecer",
    "una cabana de montana con la chimenea encendida",
    "un cielo lleno de estrellas en el campo",
    "un tren nocturno atravesando la noche",
    "olas suaves rompiendo despacio en la orilla",
    "un jardin en silencio al anochecer",
    "la nieve cayendo despacio tras el cristal",
    "una taza humeante junto a una ventana lluviosa",
    "un lago quieto reflejando el atardecer",
    "las hojas moviendose con el viento suave",
    "una tormenta lejana con truenos suaves",
    "la luz calida de una lampara al final del dia",
]
# ESTILOS que se intercalan cada dia (experiencia, no tutorial)
FORMATOS = [
    "experiencia inmersiva: describe una escena nocturna y guia al cuerpo a soltarse en ella",
    "respiracion guiada real: dirige una respiracion (4-7-8, cuadrada o exhalacion larga) contando los tiempos con calma",
    "sleep story: un micro-relato onirico en segunda persona que lleva poco a poco al sueno",
    "ambiente: evoca un lugar para dormir o descansar y describelo con los cinco sentidos",
    "reflexion para soltar el dia: una idea calmada sobre parar y permitirse descansar, sin dar consejos",
]

SCHEMA_INSTRUCCION = """
Devuelve UNICAMENTE un JSON valido (sin texto alrededor) con esta forma exacta:
{
  "title": "titulo calmado y bonito, UNICO de la escena de hoy (max 90 caracteres, 1 emoji opcional, #shorts). Nunca generico ni repetido.",
  "description": "2 frases suaves y DISTINTAS cada dia, sobre la escena concreta de hoy. Anade al final: 'Contenido de bienestar, no sustituye ayuda profesional.'",
  "hashtags": ["Shorts", "relajacion", "calma", "dormir"],  // 3 a 5, sin '#', el primero SIEMPRE 'Shorts'
  "bg": "uno de: blue, purple, teal, green (tonos nocturnos y suaves)",
  "broll": "2-4 palabras EN INGLES de la escena nocturna (ej: 'rain window night')",
  "broll_list": ["3 o 4 escenas EN INGLES para el fondo, en orden (ej: 'rain window night', 'candle flame dark', 'calm ocean moon')"],
  "ai_disclosure": false,
  "lines": [
    {"voice": "frase corta y suave que se narra (numeros en palabras: 'cuatro', no '4')",
     "cap": "subtitulo MUY corto en pantalla (2-4 palabras)"}
  ]
}
Reglas del guion (formato 'Un minuto de calma'):
- Entre 7 y 10 lineas. Cada 'voice' es una frase corta, lenta y sensorial (el video dura 30-45 s).
- ESTO NO ES UN TUTORIAL: NO expliques, NO des consejos ni datos, NO uses 'sabias que', 'truco' ni 'top 3'. Se trata de CREAR una experiencia que el espectador VIVE, no de contarle un tema.
- APERTURA (linea 1): una invitacion a parar, DISTINTA cada dia. Rota entre formulas como "Respira.", "Cierra los ojos.", "Baja el ritmo.", "Para un momento.", "Suelta el dia.", "Afloja los hombros." Reconocible como el canal, pero NUNCA identica a la de ayer.
- CIERRE (ultima linea): una despedida suave que invite a descansar o volver, tambien VARIADA: "Buenas noches.", "Descansa.", "Nos vemos manana.", "Duerme tranquilo.", "Hasta manana." Nunca la misma de ayer.
- VARIEDAD OBLIGATORIA: titulo, descripcion, escena, apertura, cierre y frases deben ser CLARAMENTE DISTINTOS a cualquier video anterior. Si se parece a uno de ayer, cambialo entero. La escena concreta de HOY manda: todo gira en torno a ELLA.
- Habla en segunda persona y en presente ("suelta los hombros", "escucha la lluvia"). Cercano, calido, sin prisa.
- 'cap' nunca lleva emojis (la fuente no los dibuja). 'voice' escribe los numeros con letras.
- Espanol de Espana, tono muy suave, pausado y envolvente; frases que respiran, con silencios implicitos.
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
    if not (s.get("description") or "").strip():
        _first = (s["lines"][0].get("voice", "") if s.get("lines") else "").strip()
        s["description"] = (_first[:110] or "Tu minuto de calma de hoy.") + " Contenido de bienestar, no sustituye ayuda profesional."
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
              + "CREA una experiencia de calma NUEVA y original para esta noche. "
                "Elige tu misma una ESCENA nocturna concreta y sensorial (una imagen bonita, "
                "no un tema de consejo).\n"
              + (f"Para forzar variedad, esta noche NO uses estas escenas (elige otra distinta): {evitar}.\n" if evitar else "")
              + f"Trabaja la experiencia con este ESTILO de hoy: {formato}.\n"
              + "El estilo se intercala cada dia; hoy toca EXACTAMENTE el de arriba.\n"
              + "Apertura y cierre VARIADOS (no repitas los de ayer). Titulo y descripcion UNICOS de la escena de hoy.\n"
              + "Nada de tutoriales ni consejos. Que HOY se note claramente distinto a cualquier dia anterior.\n"
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
