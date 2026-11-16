"""Sube las fotos del calendario al almacén privado de Supabase.

Uso:
    python herramientas/subir_fotos.py [carpeta]      (por defecto: fotos/)

En la carpeta, el número del día es el primer número del nombre del archivo:
    1.jpg, 03-playa.png, "dia 12.jpeg"...  → día 1, 3, 12.

Cada foto se endereza (según el giro que guarda el móvil), se reduce a 1600 px de lado
largo, se le quitan los metadatos (fecha, ubicación GPS...) y se sube como dia-NN.jpg.
Si ya había una foto para ese día, se cambia por la nueva.

Pide el usuario y la contraseña de la cuenta admin (o los lee de CALENDARIO_USUARIO
y CALENDARIO_CLAVE). La carpeta fotos/ está en .gitignore: las fotos nunca van al repositorio.
"""
import getpass
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

SUPABASE_URL = 'https://dwaibpjeridzinrnbnao.supabase.co'
SUPABASE_CLAVE = 'sb_publishable_Y4zCN9Blqi2Q2ta0rPp_lg_SlbJ4Zup'  # pública a propósito
DOMINIO_USUARIOS = 'josecs5.github.io'  # igual que en index.html
LADO_LARGO = 1600
CALIDAD = 85
EXTENSIONES = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC = True
except ImportError:
    HEIC = False


def peticion(metodo, ruta, cuerpo=None, cabeceras=None):
    req = urllib.request.Request(SUPABASE_URL + ruta, data=cuerpo, method=metodo,
                                 headers={'apikey': SUPABASE_CLAVE, **(cabeceras or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def iniciar_sesion(usuario, clave):
    correo = re.sub(r'\s+', '', usuario).lower() + '@' + DOMINIO_USUARIOS
    estado, cuerpo = peticion('POST', '/auth/v1/token?grant_type=password',
                              json.dumps({'email': correo, 'password': clave}).encode(),
                              {'Content-Type': 'application/json'})
    if estado != 200:
        sys.exit('No se ha podido entrar: revisa el usuario y la contraseña.')
    datos = json.loads(cuerpo)
    if datos.get('user', {}).get('app_metadata', {}).get('rol') != 'admin':
        sys.exit('Esa cuenta no puede subir fotos (hace falta la cuenta admin).')
    return datos['access_token']


def dia_del_nombre(nombre):
    m = re.search(r'\d+', nombre)
    return int(m.group()) if m else None


def preparar(ruta):
    """Devuelve (bytes JPEG sin metadatos, (ancho, alto))."""
    with Image.open(ruta) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert('RGB')
        im.thumbnail((LADO_LARGO, LADO_LARGO), Image.LANCZOS)  # nunca amplía
        limpia = Image.new('RGB', im.size)  # copia solo los píxeles: sin EXIF, GPS ni perfiles
        limpia.paste(im)
        salida = io.BytesIO()
        limpia.save(salida, 'JPEG', quality=CALIDAD, optimize=True, progressive=True)
        return salida.getvalue(), limpia.size


def main():
    if not sys.stdout.isatty():  # en Windows, la salida redirigida no es UTF-8 por defecto
        sys.stdout.reconfigure(encoding='utf-8')
    carpeta = Path(sys.argv[1] if len(sys.argv) > 1 else 'fotos')
    if not carpeta.is_dir():
        sys.exit(f'No existe la carpeta {carpeta}. Crea "fotos/" y pon dentro las fotos (1.jpg, 2.jpg...).')

    elegidas = {}
    for ruta in sorted(carpeta.iterdir()):
        if not ruta.is_file() or ruta.suffix.lower() not in EXTENSIONES:
            continue
        dia = dia_del_nombre(ruta.stem)
        if dia is None or not 1 <= dia <= 24:
            print(f'  aviso: {ruta.name} no empieza por un día del 1 al 24; se salta')
            continue
        if ruta.suffix.lower() in {'.heic', '.heif'} and not HEIC:
            print(f'  aviso: {ruta.name} es HEIC (iPhone). Instala pillow-heif '
                  f'(pip install pillow-heif) o pásala a JPG; se salta')
            continue
        if dia in elegidas:
            print(f'  aviso: {ruta.name} repite el día {dia} (ya está {elegidas[dia].name}); se salta')
            continue
        elegidas[dia] = ruta

    if not elegidas:
        sys.exit('No hay ninguna foto que subir.')

    usuario = os.environ.get('CALENDARIO_USUARIO') or input('Usuario admin: ')
    clave = os.environ.get('CALENDARIO_CLAVE') or getpass.getpass('Contraseña: ')
    token = iniciar_sesion(usuario, clave)

    fallos = 0
    for dia in sorted(elegidas):
        ruta = elegidas[dia]
        try:
            datos, (ancho, alto) = preparar(ruta)
        except Exception as e:  # archivo dañado o formato raro
            print(f'  día {dia}: no se ha podido leer {ruta.name} ({e})')
            fallos += 1
            continue
        estado, cuerpo = peticion('POST', f'/storage/v1/object/fotos/dia-{dia:02d}.jpg', datos, {
            'Authorization': f'Bearer {token}', 'Content-Type': 'image/jpeg',
            'x-upsert': 'true', 'cache-control': '3600'})
        if estado == 200:
            print(f'  día {dia}: subida ({ancho}×{alto}, {len(datos) // 1024} KB) ← {ruta.name}')
        else:
            print(f'  día {dia}: error {estado} al subir {ruta.name}: {cuerpo[:200].decode(errors="replace")}')
            fallos += 1

    sin_foto = [d for d in range(1, 25) if d not in elegidas]
    if sin_foto:
        print('Días sin foto en esta carpeta:', ', '.join(map(str, sin_foto)))
    sys.exit(1 if fallos else 0)


if __name__ == '__main__':
    main()
