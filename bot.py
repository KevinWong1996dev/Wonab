"""
Bot de dropshipping automatizado.
- Al arrancar: trae los últimos N mensajes de cada canal (backfill) para poblar
  la web de inmediato, sin esperar publicaciones nuevas.
- En vivo: escucha mensajes nuevos y hace lo mismo.
- Extrae producto (foto+precio+desc), suma margen fijo, evita duplicados
  entre canales, guarda productos.json (público, SIN dato de canal) y hace
  commit+push a GitHub.
- El canal real de cada producto se guarda SOLO localmente en
  canales_admin.json (nunca se sube al repo), para que tú puedas identificar
  el origen sin exponerlo en la web pública.

Requisitos:
    pip install telethon python-dotenv
"""

import os
import re
import json
import asyncio
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

# ---------- CONFIG ----------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "sesion_dropshipping"

CANALES = [c for c in [os.getenv("CANAL_1"), os.getenv("CANAL_2")] if c]

MARGEN_USD = 3.00
LIMITE_BACKFILL = 40  # últimos N mensajes por canal al arrancar

REPO_PATH = os.getenv("REPO_PATH")
JSON_PATH = os.path.join(REPO_PATH, "productos.json")
IMG_DIR = os.path.join(REPO_PATH, "img")
GIT_BRANCH = os.getenv("GIT_BRANCH", "main")

# Archivo PRIVADO (junto al script, nunca dentro del repo git) con el canal real
ADMIN_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canales_admin.json")

os.makedirs(IMG_DIR, exist_ok=True)
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

PRECIO_RE = re.compile(r"(?:\$|usd)?\s?(\d+(?:[.,]\d{1,2})?)\s?(?:\$|usd)?", re.IGNORECASE)


def extraer_precio(texto: str):
    if not texto:
        return None
    match = PRECIO_RE.search(texto)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def limpiar_descripcion(texto: str, precio_str: str) -> str:
    if not texto:
        return "Producto disponible"
    texto = texto.replace(precio_str, "").strip()
    return " ".join(texto.split())[:200]


def normalizar(nombre: str) -> str:
    """Para comparar duplicados: minúsculas, sin puntuación ni espacios extra."""
    return re.sub(r"[^a-z0-9áéíóúñ]+", "", nombre.lower())


# ---------- persistencia pública ----------
def cargar_productos():
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def guardar_productos(productos):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)


# ---------- registro privado de canal (NO se sube a git) ----------
def cargar_admin():
    if os.path.exists(ADMIN_LOG_PATH):
        with open(ADMIN_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_admin(registro):
    with open(ADMIN_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)


def registrar_origen(producto_id: str, canal: str, nombre: str):
    registro = cargar_admin()
    registro[producto_id] = {
        "canal": canal,
        "nombre": nombre,
        "fecha": datetime.now().isoformat(timespec="seconds"),
    }
    guardar_admin(registro)


def git_push():
    try:
        subprocess.run(["git", "add", "productos.json", "img"], cwd=REPO_PATH, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Auto-update catálogo {datetime.now():%Y-%m-%d %H:%M}"],
            cwd=REPO_PATH, check=True
        )
        subprocess.run(["git", "push", "origin", GIT_BRANCH], cwd=REPO_PATH, check=True)
        print("✔ Push realizado.")
    except subprocess.CalledProcessError as e:
        print(f"⚠ Git (probablemente nada que subir): {e}")


async def construir_producto(msg, chat_id, canal_label):
    """Devuelve el dict público del producto o None si no aplica."""
    texto = msg.message or ""
    precio_base = extraer_precio(texto)
    if precio_base is None or not msg.photo:
        return None

    precio_final = round(precio_base + MARGEN_USD, 2)
    match = PRECIO_RE.search(texto)
    descripcion = limpiar_descripcion(texto, match.group(0))
    nombre = descripcion.split(".")[0][:60] or "Producto"

    filename = f"{chat_id}_{msg.id}.jpg"
    ruta_local = await client.download_media(msg, file=os.path.join(IMG_DIR, filename))
    if not ruta_local:
        return None

    producto_id = f"{chat_id}_{msg.id}"
    producto = {
        "id": producto_id,
        "nombre": nombre,
        "descripcion": descripcion,
        "precio": precio_final,
        "imagen": f"img/{filename}",
        "fecha": datetime.now().isoformat(timespec="seconds"),
    }
    registrar_origen(producto_id, canal_label, nombre)  # solo local, no público
    return producto


def es_duplicado(existentes_norm, producto):
    clave = (normalizar(producto["nombre"]), producto["precio"])
    return clave in existentes_norm


async def backfill_historial():
    """Trae los últimos LIMITE_BACKFILL mensajes de cada canal para poblar la web ya mismo."""
    productos = cargar_productos()
    ids_existentes = {p["id"] for p in productos}
    claves_norm = {(normalizar(p["nombre"]), p["precio"]) for p in productos}
    nuevos = 0

    for canal in CANALES:
        try:
            entidad = await client.get_entity(canal)
        except Exception as e:
            print(f"⚠ No se pudo resolver el canal {canal}: {e}")
            continue

        async for msg in client.iter_messages(entidad, limit=LIMITE_BACKFILL):
            producto_id = f"{entidad.id}_{msg.id}"
            if producto_id in ids_existentes:
                continue

            producto = await construir_producto(msg, entidad.id, canal_label=canal)
            if producto is None:
                continue
            if es_duplicado(claves_norm, producto):
                print(f"↷ Duplicado omitido: {producto['nombre']}")
                continue

            productos.append(producto)
            ids_existentes.add(producto_id)
            claves_norm.add((normalizar(producto["nombre"]), producto["precio"]))
            nuevos += 1

    if nuevos:
        # más recientes primero
        productos.sort(key=lambda p: p["fecha"], reverse=True)
        guardar_productos(productos)
        git_push()
        print(f"✔ Backfill completo: {nuevos} productos nuevos.")
    else:
        print("✔ Backfill completo: nada nuevo que agregar.")


@client.on(events.NewMessage(chats=CANALES if CANALES else None))
async def handler(event):
    msg = event.message
    canal_label = (event.chat.username and f"@{event.chat.username}") or str(event.chat_id)

    productos = cargar_productos()
    ids_existentes = {p["id"] for p in productos}
    producto_id = f"{event.chat_id}_{msg.id}"
    if producto_id in ids_existentes:
        return

    producto = await construir_producto(msg, event.chat_id, canal_label)
    if producto is None:
        return

    claves_norm = {(normalizar(p["nombre"]), p["precio"]) for p in productos}
    if es_duplicado(claves_norm, producto):
        print(f"↷ Duplicado omitido: {producto['nombre']}")
        return

    productos.insert(0, producto)
    guardar_productos(productos)
    git_push()
    print(f"✔ Producto agregado: {producto['nombre']} -> ${producto['precio']}")


async def main():
    await client.start()
    print("Haciendo backfill inicial de los canales...")
    await backfill_historial()
    print("Bot escuchando canales en vivo... (Ctrl+C para salir)")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
