# Automatizar la actualización del dataset
Daniel Castillo · Proyecto ERP Odoo

---

## Qué vas a montar

El script de extracción corriendo solo, en un horario fijo, sin que
nadie lo ejecute a mano. El tablero se actualiza y tú no tocas nada.

Tres piezas:

1. `actualizar_datos.bat` — el que llama al script y guarda un registro
2. El **Programador de tareas de Windows** — el que lo dispara
3. La actualización del archivo de Power BI

---

## Paso 1 · Coloca el .bat

Guarda `actualizar_datos.bat` en `C:\proyecto-datos`, junto a los scripts.

**Pruébalo primero a mano:** doble clic. Debe correr y crear un archivo
`log_actualizacion.txt` en la misma carpeta.

Abre ese log y confirma que diga `RESULTADO: OK` al final. Si dice ERROR,
el propio log te muestra qué pasó.

---

## Paso 2 · Programador de tareas

Busca "Programador de tareas" en el menú Inicio de Windows.

En el panel derecho: **Crear tarea básica**.

**Nombre:** `Actualizar dataset Odoo`
**Descripción:** `Extrae facturación, cobros y clientes del ERP para el tablero`

**Desencadenador:** Semanalmente. Elige el día y la hora.

Sobre cuándo: la frecuencia la decide cada cuánto se toman decisiones con
ese dato, no cada cuánto puedes correrlo. Si la gerencia revisa facturación
los lunes, que corra domingo en la noche. Actualizar a diario algo que se
mira una vez al mes es trabajo desperdiciado.

**Acción:** Iniciar un programa.
- Programa o script: `C:\proyecto-datos\actualizar_datos.bat`
- Iniciar en: `C:\proyecto-datos`

Ese campo "Iniciar en" se olvida con frecuencia y sin él la tarea falla,
porque el script busca archivos en rutas relativas.

**Finalizar.** Después, clic derecho sobre la tarea y **Propiedades**:
- Marca "Ejecutar tanto si el usuario inició sesión como si no"
- Marca "Ejecutar con los privilegios más altos"

---

## Paso 3 · Pruébala

Clic derecho sobre la tarea, **Ejecutar**. Revisa el log.

Si falla al correr desatendida pero funciona a mano, casi siempre es
la ruta de Python. En ese caso edita el .bat y cambia `python` por la
ruta completa, algo como:

```
C:\Users\TuUsuario\AppData\Local\Programs\Python\Python313\python.exe 05_extraccion_dataset_v2.py
```

Para saber tu ruta exacta, abre una terminal y escribe `where python`.

---

## Paso 4 · Power BI

El script deja los CSV actualizados, pero Power BI no los lee solo.

Para refrescar el tablero: abre el archivo y usa **Inicio → Actualizar**.

En Desktop esto es manual. La actualización programada del propio informe
requiere publicarlo en el servicio de Power BI, lo cual necesita licencia Pro.

No es un problema para tu caso: el dataset se actualiza solo, y cuando
vayas a presentar abres el archivo y das Actualizar. Son dos clics.

---

## Lo que hay que cuidar

**Los CSV no pueden estar abiertos.** Si dejas uno abierto en Excel,
Windows lo bloquea y el script falla al escribirlo. Ya te pasó una vez.
En una tarea desatendida fallaría en silencio y solo lo verías en el log.

**La clave API no caduca sola, pero puede ser revocada.** Si alguien la
elimina desde Odoo, la tarea empieza a fallar. El log te lo va a decir
con "Autenticación fallida".

**Revisa el log de vez en cuando.** Una tarea programada que falla no
avisa a nadie. Es el riesgo de automatizar: el proceso se vuelve
invisible hasta que alguien nota que los números están viejos.

Una costumbre sana: mirar el log el día que vayas a presentar.

---

## Mejora opcional para después

El script escribe los CSV directamente. Si quisieras hacerlo a prueba de
archivos bloqueados, el patrón es escribir primero a un nombre temporal
y renombrar al final: si el archivo destino está bloqueado, el renombrado
falla pero la extracción ya terminó y no se pierde nada a medias.

Es la misma lógica que usan los programas al guardar: nunca escribas
encima de lo bueno hasta tener lo nuevo completo.
