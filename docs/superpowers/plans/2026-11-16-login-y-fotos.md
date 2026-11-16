# Login, bolsitas en la cuenta y foto privada por día — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bea entra con usuario y contraseña; sus bolsitas abiertas se guardan en su cuenta; cada día la nota muestra arriba, como una polaroid, una foto privada que el servidor no entrega antes de su día.

**Architecture:** Proyecto Supabase nuevo (Auth + tabla `bolsitas_abiertas` + bucket privado `fotos`) protegido por RLS que mira un rol en `app_metadata` y la hora de Madrid. El `index.html` de siempre (GitHub Pages) añade `supabase-js` al `importmap`, una pantalla de login con el estilo de la bienvenida, la sincronización de bolsitas y la polaroid. Un script Python sube las fotos iniciando sesión con la cuenta admin (sin clave de servicio). Un workflow de GitHub Actions evita que el proyecto gratuito se pause.

**Tech Stack:** Supabase (Postgres 17, Auth, Storage), `@supabase/supabase-js@2.49.4` vía `https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.49.4/+esm`, Three.js existente, Python 3.14 + Pillow 12 para el script, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-16-login-y-fotos-design.md`

## Global Constraints

- Un solo `index.html`, sin compilación, servido por GitHub Pages desde `main` (repo público).
- En el repositorio solo puede ir la URL del proyecto y la clave publishable/anon. Nunca contraseñas, nunca la clave de servicio, nunca fotos.
- Hora de referencia: `Europe/Madrid`. Día N se desbloquea en `make_timestamptz(2026, 12, N, 0, 0, 0, 'Europe/Madrid')`.
- Usuario → correo interno: `usuario.replace(/\s+/g, '').toLowerCase() + '@josecs5.github.io'` (dominio controlado por Jose; nunca se envía correo).
- Cuentas: Bea = `BeaLaRata` (→ `bealarata@josecs5.github.io`), `app_metadata.rol = 'bea'`. Jose = `<USUARIO_JOSE>`, `app_metadata.rol = 'admin'`. Contraseñas solo en la llamada que crea la cuenta, nunca en archivos.
- Fotos en el bucket: `dia-01.jpg` … `dia-24.jpg`, JPEG, lado largo 1600 px, sin metadatos EXIF.
- Textos en español, mismo estilo (kraft, lápiz blanco, botones `.btn`). Nada de esto cambia la animación ni el flujo de la grulla.
- No hay framework de tests: se verifica con SQL (`execute_sql`) y con el navegador (Playwright MCP) a 390×844 y a 1280×800, siempre sirviendo la página con `npx serve` o similar desde la raíz.

## Review Focus

- Bea escribe el usuario desde el móvil: iOS pone mayúscula inicial, autocorrige o añade un espacio al final → debe entrar igual (Task 2).
- Fotos del iPhone: HEIC, orientación en EXIF y GPS en los metadatos → el script convierte, endereza y borra metadatos, o rechaza el archivo con un mensaje claro (Task 5).
- Supabase lento o sin red al abrir la página con sesión ya guardada → la grulla llega igual (timeout), la bolsita se abre y el guardado se reintenta luego (Tasks 2–4).
- El proyecto gratuito se pausa tras 7 días sin actividad (p. ej. antes del 1 de diciembre o entre el 25 de diciembre y abril) → Bea no podría entrar (Task 6).
- Con `?prueba` y la cuenta de Bea, un día futuro: la foto no se entrega → la nota sale sin foto, sin error visible ni hueco vacío (Task 4).

---

### Task 1: Proyecto Supabase, esquema, reglas y cuentas

**Files:**
- Create: `supabase/migraciones/001_bolsitas_y_fotos.sql` (copia de lo aplicado, para tener registro)

**Interfaces:**
- Produces: URL del proyecto y clave publishable (para Task 2); funciones SQL `public.rol_actual() returns text` y `public.dia_desbloqueado(dia int) returns boolean`; tabla `public.bolsitas_abiertas(user_id uuid, dia smallint, abierta_en timestamptz)`; bucket `fotos`.

- [ ] **Step 1: Crear el proyecto** `calendario-bea` en la organización `gtfwecgpfxhccsvcyjvo`, región `eu-west-1`, plan gratuito (los dos proyectos existentes están pausados, así que cabe). Esperar a estado `ACTIVE_HEALTHY`.

- [ ] **Step 2: Escribir la migración** con:
  - `rol_actual()`: `auth.jwt() -> 'app_metadata' ->> 'rol'`, `stable`, `security invoker`.
  - `dia_desbloqueado(dia int)`: `dia between 1 and 24 and now() >= make_timestamptz(2026, 12, dia, 0, 0, 0, 'Europe/Madrid')`.
  - Tabla `bolsitas_abiertas`: PK `(user_id, dia)`, `user_id` → `auth.users(id) on delete cascade`, `check (dia between 1 and 24)`, RLS activado.
    - select: `user_id = auth.uid()`.
    - insert: `user_id = auth.uid() and rol_actual() in ('bea','admin') and (rol_actual() = 'admin' or dia_desbloqueado(dia))`.
    - Sin update ni delete.
  - Bucket `fotos` privado (`public = false`, límite 5 MB, solo `image/jpeg`).
  - `storage.objects` select: `bucket_id = 'fotos' and (rol_actual() = 'admin' or (rol_actual() = 'bea' and dia_desbloqueado(substring(name from '^dia-(\d{2})\.jpg$')::int)))`.
  - `storage.objects` insert y update: `bucket_id = 'fotos' and rol_actual() = 'admin'`.

- [ ] **Step 3: Aplicar** con `apply_migration` (nombre `bolsitas_y_fotos`).

- [ ] **Step 4: Crear las dos cuentas** desde el panel (Authentication → Add user → "Auto confirm") o con SQL sobre `auth.users` + `auth.identities` usando `crypt(<contraseña>, gen_salt('bf'))`; luego `update auth.users set raw_app_meta_data = raw_app_meta_data || '{"rol":"bea"}'` (y `"admin"` para Jose). Desactivar el registro público (Authentication → Sign In / Providers → "Allow new users to sign up" off) — si no se puede desde aquí, pedírselo a Jose; la seguridad no depende de ello porque toda regla exige `rol`.

- [ ] **Step 5: Verificar las reglas con SQL** (cada bloque en una transacción con `set local role authenticated; set local request.jwt.claims = '{"sub":"<id>","role":"authenticated","app_metadata":{"rol":"…"}}'`):
  - `select make_timestamptz(2026,12,1,0,0,0,'Europe/Madrid')` = `2026-11-30 23:00:00+00`.
  - Como `bea` hoy (antes de diciembre): `dia_desbloqueado(1)` = false; insert de `dia=1` → error RLS.
  - Como `admin`: insert de `dia=24` → ok (luego `rollback`).
  - Como `bea`: `select … from bolsitas_abiertas` de otro `user_id` → 0 filas.
  - Como usuario sin `rol`: insert → error RLS.
  - `get_advisors` (security) sin avisos nuevos sobre estas tablas/funciones.

- [ ] **Step 6: Commit**

```bash
git add supabase/migraciones/001_bolsitas_y_fotos.sql
git commit -m "Supabase: tabla de bolsitas abiertas y almacén privado de fotos con desbloqueo por día"
```

### Task 2: Cliente Supabase y pantalla de login

**Files:**
- Modify: `index.html` — `importmap` (línea ~251), estilos junto a `.bienvenida` (~214–237), HTML junto a `#bienvenida` (~303), objeto `ui` (~394), `iniciar()` (~1417).

