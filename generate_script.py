# -*- coding: utf-8 -*-
"""
Escribe el guion del dia con IA (Gemini) siguiendo PROMPT-MAESTRO.md.
Se activa solo si existe GEMINI_API_KEY. Si falla algo, devuelve None
y el sistema usa el banco de guiones (scripts.json) como reserva.
Devuelve un dict con el mismo formato que usa generate.py.

CLAVE ANTI-REPETICION: cada dia se ASIGNA (no se sugiere) una escena, una
intencion y una estructura distinta y OBLIGATORIA, rotando de forma
determinista por fecha+run. Asi dos dias seguidos NUNCA salen iguales,
y el titulo se construye a partir de la escena/intencion de HOY.
"""
import os, sys, json, datetime, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("GEMINI_MODEL", "").strip()  # vacio = autodetectar modelo valido
_MODEL_CANDIDATES = [
    "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash",
    "gemini-2.5-flash-lite", "gemini-2.0-flash-001", "gemini-1.5-flash",
]
BGS = ["blue", "green", "orange", "purple", "teal", "red"]

# ---------------------------------------------------------------------------
# POOLS DE VARIEDAD (se asigna uno de cada por dia, no los elige la IA)
# Cada escena tiene algo de LUZ visible (vela, lampara, reflejos, luna...),
# nunca un cielo totalmente negro, para que el fondo se VEA y se distinga.
# ---------------------------------------------------------------------------
ESCENAS = [
    ("la lluvia contra la ventana con una lampara calida encendida dentro", "rainy window warm lamp cozy night"),
    ("una vela encendida temblando en una habitacion a oscuras",            "candle flame macro dark room"),
    ("la luna llena reflejada sobre un mar en calma",                       "full moon reflection calm sea night"),
    ("las brasas de una chimenea encendida de cerca",                       "fireplace embers close up cozy"),
    ("las luces de la ciudad desenfocadas tras un cristal con lluvia",      "city lights bokeh rain window night"),
    ("una aurora boreal moviendose sobre un lago",                          "aurora borealis over lake night"),
    ("la via lactea sobre la silueta de una montana",                      "milky way stars mountain silhouette"),
    ("una taza humeante junto a la ventana con la primera luz del alba",    "steaming cup window soft morning light"),
    ("la niebla moviendose entre los arboles con rayos de luz al amanecer", "misty forest morning sun rays"),
    ("las olas rompiendo despacio con la luz dorada del atardecer",         "ocean waves golden hour slow"),
    ("la nieve cayendo despacio bajo la luz de una farola",                 "snow falling under streetlight night"),
    ("un farolillo de papel flotando sobre el agua quieta",                 "floating paper lantern water night"),
    ("un campo de lavanda meciendose al atardecer",                        "lavender field sunset breeze"),
    ("la lluvia resbalando por las hojas de un jardin en penumbra",         "rain on green leaves garden dusk"),
    ("una hoguera pequena en una playa vacia de noche",                    "small beach bonfire night calm"),
    ("las luces calidas de un tren nocturno atravesando la noche",          "night train warm window lights"),
    ("un valle cubierto de niebla bajo las primeras luces del dia",         "foggy valley dawn soft light"),
    ("un muelle de madera sobre un lago en calma al amanecer",              "wooden dock calm lake dawn"),
    ("la luz de unas velas reflejada en el cristal de una copa",            "candlelight warm bokeh reflection"),
    ("un cielo con estrellas fugaces sobre las dunas de un desierto",       "shooting stars desert dunes night"),
]

