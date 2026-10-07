"""
02 - Poblamiento de campos y diccionario priorizado
la firma | Daniel Castillo

Qué hace:
  Para cada modelo, mide qué porcentaje de registros tiene cada campo
  realmente lleno, descarta los campos técnicos de Odoo, y genera un
  CSV de trabajo con las columnas que TÚ debes completar.

Por qué importa:
  Un campo que existe pero está vacío en el 100% de los registros no
  sirve para construir indicadores. Medir el poblamiento antes de
  documentar es lo que separa un diccionario útil de uno decorativo.

SOLO LECTURA. No crea, modifica ni borra nada.
"""

import xmlrpc.client
import csv
import os

# ---------------------------------------------------------------
# ---------------------------------------------------------------
# CONEXIÓN AL ERP

URL     = os.environ.get("ODOO_URL",     "https://ERP.EJEMPLO.COM")
DB      = os.environ.get("ODOO_DB",      "base_de_datos")
USER    = os.environ.get("ODOO_USER",    "usuario@empresa.com")
API_KEY = os.environ.get("ODOO_API_KEY", "")

if not API_KEY:
    raise SystemExit(
        "Falta ODOO_API_KEY en el entorno.\n"
        "Define las cuatro variables antes de ejecutar (ver .env.ejemplo)."
    )

SALIDA = "salida"
MUESTRA_MAX = 500   # registros a inspeccionar por modelo


# Campos de infraestructura de Odoo: no son de negocio, se descartan.
PREFIJOS_TECNICOS = (
    "message_", "activity_", "access_", "rating_", "website_",
    "my_activity_", "__",
)
CAMPOS_TECNICOS = {
    "create_uid", "create_date", "write_uid", "write_date",
    "display_name", "id", "__last_update",
}

MODELOS = {
    "account.move":      "Facturas y asientos contables",
    "account.move.line": "Líneas de detalle de factura",
    "res.partner":       "Clientes y proveedores",
    "account.payment":   "Pagos registrados",
    "product.product":   "Productos y servicios",
}

# Dominios: qué subconjunto de registros mirar en cada modelo.
DOMINIOS = {
    "account.move":      [["move_type", "=", "out_invoice"]],
    "account.move.line": [["parent_state", "=", "posted"]],
    "res.partner":       [],
    "account.payment":   [],
    "product.product":   [],
}


def es_tecnico(nombre):
    return nombre in CAMPOS_TECNICOS or nombre.startswith(PREFIJOS_TECNICOS)


def vacio(valor):
    """En XML-RPC, un campo sin valor llega como False, '', [] o None."""
    return valor is False or valor is None or valor == "" or valor == []


def conectar():
    common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
    uid = common.authenticate(DB, USER, API_KEY, {})
    if not uid:
        raise SystemExit("Autenticación fallida. Revisa usuario y clave API.")
    print(f"Conectado. UID = {uid}\n")
    return uid, xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")


def analizar(models, uid, modelo, descripcion):
    print("=" * 62)
    print(f"{modelo}  —  {descripcion}")
    print("=" * 62)

    meta = models.execute_kw(DB, uid, API_KEY, modelo, "fields_get", [],
                             {"attributes": ["string", "type", "store",
                                             "relation", "selection", "help"]})

    # Solo campos almacenados y no técnicos.
    utiles = {n: m for n, m in meta.items()
              if m.get("store") and not es_tecnico(n)}

    print(f"  Campos totales: {len(meta)}   ->   candidatos: {len(utiles)}")

    registros = models.execute_kw(DB, uid, API_KEY, modelo, "search_read",
                                  [DOMINIOS.get(modelo, [])],
                                  {"fields": list(utiles.keys()),
                                   "limit": MUESTRA_MAX})
    n = len(registros)
    print(f"  Registros inspeccionados: {n}")

    if n == 0:
        print("  Sin registros. Se omite.\n")
        return

    filas = []
    for nombre, m in utiles.items():
        llenos = sum(1 for r in registros if not vacio(r.get(nombre)))
        pct = round(100 * llenos / n, 1)

        # Valores distintos: 1 solo valor = campo constante, poco útil para segmentar
        try:
            distintos = len({str(r.get(nombre)) for r in registros})
        except TypeError:
            distintos = ""

        filas.append({
            "campo_tecnico": nombre,
            "etiqueta": m.get("string", ""),
            "tipo": m.get("type", ""),
            "modelo_relacionado": m.get("relation", ""),
            "pct_poblado": pct,
            "valores_distintos": distintos,
            "ayuda_odoo": (m.get("help") or "").replace("\n", " ")[:160],
            # --- columnas que completas TÚ ---
            "significado_negocio": "",
            "pregunta_que_responde": "",
            "riesgo_calidad": "",
            "entra_al_modelo": "",
        })

    # Orden: los más poblados primero, luego por tipo
    prioridad_tipo = {"date": 0, "datetime": 0, "monetary": 1, "float": 1,
                      "integer": 1, "many2one": 2, "selection": 3}
    filas.sort(key=lambda f: (-f["pct_poblado"],
                              prioridad_tipo.get(f["tipo"], 9),
                              f["campo_tecnico"]))

    os.makedirs(SALIDA, exist_ok=True)
    archivo = os.path.join(SALIDA, f"trabajo_{modelo.replace('.', '_')}.csv")
    with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)

    # Resumen en pantalla
    con_datos = [f for f in filas if f["pct_poblado"] > 0]
    vacios = len(filas) - len(con_datos)
    constantes = [f for f in con_datos if f["valores_distintos"] == 1]

    print(f"  Con datos: {len(con_datos)}   |   Siempre vacíos: {vacios}   "
          f"|   Constantes: {len(constantes)}")
    print(f"  -> {archivo}")
    print(f"\n  Top 12 campos poblados (por aquí empiezas):")
    for f in con_datos[:12]:
        print(f"     {f['campo_tecnico']:<32} {f['tipo']:<12} "
              f"{f['pct_poblado']:>5}%  ({f['valores_distintos']} distintos)")
    print()


if __name__ == "__main__":
    uid, models = conectar()
    for modelo, desc in MODELOS.items():
        try:
            analizar(models, uid, modelo, desc)
        except Exception as e:
            print(f"  Error en {modelo}: {e}\n")

    print("=" * 62)
    print("SIGUIENTE PASO — lo hace una persona, no el script")
    print("=" * 62)
    print("""
  Abre los archivos trabajo_*.csv y completa las cuatro últimas columnas
  SOLO en los campos que vas a usar. No en todos.

  significado_negocio    -> qué es, en una frase, sin jerga técnica.
                            Escríbelo como se lo explicarías al contador.
  pregunta_que_responde  -> la pregunta de negocio que este campo permite
                            contestar. Si no se te ocurre ninguna, el campo
                            no entra a tu modelo.
  riesgo_calidad         -> vacíos, duplicados, formatos inconsistentes,
                            valores por defecto que nadie cambió.
  entra_al_modelo        -> SI / NO. Decisión explícita.

  Regla: si un campo tiene 0% poblado, no lo documentes. Anótalo aparte
  como hallazgo de adopción: "campo disponible y sin uso".
""")
