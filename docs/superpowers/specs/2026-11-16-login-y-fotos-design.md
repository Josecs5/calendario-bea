# Login, bolsitas guardadas en la cuenta y una foto privada por día

Fecha: 2026-11-16

## Por qué

El calendario de adviento de Bea es un único `index.html` en GitHub Pages
(repositorio público). Hoy las bolsitas abiertas solo se recuerdan en el
`localStorage` de su móvil, y no hay forma de enseñar fotos privadas: todo lo que
se sube al repositorio lo puede ver cualquiera.

Jose quiere:

1. Que Bea entre con su cuenta, y que qué bolsitas ha abierto quede guardado en esa
   cuenta (no en un móvil concreto).
2. Que cada día salga una foto de los dos que Jose le da, y que sea privada.

## Objetivos

- Pantalla de login con el estilo actual (papel kraft, lápiz blanco, botones de etiqueta).
- Las bolsitas abiertas se guardan en la cuenta y se ven igual desde cualquier dispositivo.
- Una foto por día (1–24), que sale **dentro de la nota, arriba, como una polaroid** (decidido por Jose).
- La foto del día N es imposible de obtener antes de las 00:00 del día N (hora de Madrid),
  ni siquiera leyendo el código o llamando a la API a mano. Lo comprueba el servidor.

## No objetivos

- Galería de fotos, subir fotos desde la web, registro de usuarios, recuperación de
  contraseña desde la web (si hace falta, Jose la cambia desde el panel de Supabase).
- Cambiar la animación, los textos o el flujo actuales salvo lo descrito aquí.

## Lo que sería un fracaso aunque "funcione"

- Que una foto se pueda ver antes de su día, o que cualquiera sin cuenta pueda verla.
- Que una foto acabe en el repositorio público (ni siquiera en el historial).
- Que Bea se quede sin poder entrar el 1 de diciembre.
- Que si Supabase falla un momento, la grulla no traiga la bolsita.

## Restricciones

- Sigue siendo un solo `index.html` sin paso de compilación, servido por GitHub Pages.
- Repositorio público: en el HTML solo puede ir la clave pública (publishable/anon) de Supabase;
  la seguridad la ponen las reglas (RLS) del servidor.
- Hora de referencia: Europe/Madrid, igual que `INICIO_DICIEMBRE`.
- Textos en español, mismo tono y estilo visual.

## Enfoques considerados

- **A) Supabase (elegido por Jose).** Login, base de datos y almacén privado en un servicio
  gratuito; el bloqueo por día se hace con reglas del servidor. Cumple todo.
- **B) Fotos cifradas en el repositorio, sin servidor.** Sin dependencias, pero no hay dónde
  guardar las bolsitas abiertas y con la contraseña se descifran todas las fotos el primer día.
  Descartado.
- Firebase (lo mismo que A sin ventaja) y la protección por contraseña de Vercel (de pago, no
  guarda estado), descartados.

## Diseño

### Supabase

- Proyecto gratuito nuevo, región UE.
- **Auth:** **usuario + contraseña** (decidido por Jose: nada de correo). Supabase solo
  admite correo o teléfono, así que cada usuario se guarda por dentro con un correo
  inventado que nunca recibe nada (`<usuario>@<dominio fijo>`, creado ya confirmado).
  Bea solo ve y escribe su usuario. Registro público desactivado. Dos cuentas creadas a mano:
  - Bea (cuenta normal).
  - Jose, con `app_metadata.rol = 'admin'`: puede ver las fotos de cualquier día, para probar.
- **Tabla `bolsitas_abiertas`**: `user_id uuid` (→ `auth.users`), `dia smallint` (1–24),
  `abierta_en timestamptz default now()`, clave primaria `(user_id, dia)`.
  RLS: cada usuario solo lee e inserta sus propias filas; solo puede insertar un día que ya
  ha llegado en Madrid (o cualquiera si es admin).
- **Almacén `fotos`** (bucket privado). Nombres `dia-01.jpg` … `dia-24.jpg`.
  RLS en `storage.objects` (solo lectura): usuario autenticado y
  (`rol = 'admin'` **o** `now() >= 00:00 Madrid del 1 de diciembre de 2026 + (día − 1)`).
  Nadie puede subir ni borrar desde la web; las fotos se suben con la clave de servicio,
  desde fuera del navegador.

- **Que no se pause:** los proyectos gratuitos se pausan tras 7 días sin uso. Un workflow
  de GitHub Actions hace una consulta cada 3 días hasta el 5 de abril de 2027.
- Las fotos las sube un script iniciando sesión con la cuenta admin (no hace falta clave de servicio).

### Página

- `supabase-js` v2 añadido al `importmap` existente (versión fija desde un CDN).
- **Orden al entrar:** login (si no hay sesión) → bienvenida (solo la primera vez, como ahora)
  → grulla. La sesión se recuerda, así que el login se ve una sola vez por dispositivo.
- **Pantalla de login:** misma caja que la bienvenida: grulla, título, campos de usuario y
  contraseña, botón «Entrar», mensaje de error en lenguaje normal («Ese usuario o esa
  contraseña no son correctos»). Campo «Usuario»; se quitan espacios y se pasa a minúsculas
  antes de convertirlo en el correo interno. Se pide siempre, también antes de diciembre.
- **Bolsitas abiertas:** al entrar se cargan de la tabla. `guardarAbierta` escribe en la tabla
  y además en `localStorage` como copia; `estaAbierta` usa lo cargado más esa copia.
  La primera vez que entra, lo que hubiera en `localStorage` se sube a su cuenta.
  Si falla la red, la bolsita se abre igual y se reintenta guardar la próxima vez.
- **Foto en la nota:** al abrir la nota del día se pide una URL firmada de `dia-NN.jpg`
  (validez corta) y se muestra arriba de la nota, en un marco blanco tipo polaroid, ligeramente
  girado. Hay un hueco reservado mientras carga, para que la nota no salte. Si no hay foto o
  falla, la nota sale como hoy. `alt` descriptivo genérico («Foto del día N»).
- **`?prueba`:** también pide login. Con la cuenta admin se ven las fotos de cualquier día del
  selector; las bolsitas abiertas en modo prueba siguen sin guardarse (solo en memoria).

### Fotos

- Jose pasa las fotos. Se redimensionan (lado largo ~1600 px, JPEG) y se suben al bucket.
- Las fotos locales viven en una carpeta incluida en `.gitignore` (p. ej. `fotos/`), para que
  nunca acaben en el repositorio.

## Decisiones que tomé yo (Claude), para revisar

- Dominio inventado para los correos internos.
- Cuenta de admin para Jose y el comportamiento de `?prueba` con login.
- Login obligatorio siempre, también antes de diciembre.
- Copia en `localStorage` como respaldo y migración de lo ya abierto.
- Tamaño de las fotos (~1600 px) y nombres `dia-NN.jpg`.
- Las reglas del servidor también impiden marcar como abierta una bolsita futura.

## Queda para quien lo construya

- Detalles visuales de la polaroid y del formulario dentro del estilo existente.
- Validez exacta de la URL firmada y cómo se reintenta el guardado pendiente.
- Cómo se ejecuta la subida de fotos (script local con la clave de servicio, que no se guarda
  en el repositorio).

## Pendiente de Jose

- El nombre de usuario de Bea y el de Jose (cuenta admin). Las contraseñas las elige Jose.
- Las fotos, cuando las tenga.
