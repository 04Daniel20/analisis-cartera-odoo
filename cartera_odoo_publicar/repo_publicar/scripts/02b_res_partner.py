"""
02b - Poblamiento de res.partner (con tolerancia a campos restringidos)
la firma | Daniel Castillo

Por qué existe este script:
  En el script 02, res.partner falló con "Failed to read field rtc_session_ids".
  Odoo restringe ciertos campos a administradores de sistema. En un ERP en
  producción esto es normal y hay que preverlo.

Estrategia:
  Si la lectura completa falla, el script divide los campos en bloques,
  identifica cuáles no puede leer, los reporta como restringidos y continúa
  con el resto. Nunca se detiene por un campo.

SOLO LECTURA.
"""

import xmlrpc.client
import csv
import os

# ---------------------------------------------------------------
# ---------------------------------------------------------------
# CONEXIÓN AL ERP
# ---------------------------------------------------------------
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
MUESTRA_MAX = 500

PREFIJOS_TECNICOS = (
    "message_", "activity_", "access_", "rating_", "website_",
    "my_activity_", "__",
)
CAMPOS_TECNICOS = {
    "create_uid", "create_date", "write_uid", "write_date",
    "display_name", "id", "__last_update",
}

# Modelos cuyos campos suelen estar restringidos o no aportan al negocio
RELACIONES_EXCLUIDAS = ("discuss.", "mail.", "bus.", "ir.")


def es_tecnico(nombre, meta):
    if nombre in CAMPOS_TECNICOS or nombre.startswith(PREFIJOS_TECNICOS):
        return True
    rel = meta.get("relation") or ""
    return rel.startswith(RELACIONES_EXCLUIDAS)


def vacio(v):
    return v is False or v is None or v == "" or v == []


def conectar():
    common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
    uid = common.authenticate(DB, USER, API_KEY, {})
    if not uid:
        raise SystemExit("Autenticación fallida.")
    print(f"Conectado. UID = {uid}\n")
    return uid, xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")


def leer_tolerante(models, uid, modelo, campos, dominio, limite):
    """
    Intenta leer todos los campos. Si falla, divide en bloques y descarta
    los que el usuario no tiene permiso de leer. Devuelve (registros, bloqueados).
    """
    try:
        regs = models.execute_kw(DB, uid, API_KEY, modelo, "search_read",
                                 [dominio], {"fields": campos, "limit": limite})
        return regs, []
    except Exception:
        pass

    print("  Lectura completa falló. Identificando campos restringidos...")
    buenos, bloqueados = [], []

    # Prueba campo por campo, en bloques pequeños para no saturar el servidor
    for c in campos:
        try:
            models.execute_kw(DB, uid, API_KEY, modelo, "search_read",
                              [dominio], {"fields": [c], "limit": 1})
            buenos.append(c)
        except Exception:
            bloqueados.append(c)

    regs = models.execute_kw(DB, uid, API_KEY, modelo, "search_read",
                             [dominio], {"fields": buenos, "limit": limite})
    return regs, bloqueados


def analizar(models, uid, modelo, descripcion, dominio=None):
    dominio = dominio or []
    print("=" * 62)
    print(f"{modelo}  —  {descripcion}")
    print("=" * 62)

    meta = models.execute_kw(DB, uid, API_KEY, modelo, "fields_get", [],
                             {"attributes": ["string", "type", "store",
                                             "relation", "help"]})

    utiles = {n: m for n, m in meta.items()
              if m.get("store") and not es_tecnico(n, m)}
    print(f"  Campos totales: {len(meta)}   ->   candidatos: {len(utiles)}")

    registros, bloqueados = leer_tolerante(
        models, uid, modelo, list(utiles.keys()), dominio, MUESTRA_MAX)

    if bloqueados:
        print(f"  Campos sin permiso de lectura ({len(bloqueados)}): "
              f"{', '.join(bloqueados[:8])}"
              f"{' ...' if len(bloqueados) > 8 else ''}")
        for c in bloqueados:
            utiles.pop(c, None)

    n = len(registros)
    print(f"  Registros inspeccionados: {n}")
    if n == 0:
        print("  Sin registros.\n")
        return

    filas = []
    for nombre, m in utiles.items():
        llenos = sum(1 for r in registros if not vacio(r.get(nombre)))
        pct = round(100 * llenos / n, 1)
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
            "significado_negocio": "",
            "pregunta_que_responde": "",
            "riesgo_calidad": "",
            "entra_al_modelo": "",
        })

    prioridad = {"date": 0, "datetime": 0, "monetary": 1, "float": 1,
                 "integer": 1, "many2one": 2, "selection": 3}
    filas.sort(key=lambda f: (-f["pct_poblado"],
                              prioridad.get(f["tipo"], 9), f["campo_tecnico"]))

    os.makedirs(SALIDA, exist_ok=True)
    archivo = os.path.join(SALIDA, f"trabajo_{modelo.replace('.', '_')}.csv")
    with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)

    con_datos = [f for f in filas if f["pct_poblado"] > 0]
    print(f"  Con datos: {len(con_datos)}   |   "
          f"Siempre vacíos: {len(filas) - len(con_datos)}")
    print(f"  -> {archivo}\n")
    print("  Top 15 campos poblados:")
    for f in con_datos[:15]:
        print(f"     {f['campo_tecnico']:<30} {f['tipo']:<12} "
              f"{f['pct_poblado']:>5}%  ({f['valores_distintos']} distintos)")
    print()


def perfil_clientes(models, uid):
    """Preguntas de negocio concretas sobre la cartera de clientes."""
    print("=" * 62)
    print("PERFIL DE LA CARTERA DE CLIENTES")
    print("=" * 62)

    total    = models.execute_kw(DB, uid, API_KEY, "res.partner",
                                 "search_count", [[["customer_rank", ">", 0]]])
    empresas = models.execute_kw(DB, uid, API_KEY, "res.partner",
                                 "search_count", [[["customer_rank", ">", 0],
                                                   ["is_company", "=", True]]])
    personas = models.execute_kw(DB, uid, API_KEY, "res.partner",
                                 "search_count", [[["customer_rank", ">", 0],
                                                   ["is_company", "=", False]]])
    sin_rnc  = models.execute_kw(DB, uid, API_KEY, "res.partner",
                                 "search_count", [[["customer_rank", ">", 0],
                                                   ["vat", "=", False]]])
    sin_mail = models.execute_kw(DB, uid, API_KEY, "res.partner",
                                 "search_count", [[["customer_rank", ">", 0],
                                                   ["email", "=", False]]])

    print(f"  Clientes registrados:        {total}")
    print(f"    Empresas:                  {empresas}")
    print(f"    Personas físicas:          {personas}")
    print(f"  Sin RNC/cédula (campo vat):  {sin_rnc}"
          f"   <- riesgo fiscal si facturan")
    print(f"  Sin correo electrónico:      {sin_mail}"
          f"   <- limita envío automático de comprobantes")
    print()


if __name__ == "__main__":
    uid, models = conectar()
    analizar(models, uid, "res.partner", "Clientes y proveedores")
    try:
        perfil_clientes(models, uid)
    except Exception as e:
        print(f"  Perfil no disponible: {e}\n")
    print("Listo.")
