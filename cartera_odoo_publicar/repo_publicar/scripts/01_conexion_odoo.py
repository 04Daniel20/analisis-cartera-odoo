"""
01 - Conexión y exploración inicial a Odoo vía XML-RPC
la firma | Daniel Castillo

Objetivo de este script:
  1. Verificar que la conexión funciona
  2. Confirmar qué empresas existen en el sistema
  3. Contar facturas reales
  4. Generar el diccionario de datos de las tablas clave

IMPORTANTE: este script es de SOLO LECTURA. No crea, modifica ni borra nada.
"""

import xmlrpc.client
import csv
import os

# ---------------------------------------------------------------
# CONFIGURACIÓN — completa estos cuatro valores
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

SALIDA = "salida"  # carpeta donde se guardan los CSV


# ---------------------------------------------------------------
# 1. CONEXIÓN
# ---------------------------------------------------------------
def conectar():
    common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
    version = common.version()
    print(f"Odoo versión: {version.get('server_version')}")

    uid = common.authenticate(DB, USER, API_KEY, {})
    if not uid:
        raise SystemExit(
            "Autenticación fallida.\n"
            "Revisa: nombre de la base de datos, usuario y clave API."
        )
    print(f"Conectado. UID = {uid}\n")

    models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")
    return uid, models


def leer(models, uid, modelo, dominio, campos, limite=None):
    """Envoltorio de search_read. Solo lectura."""
    opciones = {"fields": campos}
    if limite:
        opciones["limit"] = limite
    return models.execute_kw(DB, uid, API_KEY, modelo, "search_read",
                             [dominio], opciones)


def contar(models, uid, modelo, dominio):
    return models.execute_kw(DB, uid, API_KEY, modelo, "search_count", [dominio])


# ---------------------------------------------------------------
# 2. ¿QUÉ EMPRESAS HAY? 
# ---------------------------------------------------------------
def explorar_empresas(models, uid):
    print("=" * 60)
    print("EMPRESAS EN EL SISTEMA")
    print("=" * 60)

    empresas = leer(models, uid, "res.company", [],
                    ["id", "name", "vat", "parent_id"])

    for e in empresas:
        padre = e["parent_id"][1] if e.get("parent_id") else "-"
        print(f"  [{e['id']:>3}] {e['name']:<45} RNC: {e.get('vat') or '-':<12} Padre: {padre}")

    print(f"\nTotal: {len(empresas)} empresas\n")
    return empresas


# ---------------------------------------------------------------
# 3. VOLUMEN REAL DE FACTURACIÓN POR EMPRESA
# ---------------------------------------------------------------
def volumen_facturacion(models, uid, empresas):
    print("=" * 60)
    print("FACTURAS DE CLIENTE POR EMPRESA")
    print("=" * 60)

    total_global = 0
    for e in empresas:
        # move_type = out_invoice  ->  factura de cliente
        dominio = [["move_type", "=", "out_invoice"],
                   ["company_id", "=", e["id"]]]
        n = contar(models, uid, "account.move", dominio)

        # cuántas están publicadas (posted) vs borrador (draft)
        n_post = contar(models, uid, "account.move",
                        dominio + [["state", "=", "posted"]])
        n_draft = contar(models, uid, "account.move",
                         dominio + [["state", "=", "draft"]])

        total_global += n
        if n:
            print(f"  {e['name']:<45} total:{n:>5}  publicadas:{n_post:>5}  borrador:{n_draft:>4}")

    print(f"\nTOTAL DE FACTURAS EN TODO EL SISTEMA: {total_global}")
    print("(Si este número es mucho mayor que 85, la vista del navegador")
    print(" estaba filtrada por empresa activa.)\n")