**Interfaces:**
- Consumes: URL y clave publishable (Task 1).
- Produces:
  - `const supabase` (cliente, `auth.persistSession: true`, `storageKey: 'bea-sesion'`).
  - `correoDeUsuario(usuario: string): string`.
  - `entrar(): Promise<void>` — resuelve cuando hay sesión válida; si no, muestra `#login` y resuelve tras un login correcto.
  - `esAdmin(): boolean` — `rol` del usuario de la sesión === `'admin'`.

- [ ] **Step 1: Añadir** `"@supabase/supabase-js": "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.49.4/+esm"` al `importmap` y `const SUPABASE = { url: '…', clave: '…' }` junto a las constantes de configuración, con un comentario de que la clave es pública por diseño.

- [ ] **Step 2: Añadir** `<section id="login" class="bienvenida login" hidden>` reutilizando la caja de la bienvenida: grulla, `<h2>Hola, Bea</h2>`, texto corto («Entra para que la grulla te reconozca»), `<form>` con `<label>Usuario</label><input name="usuario" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" required>`, `<label>Contraseña</label><input type="password" autocomplete="current-password" required>`, `<p class="login-error" role="alert" hidden>`, `<button class="btn" type="submit">Entrar</button>`. Campos con borde de lápiz blanco sobre kraft, como el resto. Los textos van en un objeto `LOGIN` junto a `BIENVENIDA`.

- [ ] **Step 3: Implementar `entrar()`**: `getSession()`; si hay sesión, resolver. Si no, `body.con-bienvenida` + mostrar `#login`; en `submit`, deshabilitar el botón, `signInWithPassword({ email: correoDeUsuario(usuario), password })`; error de credenciales → «Ese usuario o esa contraseña no son correctos»; error de red → «No hay conexión. Prueba otra vez en un momento»; éxito → misma salida animada que la bienvenida (`saliendo`, 600 ms o 0 con `reducido`).

