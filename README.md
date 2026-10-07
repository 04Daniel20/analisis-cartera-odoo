# Análisis de cartera y cobranza sobre un ERP Odoo 19

Proyecto de analítica de datos de punta a punta: desde un ERP en producción
sin reportería, hasta un tablero de Power BI con el que la gerencia toma
decisiones de cobranza.

No es un ejercicio con un dataset descargado. Es un sistema real, con sus
campos vacíos, sus migraciones mal documentadas y sus datos que mienten si
uno no sabe qué preguntarles.

---

## El problema

Una firma de consultoría contable y fiscal operaba sobre Odoo 19 Community
sin ningún reporte. Para saber cuánto se había facturado o quién debía, había
que abrir el sistema y contar a mano.

La pregunta de la gerencia era simple de enunciar y difícil de responder:

> ¿Cuánto nos deben, desde cuándo, y quién?

---

## Lo que había que resolver antes de poder responderla

| Obstáculo | Cómo se resolvió |
|---|---|
| El ERP expone **962 campos** entre los cinco modelos relevantes | Filtro de tres pasadas hasta dejar **83 campos con significado de negocio** |
| No existe campo que marque los registros migrados de otro sistema | Se identificaron por ventana de carga y se marcaron con una bandera propia |
| La antigüedad de cartera estaba falseada por la migración | Se separó `antiguedad_confiable` para no mezclar peras con manzanas |
| Un cobro puede saldar varias facturas y una factura recibir varios cobros | Tabla puente, para no inflar los importes |
| Campos "espejo": poblados al 100% pero redundantes | Se detectaron comparando contra su campo de origen |

---

## Arquitectura

```
Odoo 19 Community
       │
       │  XML-RPC  (solo lectura)
       ▼
  Scripts Python ──► 8 archivos CSV (modelo en estrella)
       │
       │  Programador de tareas de Windows
       ▼
   Power BI Desktop ──► 3 páginas, 30 medidas DAX
```

---

## Los scripts

Se ejecutan en orden. Cada uno responde a una pregunta distinta y ninguno
escribe sobre el ERP: **todos son de solo lectura**.

| Script | Qué hace |
|---|---|
| `01_conexion_odoo.py` | Autentica, confirma versión y lista los campos disponibles por modelo |
| `02_poblamiento_campos.py` | Mide qué porcentaje de cada campo está realmente poblado y cuántos valores distintos tiene |
| `02b_res_partner.py` | Lo mismo para contactos, tolerando los campos que el permiso bloquea |
| `03_diccionario_final.py` | Aplica el filtro de tres pasadas: descarta técnicos, vacíos y constantes |
| `04_resolver_revisar.py` | Clasifica los campos dudosos por familia y decide si entran |
| `05_extraccion_dataset_v2.py` | Extrae el dataset final, ya modelado en estrella |

### Ejecutarlos

```bash
pip install -r requirements.txt     # solo biblioteca estándar, en realidad
cp .env.ejemplo .env                # y completa tus valores
python scripts/01_conexion_odoo.py
```

Las credenciales se leen de variables de entorno. **Ningún script lleva
usuario, servidor ni clave escritos dentro.**

---

## El dataset de ejemplo

`dataset_ejemplo/` contiene los 8 archivos del modelo con la misma estructura
y las mismas proporciones que el real, para que el proyecto se pueda explorar
sin acceso al ERP.

Sobre su anonimización, con transparencia:

- **Los nombres son seudónimos.** Cada cliente, entidad y responsable tiene un
  nombre inventado, asignado de forma consistente en todos los archivos. El
  cliente 205 es el mismo seudónimo en facturas, cobros y dimensiones, así que
  el dataset sigue sirviendo para analizar.
- **Los importes están escalados por un factor constante que no se publica.**
  Las proporciones, los porcentajes y la forma de las distribuciones se
  conservan intactos. Los valores absolutos no corresponden a la realidad.
- **No hay RNC, correos ni teléfonos.** El modelo nunca los extrajo: solo
  guarda si existen o no (`tiene_rnc`, `tiene_correo`), que es lo único que la
  pregunta de negocio necesitaba.

Por eso los números de este repositorio no coinciden con los de las capturas
del tablero, y está bien que así sea.

---

## Las siete familias de campos

El criterio que ordenó las 962 columnas. Útil en cualquier ERP, no solo Odoo:

| Familia | Qué es | Ejemplo |
|---|---|---|
| **MONTO** | Lo que se suma | `monto_total`, `saldo_pendiente` |
| **TIEMPO** | Lo que ordena y permite comparar periodos | `fecha_factura`, `fecha_vencimiento` |
| **RELACIÓN** | Lo que conecta tablas | `id_cliente`, `id_entidad` |
| **CLASIFICACIÓN** | Lo que agrupa | `segmento_fiscal`, `metodo_pago` |
| **ESTADO** | Lo que filtra | `estado_cobro`, `conciliado_con_banco` |
| **TÉCNICO** | Lo que el ERP necesita y el negocio no | `write_uid`, `message_main_attachment_id` |
| **ESPEJO** | La traicionera: poblada al 100%, pero copia de otra | el nombre del cliente dentro del método de pago |

La familia ESPEJO es la que más tiempo cuesta descubrir y la que más ensucia
un modelo si pasa desapercibida.

---

## Hallazgos

Quince en total. Los que cambiaron decisiones:

- El **90% de la cartera pendiente** está en facturas que no han recibido
  ningún cobro parcial. No es morosidad repartida: es un bloque.
- **68% de los cobros registrados no está conciliado con banco.** Sin
  conciliación no hay certeza de que el dinero haya ingresado.
- La **concentración del Top 10 de clientes llega al 72%**. El Top 5 solo,
  al 53%.
- El promedio de días de cobro es **31.3**, pero la mediana es **25**: la
  media la empujan unos pocos casos largos.
- Una **carga masiva** sobrescribió las fechas de vencimiento originales.
  La antigüedad de cartera anterior a esa carga no es confiable, y el tablero
  lo dice explícitamente en lugar de esconderlo.

---

## El tablero

Tres páginas, cada una respondiendo una pregunta:

1. **Resumen** — cuánto se facturó y de qué tipo
2. **Cobranza y antigüedad** — cuánto falta por cobrar y desde cuándo
3. **Clientes y calidad de datos** — de quién depende el ingreso y qué tan
   confiable es el registro

El archivo `.pbix` no se publica: contiene el dataset embebido.

---

## Estructura

```
.
├── scripts/              los 6 scripts de extracción
├── dataset_ejemplo/      los 8 CSV anonimizados
├── docs/                 metodología, diccionario, medidas DAX, modelo
├── .env.ejemplo          plantilla de configuración
├── .gitignore
└── README.md
```

---

## Nota sobre el acceso

Todo el trabajo se hizo con un usuario propio y una clave API generada bajo
esa cuenta, con permisos de lectura. Nunca con credenciales prestadas de otra
persona.

No es formalismo: si la actividad queda registrada a nombre de alguien más,
el trabajo no es demostrablemente tuyo y la trazabilidad del sistema se
rompe.

---

## Licencia

MIT. Ver `LICENSE`.