# ---------------------------------------------------------------
# 4. RANGO TEMPORAL — ¿cuánto histórico hay realmente?
# ---------------------------------------------------------------
def rango_temporal(models, uid):
    print("=" * 60)
    print("RANGO TEMPORAL DE LA DATA")
    print("=" * 60)

    dominio = [["move_type", "=", "out_invoice"], ["state", "=", "posted"]]

    primera = models.execute_kw(DB, uid, API_KEY, "account.move", "search_read",
                                [dominio],
                                {"fields": ["invoice_date", "name"],
                                 "order": "invoice_date asc", "limit": 1})
    ultima = models.execute_kw(DB, uid, API_KEY, "account.move", "search_read",
                               [dominio],
                               {"fields": ["invoice_date", "name"],
                                "order": "invoice_date desc", "limit": 1})

    if primera:
        print(f"  Primera factura: {primera[0]['invoice_date']}  ({primera[0]['name']})")
    if ultima:
        print(f"  Última factura:  {ultima[0]['invoice_date']}  ({ultima[0]['name']})")
    print()


# ---------------------------------------------------------------
# 5. DICCIONARIO DE DATOS  
# ---------------------------------------------------------------
MODELOS_CLAVE = {
    "account.move":       "Facturas y asientos contables",
    "account.move.line":  "Líneas de detalle de factura",
    "res.partner":        "Clientes y proveedores",
    "account.payment":    "Pagos registrados",
    "product.product":    "Productos y servicios",
}


def diccionario_datos(models, uid):
    print("=" * 60)
    print("GENERANDO DICCIONARIO DE DATOS")
    print("=" * 60)

    os.makedirs(SALIDA, exist_ok=True)

    for modelo, descripcion in MODELOS_CLAVE.items():
        campos = models.execute_kw(DB, uid, API_KEY, modelo, "fields_get", [],
                                   {"attributes": ["string", "type", "required",
                                                   "readonly", "relation", "help"]})

        archivo = os.path.join(SALIDA, f"diccionario_{modelo.replace('.', '_')}.csv")
        with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["campo_tecnico", "etiqueta", "tipo", "requerido",
                        "solo_lectura", "modelo_relacionado", "ayuda"])
            for nombre, meta in sorted(campos.items()):
                w.writerow([
                    nombre,
                    meta.get("string", ""),
                    meta.get("type", ""),
                    "Sí" if meta.get("required") else "No",
                    "Sí" if meta.get("readonly") else "No",
                    meta.get("relation", ""),
                    (meta.get("help") or "").replace("\n", " ")[:200],
                ])

        print(f"  {modelo:<22} {len(campos):>4} campos  ->  {archivo}")
        print(f"     ({descripcion})")

    print("\nEstos CSV son la base de tu diccionario de datos.")
    print("No los entregues crudos: revísalos y añade la columna de")
    print("significado de negocio. Esa columna es tu aporte, no la del script.\n")


# ---------------------------------------------------------------
# 6. VERIFICAR SI EXISTEN HOJAS DE HORAS (para rentabilidad por cliente)
# ---------------------------------------------------------------
def verificar_horas(models, uid):
    print("=" * 60)
    print("¿HAY REGISTRO DE HORAS?  (decide el indicador de rentabilidad)")
    print("=" * 60)

    try:
        n = contar(models, uid, "account.analytic.line", [])
        print(f"  Líneas analíticas / hojas de horas encontradas: {n}")
        if n > 0:
            print("  -> El indicador de RENTABILIDAD POR CLIENTE es viable.")
        else:
            print("  -> Módulo presente pero sin datos. Rentabilidad queda en espera.")
    except Exception:
        print("  -> El modelo de hojas de horas no está disponible.")
        print("     Sustituir rentabilidad por análisis de embudo (CRM).")
    print()


# ---------------------------------------------------------------
if __name__ == "__main__":
    uid, models = conectar()
    empresas = explorar_empresas(models, uid)
    volumen_facturacion(models, uid, empresas)
    rango_temporal(models, uid)
    verificar_horas(models, uid)
    diccionario_datos(models, uid)
    print("Listo.")