- [ ] **Step 4: Encadenar en `iniciar()`**: sustituir `bienvenida()` en el `Promise.all` por `entrar().then(bienvenida)`. `?prueba` también pasa por `entrar()`.

- [ ] **Step 5: Verificar en el navegador** (sin sesión, 390×844):
  - Sale el login, no la bienvenida.
  - Usuario `bealarata ` (minúsculas + espacio final) y contraseña errónea → mensaje de error, el foco vuelve al campo.
  - Usuario ` BeaLaRata` + contraseña buena → login se va, sale la bienvenida (cookie borrada), luego la grulla.
  - Recargar → no sale el login.
  - Con la red cortada (`browser_run_code_unsafe` → `context.setOffline(true)`) y sesión guardada → la grulla llega igual.
  - Sin errores en consola.

- [ ] **Step 6: Commit** — `git commit -m "Pantalla de login con usuario y contraseña antes de la bienvenida"`

### Task 3: Bolsitas abiertas guardadas en la cuenta

**Files:**
- Modify: `index.html:1029-1038` (`estaAbierta`, `guardarAbierta`) y `iniciar()`.

**Interfaces:**
- Consumes: `supabase`, sesión (Task 2).
- Produces: `cargarAbiertas(): Promise<void>` (rellena `abiertasCuenta: Set<number>`); `estaAbierta(dia)` y `guardarAbierta(dia)` con la misma firma que hoy.

- [ ] **Step 1: Implementar `cargarAbiertas()`**: `select dia from bolsitas_abiertas` → `abiertasCuenta`. Después, los días con `bea-bolsita-N = '1'` en `localStorage` que no estén en la cuenta se suben con `upsert(…, { onConflict: 'user_id,dia', ignoreDuplicates: true })`; los rechazados por RLS (día aún no llegado) se ignoran. No hace nada en `PRUEBA`.

- [ ] **Step 2: Cambiar `estaAbierta`** a `abiertasCuenta.has(dia) || localStorage === '1'` (prueba: igual que hoy). **`guardarAbierta`**: `localStorage` como hoy + `abiertasCuenta.add` + insert sin esperar; si falla por red, queda en `localStorage` y el próximo `cargarAbiertas()` lo sube.

- [ ] **Step 3: En `iniciar()`**, después de `entrar()` y antes de `iniciarDia(dia)`, `await Promise.race([cargarAbiertas(), espera(4000)])`.

- [ ] **Step 4: Verificar** (fecha simulada con la cuenta admin, que puede insertar cualquier día; borrar luego sus filas con SQL):
  - Abrir la bolsita → fila nueva en `bolsitas_abiertas` (consultar con `execute_sql`).
  - Borrar `localStorage` (menos la sesión) y recargar → la bolsita sigue abierta.
  - Poner `bea-bolsita-3 = '1'` en `localStorage` en una sesión nueva → tras cargar, existe la fila del día 3.
  - Con `?prueba` → no se crea ninguna fila.

- [ ] **Step 5: Commit** — `git commit -m "Las bolsitas abiertas se guardan en la cuenta y se ven en cualquier dispositivo"`

### Task 4: La foto del día, como polaroid arriba de la nota

**Files:**
- Modify: `index.html` — `#nota` (~280, nuevo `<figure id="nota-polaroid" class="polaroid" hidden><img id="nota-img" alt=""></figure>` como primer hijo), estilos de `.nota`, `ui`, `iniciarDia` (~947) y el bloque `if (f === 'nota')` (~924).

**Interfaces:**
- Consumes: `supabase`, `esAdmin()` (Task 2).
- Produces: `urlFoto(dia: number): Promise<string | null>` (URL firmada de `dia-NN.jpg`, validez 3600 s; `null` si no existe o no está permitida).

- [ ] **Step 1: Implementar `urlFoto`** con `storage.from('fotos').createSignedUrl(…)`, cacheada por día en un `Map`. Sin sesión → `null`.

- [ ] **Step 2: Precargar**: en `iniciarDia(dia)` para `1 ≤ dia ≤ 24`, lanzar `urlFoto(dia)` y crear un `Image()` con ella para que esté descargada al abrir la nota.

- [ ] **Step 3: Mostrar**: al entrar en fase `nota`, si hay URL, `alt = "Foto del día N"`, mostrar la polaroid; si no, `hidden` y la nota queda como hoy. Ignorar resultados que lleguen cuando `est.dia` ya cambió (selector de prueba).

- [ ] **Step 4: Estilo**: marco blanco roto (`--crema`), borde inferior más ancho como una polaroid, `rotate: -2deg`, sombra como la de la grulla de la bienvenida. La foto no se recorta (`object-fit: contain`, ancho 100 %), `max-height: 42vh`. Mientras carga, hueco con `aspect-ratio: 4 / 3` para que la nota no salte al aparecer.

