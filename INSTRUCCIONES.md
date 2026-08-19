# Guía de instalación — Catálogo automático (Telegram → GitHub Pages)

## 1. Credenciales de Telegram (API_ID / API_HASH)
1. Entra a https://my.telegram.org con tu número.
2. Ve a **API development tools**.
3. Crea una app (nombre y descripción, cualquier valor sirve).
4. Copia el `api_id` y `api_hash` que te muestra.

## 2. Repositorio en GitHub (la web)
1. Crea un repo nuevo, ej: `mi-catalogo`.
2. Clónalo en tu máquina: `git clone https://github.com/tu_usuario/mi-catalogo.git`
3. Copia dentro el contenido de la carpeta `web/` (index.html, style.css, script.js, productos.json, y crea una carpeta `img/` con un `placeholder.jpg`).
4. Haz commit y push inicial:
   ```
   git add .
   git commit -m "primer despliegue"
   git push origin main
   ```
5. En GitHub → Settings → Pages → Source: selecciona la rama `main` y carpeta `/root`. Guarda. Tu web quedará en `https://tu_usuario.github.io/mi-catalogo/`.

## 3. Configurar el bot en tu máquina
1. Instala Python 3.10+ y crea un entorno:
   ```
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # Mac/Linux
   pip install -r requirements.txt
   ```
2. Copia `.env.example` a `.env` y completa:
   - `API_ID`, `API_HASH`: los del paso 1.
   - `CANAL_1`, `CANAL_2`: usernames de los canales (`@canal`) o su ID numérico.
   - `REPO_PATH`: ruta absoluta a la carpeta del repo clonado en el paso 2 (donde está `productos.json`).
   - `GIT_BRANCH`: normalmente `main`.
3. Configura tu identidad de git una sola vez (si no lo has hecho):
   ```
   git config --global user.name "tu nombre"
   git config --global user.email "tu correo"
   ```
4. Para que `git push` no pida contraseña cada vez, usa un **Personal Access Token**:
   - GitHub → Settings → Developer settings → Personal access tokens → Generate new token (permiso `repo`).
   - Al hacer el primer `git push` manual desde `REPO_PATH`, usa ese token como contraseña. Git lo recordará (credential helper) para los próximos push automáticos del script.

## 4. Primera ejecución (crea la sesión de Telegram)
```
python bot.py
```
- La primera vez te pedirá tu número de teléfono y el código que llega por Telegram (una sola vez). Esto crea el archivo `sesion_dropshipping.session`, que reutiliza el login en adelante — no vuelve a pedir código.
- Déjalo corriendo. Cada vez que llegue un mensaje con foto+precio en los canales configurados, el bot:
  1. Suma $3.00 al precio detectado.
  2. Descarga la foto a `REPO_PATH/img/`.
  3. Actualiza `productos.json`.
  4. Hace `git commit` + `git push` automáticamente.
- GitHub Pages se actualiza solo (puede tardar 1–2 min en reflejarse).

## 5. Dejarlo corriendo todo el día
- Simplemente deja la terminal abierta con `python bot.py` corriendo.
- Opcional (Windows): usa el **Programador de tareas** para reiniciarlo si se cierra.
- Opcional (Mac/Linux): usa `nohup python bot.py &` o un servicio `systemd`/`launchd` para que sobreviva a cierres de sesión.

## 6. Personalizar tu número de WhatsApp
Edita en `web/script.js`:
```js
const NUMERO_WHATSAPP = "593999999999"; // tu número, código de país, sin '+' ni espacios
```
Vuelve a hacer push de ese archivo al repo.

## 7. Backfill automático (últimos 40 productos por canal)
Cada vez que arrancas `python bot.py`, antes de escuchar en vivo, el bot:
1. Recorre los **últimos 40 mensajes** de cada canal configurado.
2. Descarta duplicados (mismo nombre normalizado + mismo precio, sin importar el canal).
3. Agrega lo nuevo a `productos.json` y hace push — así la web se llena aunque los canales no publiquen nada nuevo hoy.

Esto corre siempre al inicio; si ya procesó todo antes, simplemente no encuentra nada nuevo y no hace push vacío.

## 8. Saber de qué canal viene cada producto (solo tú)
La web pública **nunca** muestra ni incluye el canal de origen — ni siquiera en el `productos.json` que cualquiera puede abrir. Ese dato se guarda aparte, en tu máquina, en:
```
canales_admin.json
```
(al lado de `bot.py`, **fuera** del repo de git, así que jamás se sube a GitHub). Ábrelo cuando quieras saber de qué proveedor es un pedido:
```json
{
  "-1001234567890_5821": {
    "canal": "@canal_proveedor_uno",
    "nombre": "Audífonos Bluetooth",
    "fecha": "2026-08-18T10:32:00"
  }
}
```
La clave (`-1001234567890_5821`) es el mismo `id` que ves en `productos.json`, así que puedes cruzar el pedido del cliente con este archivo para saber a quién comprarle.

## Notas importantes
- El regex de precio (`PRECIO_RE` en `bot.py`) es simple: detecta patrones como `$12.50`, `12,50$`, `12.50 usd`. Si tus proveedores usan otro formato, ajusta esa expresión regular.
- Si un mensaje no tiene precio detectable o no trae foto, se ignora (no rompe el bot).
- El costo de infraestructura es $0: Telethon corre en tu PC, GitHub y GitHub Pages son gratuitos para repos públicos.
- Nunca subas `canales_admin.json` ni `.env` a git (ambos contienen datos privados/credenciales).