INTENCIONES = [
    "soltar el trabajo que hoy no diste por terminado",
    "dejar de darle vueltas a algo que dijiste hoy",
    "perdonarte por un dia que no salio como querias",
    "agradecer una cosa pequena que te ha pasado hoy",
    "dejar ir una preocupacion que no depende de ti",
    "despedir el dia sin exigirte nada mas",
    "reconciliarte con el silencio de la casa",
    "aflojar el cuerpo poco a poco antes de dormir",
    "dejar lo de manana para manana",
    "hacer las paces con el cansancio de hoy",
    "soltar una conversacion que te quedo dando vueltas",
    "permitirte no hacer absolutamente nada por un minuto",
    "dejar que el dia se cierre solo, sin empujar",
    "quitarte de encima el peso de todo lo pendiente",
    "volver a tu respiracion y a este momento",
]

ESTRUCTURAS = [
    "respiracion guiada real: dirige una respiracion (4-7-8 o exhalacion larga) contando los tiempos con mucha calma",
    "sleep-story: un micro-relato en segunda persona DENTRO de la escena, que lleva poco a poco al sueno",
    "escena sensorial: describe la escena de HOY con los cinco sentidos y guia al cuerpo a soltarse en ella",
    "reflexion suave para soltar: una idea calmada sobre parar y permitirte descansar, sin dar consejos ni datos",
]

APERTURAS = ["Respira.", "Cierra los ojos.", "Baja el ritmo.", "Para un momento.",
             "Suelta el dia.", "Afloja los hombros.", "Quedate aqui.", "Respira hondo.",
             "Deja de correr.", "Suelta el aire."]
CIERRES  = ["Buenas noches.", "Descansa.", "Nos vemos manana.", "Duerme tranquilo.",
            "Hasta manana.", "Que descanses.", "Cierra los ojos.", "Ya puedes soltar."]


def _run_seed():
    try:
        return int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    except ValueError:
        return 0

def _daykey():
    # cambia cada dia (fecha) y tambien en cada run manual (run number)
    return datetime.date.today().toordinal() + _run_seed()

def _rot(lst, stride):
    return lst[(_daykey() * stride) % len(lst)]


def _list_models(key):
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
        "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]

def _call_gemini(prompt, key):
    last = None
    for model in _model_order(key):
        try:
            txt = _post_generate(model, prompt, key)
            sys.stderr.write(f"[ai] modelo usado: {model}\n")
            return txt
        except Exception as e:
            last = e
    raise RuntimeError(f"ningun modelo Gemini respondio: {last}")


_TITULOS_PROHIBIDOS = ("suelta el peso del dia", "suelta el peso del día",
                       "un minuto de calma", "tu momento de calma",
                       "respira y calmate", "respira asi")

def _validate(s, escena_es="", intencion="", broll_en=""):
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

    # --- TITULO: unico de hoy y NUNCA el generico repetido ---
    t = (s.get("title") or "").strip()
    low = t.lower()
    generico = (not t) or any(p in low for p in _TITULOS_PROHIBIDOS)
    if generico:
        base = (escena_es or "esta noche").strip()
        base = base[0].upper() + base[1:]
        if len(base) > 66:
            base = base[:66].rsplit(" ", 1)[0]
        s["title"] = f"{base} 🌙 #shorts"
    elif "#short" not in low:
        s["title"] = t + " #shorts"

    # --- DESCRIPCION: derivada de la escena/intencion si viene vacia ---
    if not (s.get("description") or "").strip():
        d = f"Un minuto para {intencion}." if intencion else "Tu minuto de calma de hoy."
        s["description"] = d + " Contenido de bienestar, no sustituye ayuda profesional."

    # --- BROLL: garantiza la escena de HOY como primer plano ---
    bl = s.get("broll_list")
    if not isinstance(bl, list) or not bl:
        bl = []
    if broll_en:
        bl = [broll_en] + [b for b in bl if isinstance(b, str) and b.strip()]
    bl = [b.strip() for b in bl if isinstance(b, str) and b.strip()][:4]
    if bl:
        s["broll_list"] = bl
        s["broll"] = bl[0]
    elif broll_en:
        s["broll_list"] = [broll_en]; s["broll"] = broll_en

    s["ai_disclosure"] = False
    s["id"] = "ia-" + datetime.date.today().isoformat()
    s.pop("chart", None)
    return s


