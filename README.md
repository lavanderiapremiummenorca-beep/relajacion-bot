# 🤖 Calma en 30s — Shorts automaticos y gratis

Genera y publica un Short de relajacion y bienestar al dia en YouTube, en automatico y sin pagar suscripciones.

- **Voz:** edge-tts (neuronal, gratis) en GitHub Actions · voz configurada: `es-ES-ElviraNeural`
- **Video:** ffmpeg (fondo con movimiento + subtitulos sincronizados)
- **Subida:** API de datos de YouTube
- **Programador:** GitHub Actions (cron diario), gratis

## Como funciona
1. `generate.py` elige el guion del dia (IA con Gemini, o el banco `scripts.json` si no hay clave), crea la voz, los subtitulos y monta el video vertical en `output/`.
2. `upload.py` sube ese video a tu canal de YouTube.
3. El workflow `.github/workflows/daily.yml` hace las dos cosas cada dia (~22:51 Espana).

## Secrets (en GitHub -> Settings -> Secrets -> Actions)
Obligatorios (subida a YouTube):
- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`
- `CHANNEL_HANDLE` — tu @handle para la marca de agua (ej. `@CalmaEn30s`)

Recomendados (mejoran el resultado, se activan solos):
- `GEMINI_API_KEY` — la IA escribe el guion cada dia siguiendo `PROMPT-MAESTRO.md` (se puede reutilizar la misma de tus otros canales)
- `PIXABAY_API_KEY` y/o `PEXELS_API_KEY` — fondo de video real (reutilizables)

## Cambiar la voz
Edita `EDGE_VOICE` en `.github/workflows/daily.yml`. Voces de Espana: `es-ES-AlvaroNeural` (hombre), `es-ES-ElviraNeural` (mujer). LATAM: `es-MX-JorgeNeural`, `es-MX-DaliaNeural`. Si una voz da error, vuelve a Alvaro/Elvira.

## Anadir mas temas al banco
Abre `scripts.json` y anade otro bloque con el mismo formato. Cuantos mas guiones, menos se repite el contenido si algun dia falla la IA.