- [ ] **Step 5: Verificar** (subir a mano dos JPEG de prueba como `dia-01.jpg` y `dia-24.jpg` con la cuenta admin; borrarlos al acabar):
  - Admin + `?prueba`, día 1 → polaroid arriba de la nota; día 2 → sin polaroid ni hueco.
  - Bea + `?prueba`, día 24 → sin polaroid, y en red la petición de firma devuelve 400/404 (no hay URL).
  - A 390×844 la nota completa se puede leer y el botón «Cerrar» es alcanzable (desplazando si hace falta); a 1280×800, igual.
  - Foto vertical y foto apaisada: ninguna se recorta.
  - Cambiar rápido de día en el selector → nunca sale la foto de otro día.

- [ ] **Step 6: Commit** — `git commit -m "Cada día la nota trae arriba una foto privada, como una polaroid"`

### Task 5: Script para subir las fotos

**Files:**
- Create: `herramientas/subir_fotos.py`
- Modify: `.gitignore` (añadir `fotos/`)

**Interfaces:**
- Consumes: URL y clave publishable (Task 1), cuenta admin.
- Produces: `python herramientas/subir_fotos.py [carpeta=fotos]` — pide usuario y contraseña admin por consola (`getpass`), sube cada foto como `dia-NN.jpg` con `x-upsert: true`, imprime una línea por día (`día 3: subida (1600×1200)`) y al final los días sin foto.

- [ ] **Step 1: Añadir `fotos/` a `.gitignore`** y comprobar con `git check-ignore fotos/1.jpg`.

- [ ] **Step 2: Implementar** (solo biblioteca estándar + Pillow):
  - Archivos de entrada: el número de día es el primer número del nombre (`1.jpg`, `03-playa.png`, `dia 12.jpeg`); fuera de 1–24 o repetido → aviso y se salta.
  - `ImageOps.exif_transpose`, convertir a RGB, lado largo 1600 px (sin ampliar), guardar JPEG calidad 85 **sin EXIF**.
  - `.heic`/`.heif`: si `pillow_heif` está instalado, registrarlo; si no, saltar con «Instala pillow-heif o pásala a JPG».
  - Login con `POST {url}/auth/v1/token?grant_type=password`, subida con `POST {url}/storage/v1/object/fotos/dia-NN.jpg`.

- [ ] **Step 3: Verificar** con una carpeta temporal en el scratchpad que contenga un JPEG con EXIF de orientación 6 y GPS, un PNG y un archivo `99.jpg`:
  - Sube los dos válidos; descargados como admin, el primero sale derecho y `Image.getexif()` está vacío.
  - `99.jpg` → aviso, no se sube.
  - Borrar las fotos de prueba del bucket al terminar.

- [ ] **Step 4: Commit** — `git add .gitignore herramientas/subir_fotos.py && git commit -m "Script para subir las fotos de cada día al almacén privado"`

### Task 6: Mantener despierto el proyecto gratuito

**Files:**
- Create: `.github/workflows/despertar-supabase.yml`

- [ ] **Step 1: Workflow** con `schedule: cron '17 6 */3 * *'` y `workflow_dispatch`, un paso `curl -fsS "$URL/rest/v1/bolsitas_abiertas?select=dia&limit=1" -H "apikey: $CLAVE"` (devuelve `[]` por RLS pero toca la base de datos). URL y clave publishable en texto (son públicas). Se salta solo a partir del 2027-04-06.

- [ ] **Step 2: Verificar** tras el push (Task 7) lanzándolo a mano con `gh workflow run` y `gh run watch` → éxito. Avisar a Jose de que GitHub desactiva los cron tras 60 días sin commits en el repo (entre finales de diciembre y febrero): se reactiva con un clic en Actions.

- [ ] **Step 3: Commit** — `git commit -m "Despierta Supabase cada tres días para que no se pause"`

### Task 7: Publicar y comprobar en la web

- [ ] **Step 1: Pedir permiso a Jose** antes de `git push` (publica la web).
- [ ] **Step 2: `git push`** y esperar a que GitHub Pages termine (`gh api repos/Josecs5/calendario-bea/pages/builds/latest` → `built`).
- [ ] **Step 3: Verificar** en `https://josecs5.github.io/calendario-bea/` en una ventana sin sesión: login → bienvenida → grulla (cuenta admin, luego cerrar sesión borrando `localStorage`), sin errores en consola. Ejecutar el workflow de Task 6.
- [ ] **Step 4: Recordar a Jose** que pase las fotos (carpeta `fotos/`) para ejecutar `herramientas/subir_fotos.py`.