def _schema(escena_es, intencion, estructura, broll_en, apertura, cierre):
    return f"""
Devuelve UNICAMENTE un JSON valido (sin texto alrededor) con esta forma exacta:
{{
  "title": "titulo calmado y bonito, UNICO de la escena de HOY. Construyelo a partir de la escena y la intencion de hoy. Max 80 caracteres, 1 emoji opcional, incluye #shorts. PROHIBIDO usar 'Suelta el peso del dia', 'Un minuto de calma' o cualquier titulo generico de otros dias.",
  "description": "2 frases suaves y DISTINTAS, sobre la escena de HOY y la intencion de HOY. Termina con: 'Contenido de bienestar, no sustituye ayuda profesional.'",
  "hashtags": ["Shorts", "relajacion", "calma", "dormir"],
  "bg": "uno de: blue, purple, teal, green (tonos nocturnos suaves)",
  "broll": "{broll_en}",
  "broll_list": ["{broll_en}", "y 2-3 planos EN INGLES mas de la MISMA escena o afines, todos CON algo de luz visible, nunca un cielo totalmente negro"],
  "ai_disclosure": false,
  "lines": [
    {{"voice": "frase corta, lenta y sensorial (numeros en palabras)", "cap": "subtitulo MUY corto (2-4 palabras, sin emojis)"}}
  ]
}}
GUION DE HOY - 'Un minuto de calma' (obligatorio, distinto a cualquier dia anterior):
- ESCENA DE HOY (usala como corazon del video): {escena_es}.
- INTENCION DE HOY (de que va la calma esta noche): {intencion}.
- ESTRUCTURA DE HOY: {estructura}.
- Entre 7 y 10 lineas. Cada 'voice' es una frase corta y sensorial (video de 30-45 s).
- NO es un tutorial: NO expliques, NO des consejos ni datos, NO uses 'sabias que', 'truco' ni 'top'. CREA una experiencia que se VIVE.
- APERTURA (linea 1): empieza con algo tipo "{apertura}" (una invitacion a parar, breve).
- CIERRE (ultima linea): despidete con algo tipo "{cierre}".
- Todo gira en torno a la ESCENA e INTENCION de HOY. El titulo y la descripcion deben dejar claro que HOY es distinto a cualquier otro dia.
- Segunda persona y presente ("escucha la lluvia", "suelta los hombros"). Espanol de Espana, muy suave y pausado.
- 'cap' sin emojis. 'voice' escribe los numeros con letras ('cuatro', no '4').
"""


def generate():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        master = open(os.path.join(BASE, "PROMPT-MAESTRO.md"), encoding="utf-8").read()
    except Exception:
        master = "Eres un creador experto de Shorts de relajacion y sueno en espanol de Espana."

    escena_es, broll_en = _rot(ESCENAS, 1)
    intencion = _rot(INTENCIONES, 7)
    estructura = _rot(ESTRUCTURAS, 3)
    apertura = _rot(APERTURAS, 5)
    cierre = _rot(CIERRES, 11)
    hoy = datetime.date.today().isoformat()

    prompt = (master
              + f"\n\n---\nTAREA DE HOY ({hoy}):\n"
              + "Crea la experiencia de calma de esta noche siguiendo EXACTAMENTE la escena, "
                "la intencion y la estructura que se te asignan abajo. No elijas otra escena.\n"
              + _schema(escena_es, intencion, estructura, broll_en, apertura, cierre))
    try:
        raw = _call_gemini(prompt, key)
        s = json.loads(raw)
        s = _validate(s, escena_es=escena_es, intencion=intencion, broll_en=broll_en)
        return s
    except Exception as e:
        sys.stderr.write(f"[ai] no se pudo generar con IA ({e}); se usara el banco.\n")
        return None


if __name__ == "__main__":
    import json as _j
    s = generate()
    print(_j.dumps(s, ensure_ascii=False, indent=2) if s else "None (sin GEMINI_API_KEY o error)")
