"""
05 v2 - Extracción del dataset para Power BI
la firma | Daniel Castillo

QUÉ CAMBIÓ RESPECTO A LA VERSIÓN 1

  1. Marca los registros migrados.
     La carga masiva de agosto 2026 trae fechas de vencimiento asignadas al
     momento de la carga, no las originales. Sin separarlas, cualquier
     reporte de antigüedad subestima la mora. Ahora se marcan con una
     columna explícita.

  2. Calcula la antigüedad dentro del dataset.
     Días vencidos y tramo de antigüedad se calculan aquí, no en DAX, para
     que la regla quede escrita una sola vez y sea auditable.

  3. Corrige el sesgo de supervivencia en el ciclo de cobro.
     La versión 1 promediaba solo las facturas cobradas. Ahora se reporta
     además cuántas facturas no tienen ningún cobro cruzado, que es la
     información que el promedio ocultaba.

  4. Declara la población de cada porcentaje.
     Todo porcentaje del resumen dice sobre qué conjunto se calculó. Este
     fue el origen de los tres errores de medición del diagnóstico inicial.

  5. Verifica su propia salida.
     Al terminar comprueba que las 8 tablas tengan las columnas que el
     modelo de Power BI espera. Un nombre de columna cambiado no produce
     ningún error en Power BI: deja el visual vacío, y eso no se nota
     hasta que alguien mira el tablero.

SOLO LECTURA sobre el ERP.
"""

import xmlrpc.client
import csv
import os
from datetime import date, timedelta

# ---------------------------------------------------------------
# ---------------------------------------------------------------
# CONEXIÓN AL ERP
# ---------------------------------------------------------------
URL     = os.environ.get("ODOO_URL",     "https://ERP.EJEMPLO.COM")
DB      = os.environ.get("ODOO_DB",      "base_de_datos")
USER    = os.environ.get("ODOO_USER",    "usuario@empresa.com")
API_KEY = os.environ.get("ODOO_API_KEY", "")

SALIDA = "dataset"
ANONIMIZAR = False          # True para capturas de portafolio

# Fecha de referencia para calcular antigüedad. None = hoy.
FECHA_CORTE = None

# ---------------------------------------------------------------
# VENTANA DE MIGRACIÓN
#
# El sistema NO tiene un campo que identifique los registros migrados.
# Esa es precisamente la recomendación número 1 del diagnóstico.
# Mientras no exista, se identifican por la ventana de carga, que es
# conocimiento del negocio y no un dato del sistema.
#
# Si la empresa agrega el campo, borra esta sección y usa el campo real.
# ---------------------------------------------------------------
MIGRACION_DESDE = "2026-08-01"
MIGRACION_HASTA = "2026-08-31"


def hoy():
    return date.fromisoformat(FECHA_CORTE) if FECHA_CORTE else date.today()


def conectar():
    # Si la clave está vacía, detenerse aquí con un mensaje claro.
    # Sin esto, el intento de conexión falla más adelante con
    # "Autenticación fallida", que manda a buscar el problema donde no está.
    if not API_KEY:
        raise SystemExit(
            "Falta la clave API.\n"
            "Pégala en la línea  API_KEY = \"...\"  al inicio de este archivo."
        )
    common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
    uid = common.authenticate(DB, USER, API_KEY, {})
    if not uid:
        raise SystemExit("Autenticación fallida.")
    print(f"Conectado. UID = {uid}\n")
    return uid, xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")


def rel_id(v):
    return v[0] if isinstance(v, list) and v else None


def rel_nom(v):
    return v[1] if isinstance(v, list) and len(v) > 1 else ""


def escribir(nombre, filas, campos=None):
    os.makedirs(SALIDA, exist_ok=True)
    campos = campos or (list(filas[0].keys()) if filas else [])
    with open(os.path.join(SALIDA, nombre), "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    print(f"  {nombre:<28} {len(filas):>6} filas")


def dias_entre(desde, hasta):
    if not desde or not hasta:
        return None
    try:
        return (date.fromisoformat(hasta) - date.fromisoformat(desde)).days
    except ValueError:
        return None


def tramo(dias):
    if dias is None:
        return "Sin fecha"
    if dias < 0:
        return "Por vencer"
    if dias <= 30:
        return "1-30 días"
    if dias <= 60:
        return "31-60 días"
    if dias <= 90:
        return "61-90 días"
    if dias <= 180:
        return "91-180 días"
    return "Más de 180 días"


# ---------------------------------------------------------------
def extraer_facturas(models, uid):
    print("Extrayendo facturas...")
    campos = ["name", "invoice_date", "invoice_date_due", "date",
              "amount_untaxed", "amount_tax", "amount_total", "amount_residual",
              "partner_id", "commercial_partner_id", "company_id", "journal_id",
              "invoice_user_id", "invoice_payment_term_id", "payment_state",
              "l10n_do_ncf", "l10n_do_sequence_prefix", "currency_id",
              "create_date"]

    regs = models.execute_kw(DB, uid, API_KEY, "account.move", "search_read",
                             [[["move_type", "=", "out_invoice"],
                               ["state", "=", "posted"]]],
                             {"fields": campos})
    corte = hoy().isoformat()
    filas = []

    for r in regs:
        ncf = r.get("l10n_do_ncf") or ""
        pref = ncf[:3].upper() if len(ncf) >= 3 else ""
        segmento = {
            "B01": "B2B - Crédito Fiscal",
            "B02": "B2C - Consumo Final",
            "B04": "Nota de Crédito",
            "B14": "Régimen Especial",
            "B15": "Gubernamental",
        }.get(pref, f"Otro ({pref})" if pref else "Sin NCF")

        f_fac = r.get("invoice_date") or ""
        f_ven = r.get("invoice_date_due") or ""
        saldo = r.get("amount_residual") or 0

        # ¿Registro migrado? Por ventana de carga, no por campo del sistema.
        migrada = bool(f_fac and MIGRACION_DESDE <= f_fac <= MIGRACION_HASTA)

        dv = dias_entre(f_ven, corte) if saldo > 0 else None

        filas.append({
            "id_factura": r["id"],
            "numero": r.get("name") or "",
            # Llave real en multi-empresa: la numeración se repite entre entidades
            "clave_unica": f"{rel_id(r.get('company_id'))}-{r.get('name') or ''}",
            "ncf": ncf,
            "prefijo_ncf": pref,
            "segmento_fiscal": segmento,
            "fecha_factura": f_fac,
            "fecha_vencimiento": f_ven,
            "fecha_contable": r.get("date") or "",
            "plazo_credito_dias": dias_entre(f_fac, f_ven),
            "es_migrada": 1 if migrada else 0,
            "origen_registro": "Migrado de sistema anterior" if migrada
                               else "Creado en el sistema",
            "antiguedad_confiable": 0 if migrada else 1,
            "dias_vencido": dv if dv is not None else "",
            "tramo_antiguedad": tramo(dv) if saldo > 0 else "Cobrada",
            "id_cliente": rel_id(r.get("partner_id")),
            "id_cliente_matriz": rel_id(r.get("commercial_partner_id")),
            "id_entidad": rel_id(r.get("company_id")),
            "id_responsable": rel_id(r.get("invoice_user_id")),
            "condicion_pago": rel_nom(r.get("invoice_payment_term_id")),
            "monto_sin_impuesto": r.get("amount_untaxed") or 0,
            "impuesto": r.get("amount_tax") or 0,
            "monto_total": r.get("amount_total") or 0,
            "saldo_pendiente": saldo,
            "monto_cobrado": (r.get("amount_total") or 0) - saldo,
            "estado_cobro": r.get("payment_state") or "",
            "esta_pagada": 1 if saldo == 0 else 0,
        })

    escribir("hechos_facturas.csv", filas)
    return filas


def extraer_lineas(models, uid, ids):
    print("Extrayendo líneas de factura...")
    campos = ["move_id", "name", "product_id", "quantity", "price_unit",
              "discount", "price_subtotal", "price_total", "account_id",
              "partner_id", "company_id", "display_type", "date"]

    # display_type = product: solo líneas de servicio.
    # Sin este filtro se incluyen apuntes de impuesto y de cuenta por cobrar,
    # que fue el origen del falso hallazgo sobre el uso del catálogo.
    regs = models.execute_kw(DB, uid, API_KEY, "account.move.line",
                             "search_read",
                             [[["move_id", "in", ids],
                               ["display_type", "=", "product"]]],
                             {"fields": campos})
    filas = []
    for r in regs:
        pu = r.get("price_unit") or 0
        cant = r.get("quantity") or 0
        pct = r.get("discount") or 0
        filas.append({
            "id_linea": r["id"],
            "id_factura": rel_id(r.get("move_id")),
            "descripcion": (r.get("name") or "").replace("\n", " ").strip(),
            "id_servicio": rel_id(r.get("product_id")),
            "servicio_catalogo": rel_nom(r.get("product_id")),
            "usa_catalogo": 1 if r.get("product_id") else 0,
            "cantidad": cant,
            "precio_unitario": pu,
            "descuento_pct": pct,
            "monto_descuento": round(pu * cant * pct / 100, 2),
            "tiene_descuento": 1 if pct else 0,
            "subtotal": r.get("price_subtotal") or 0,
            "total_linea": r.get("price_total") or 0,
            "id_cliente": rel_id(r.get("partner_id")),
            "id_entidad": rel_id(r.get("company_id")),
        })
    escribir("hechos_lineas.csv", filas)
    return filas


def extraer_cobros(models, uid, facturas):
    print("Extrayendo cobros y construyendo el puente...")
    campos = ["name", "date", "amount", "partner_id", "company_id", "journal_id",
              "payment_method_line_id", "state", "is_reconciled", "is_matched",
              "invoice_ids"]
    regs = models.execute_kw(DB, uid, API_KEY, "account.payment", "search_read",
                             [[["partner_type", "=", "customer"]]],
                             {"fields": campos})

    fecha_fac = {f["id_factura"]: f["fecha_factura"] for f in facturas}
    migrada = {f["id_factura"]: f["es_migrada"] for f in facturas}

    cobros, puente = [], []
    for r in regs:
        cobros.append({
            "id_cobro": r["id"],
            "referencia": r.get("name") or "",
            "fecha_cobro": r.get("date") or "",
            "monto_cobrado": r.get("amount") or 0,
            "id_cliente": rel_id(r.get("partner_id")),
            "id_entidad": rel_id(r.get("company_id")),
            "metodo_pago": rel_nom(r.get("payment_method_line_id")),
            "estado": r.get("state") or "",
            "aplicado_a_factura": 1 if r.get("is_reconciled") else 0,
            "conciliado_con_banco": 1 if r.get("is_matched") else 0,
            "facturas_saldadas": len(r.get("invoice_ids") or []),
        })

        for idf in (r.get("invoice_ids") or []):
            d = dias_entre(fecha_fac.get(idf, ""), r.get("date") or "")
            # Días negativos = pago registrado antes de la factura (anticipo).
            # Se marcan en lugar de borrarse: distorsionan el promedio pero
            # son información válida sobre la operación.
            puente.append({
                "id_cobro": r["id"],
                "id_factura": idf,
                "fecha_cobro": r.get("date") or "",
                "fecha_factura": fecha_fac.get(idf, ""),
                "dias_hasta_cobro": d if d is not None else "",
                "es_anticipo": 1 if (d is not None and d < 0) else 0,
                "valido_para_promedio": 1 if (d is not None and d >= 0) else 0,
                "factura_migrada": migrada.get(idf, 0),
            })

    escribir("hechos_cobros.csv", cobros)
    escribir("puente_cobro_factura.csv", puente)
    return cobros, puente


def extraer_clientes(models, uid):
    print("Extrayendo dimensión de clientes...")
    campos = ["name", "vat", "email", "phone", "is_company",
              "commercial_partner_id", "parent_id", "country_id",
              "l10n_do_dgii_tax_payer_type", "l10n_do_rnc_economic_activity",
              "l10n_do_rnc_status", "l10n_do_rnc_payment_regimen",
              "l10n_do_rnc_operation_start", "customer_rank"]
    # Filtro por cliente. Sin él se incluyen proveedores y contactos internos,
    # que fue el origen del falso 18% de correos registrados.
    regs = models.execute_kw(DB, uid, API_KEY, "res.partner", "search_read",
                             [[["customer_rank", ">", 0]]], {"fields": campos})
    filas = []
    for i, r in enumerate(regs, 1):
        filas.append({
            "id_cliente": r["id"],
            "cliente": f"Cliente {i:04d}" if ANONIMIZAR else (r.get("name") or ""),
            "tiene_rnc": 1 if r.get("vat") else 0,
            "tiene_correo": 1 if r.get("email") else 0,
            "tiene_telefono": 1 if r.get("phone") else 0,
            "tipo": "Empresa" if r.get("is_company") else "Persona física",
            "tipo_contribuyente": r.get("l10n_do_dgii_tax_payer_type") or "Sin clasificar",
            "actividad_economica": r.get("l10n_do_rnc_economic_activity") or "Sin registrar",
            "estado_dgii": r.get("l10n_do_rnc_status") or "Sin verificar",
            "regimen_pago": r.get("l10n_do_rnc_payment_regimen") or "Sin registrar",
            "inicio_operaciones": r.get("l10n_do_rnc_operation_start") or "",
            "verificado_dgii": 1 if r.get("l10n_do_rnc_status") else 0,
            "id_cliente_matriz": rel_id(r.get("commercial_partner_id")),
            "es_sucursal": 1 if r.get("parent_id") else 0,
            "pais": rel_nom(r.get("country_id")) or "Sin registrar",
        })
    escribir("dim_clientes.csv", filas)
    return filas


def extraer_entidades(models, uid):
    print("Extrayendo dimensión de entidades...")
    regs = models.execute_kw(DB, uid, API_KEY, "res.company", "search_read",
                             [[]], {"fields": ["name", "vat"]})
    filas = [{
        "id_entidad": r["id"],
        "entidad": f"Entidad {chr(64+i)}" if ANONIMIZAR else (r.get("name") or ""),
        "tiene_rnc": 1 if r.get("vat") else 0,
    } for i, r in enumerate(regs, 1)]
    escribir("dim_entidades.csv", filas)
    return filas


def extraer_responsables(models, uid):
    print("Extrayendo dimensión de responsables...")
    regs = models.execute_kw(DB, uid, API_KEY, "res.users", "search_read",
                             [[]], {"fields": ["name"]})
    filas = [{
        "id_responsable": r["id"],
        "responsable": f"Responsable {i}" if ANONIMIZAR else (r.get("name") or ""),
    } for i, r in enumerate(regs, 1)]
    escribir("dim_responsables.csv", filas)
    return filas


def generar_calendario(facturas):
    print("Generando dimensión calendario...")
    fechas = [f["fecha_factura"] for f in facturas if f["fecha_factura"]]
    if not fechas:
        return []
    ini = date.fromisoformat(min(fechas)).replace(day=1)
    fin = date(date.fromisoformat(max(fechas)).year, 12, 31)
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes",
            "Sábado", "Domingo"]
    filas, d = [], ini
    while d <= fin:
        filas.append({
            "fecha": d.isoformat(), "año": d.year, "mes_numero": d.month,
            "mes_nombre": meses[d.month - 1],
            "año_mes": f"{d.year}-{d.month:02d}",
            "trimestre": f"T{(d.month-1)//3+1}",
            "año_trimestre": f"{d.year}-T{(d.month-1)//3+1}",
            "dia": d.day, "dia_semana": dias[d.weekday()],
            "es_fin_de_semana": 1 if d.weekday() >= 5 else 0,
        })
        d += timedelta(days=1)
    escribir("dim_calendario.csv", filas)
    return filas


# ---------------------------------------------------------------
def resumen(facturas, lineas, cobros, puente, clientes):
    L = "=" * 66
    print("\n" + L)
    print("LÍNEA BASE")
    print("Cada porcentaje indica sobre qué población se calculó.")
    print(L)

    nat = [f for f in facturas if not f["es_migrada"]]
    mig = [f for f in facturas if f["es_migrada"]]
    ing = sum(f["monto_sin_impuesto"] for f in facturas)
    pen = sum(f["saldo_pendiente"] for f in facturas)

    print(f"\n  Facturas emitidas y publicadas: {len(facturas)}")
    print(f"    Creadas en el sistema:        {len(nat)}")
    print(f"    Migradas (ventana agosto):    {len(mig)}")
    print(f"  Ingreso sin impuestos:          {ing:,.2f}")
    print(f"  Saldo pendiente:                {pen:,.2f}"
          f"  ({100*pen/ing:.1f}% del ingreso total)" if ing else "")

    # --- ANTIGÜEDAD, SEPARADA ---
    print(f"\n  ANTIGÜEDAD DE CARTERA — registros nativos")
    print(f"  (población: {len(nat)} facturas creadas en el sistema)")
    orden = ["Por vencer", "1-30 días", "31-60 días", "61-90 días",
             "91-180 días", "Más de 180 días"]
    for t in orden:
        g = [f for f in nat if f["tramo_antiguedad"] == t]
        if g:
            m = sum(f["saldo_pendiente"] for f in g)
            print(f"     {t:<18} {len(g):>3} fact   {m:>14,.2f}")
    vieja = sum(f["saldo_pendiente"] for f in nat
                if f["tramo_antiguedad"] in ("61-90 días", "91-180 días",
                                             "Más de 180 días"))
    print(f"     Mora verificable (+60 días):      {vieja:>14,.2f}")

    pen_mig = sum(f["saldo_pendiente"] for f in mig)
    print(f"\n  ANTIGÜEDAD NO DETERMINABLE — registros migrados")
    print(f"  (población: {len(mig)} facturas cargadas desde otro sistema)")
    print(f"     Saldo pendiente:                  {pen_mig:>14,.2f}")
    print(f"     La fecha de vencimiento de estos registros corresponde")
    print(f"     a la carga, no al vencimiento original. Su antigüedad real")
    print(f"     requiere el dato del sistema anterior.")

    # --- SEGMENTACIÓN ---
    print(f"\n  MEZCLA FISCAL  (población: {len(facturas)} facturas)")
    seg = {}
    for f in facturas:
        seg[f["segmento_fiscal"]] = seg.get(f["segmento_fiscal"], 0) + f["monto_sin_impuesto"]
    for s, m in sorted(seg.items(), key=lambda x: -x[1]):
        print(f"     {s:<30} {m:>14,.2f}  ({100*m/ing:>5.1f}%)")

    # --- CONCENTRACIÓN ---
    porcli = {}
    for f in facturas:
        k = f["id_cliente_matriz"] or f["id_cliente"]
        porcli[k] = porcli.get(k, 0) + f["monto_sin_impuesto"]
    top = sorted(porcli.values(), reverse=True)
    print(f"\n  CONCENTRACIÓN  (población: {len(porcli)} clientes con facturación)")
    for n in (1, 3, 5, 10):
        if len(top) >= n:
            print(f"     Top {n:<2} concentran  {100*sum(top[:n])/ing:>5.1f}%")
    print(f"     Clientes con facturación: {len(porcli)} de {len(clientes)} registrados")

    # --- CICLO DE COBRO, SIN SESGO ---
    val = [int(p["dias_hasta_cobro"]) for p in puente
           if p["valido_para_promedio"] == 1 and str(p["dias_hasta_cobro"]).isdigit()]
    ant = sum(1 for p in puente if p["es_anticipo"] == 1)
    con_cobro = {p["id_factura"] for p in puente}
    sin_cobro = [f for f in facturas if f["id_factura"] not in con_cobro]

    print(f"\n  CICLO DE COBRO")
    if val:
        o = sorted(val)
        print(f"  (población: {len(val)} cruces factura-pago con días positivos)")
        print(f"     Promedio:  {sum(val)/len(val):.1f} días")
        print(f"     Mediana:   {o[len(o)//2]} días")
        print(f"     Rango:     {min(val)} a {max(val)} días")
    print(f"     Anticipos excluidos del promedio: {ant}")
    print(f"\n     ATENCIÓN — el promedio anterior describe solo las facturas")
    print(f"     que llegaron a cobrarse. Facturas sin ningún cobro cruzado:")
    print(f"     {len(sin_cobro)} de {len(facturas)}"
          f"  ({100*len(sin_cobro)/len(facturas):.1f}%)")
    print(f"     Saldo de esas facturas: "
          f"{sum(f['saldo_pendiente'] for f in sin_cobro):,.2f}")

    # --- CALIDAD ---
    print(f"\n  CALIDAD DE LA CARTERA  (población: {len(clientes)} clientes)")
    for et, k in [("Con RNC", "tiene_rnc"), ("Con correo", "tiene_correo"),
                  ("Con teléfono", "tiene_telefono"),
                  ("Verificados en DGII", "verificado_dgii")]:
        n = sum(c[k] for c in clientes)
        print(f"     {et:<22} {n:>4} de {len(clientes)}  ({100*n/len(clientes):>5.1f}%)")

    print(f"\n  CONCILIACIÓN BANCARIA  (población: {len(cobros)} cobros)")
    sb = sum(1 for c in cobros if not c["conciliado_con_banco"])
    print(f"     Sin conciliar con banco: {sb} de {len(cobros)}"
          f"  ({100*sb/len(cobros):.1f}%)" if cobros else "")

    print(f"\n  CATÁLOGO DE SERVICIOS  (población: {len(lineas)} líneas de servicio)")
    cc = sum(1 for l in lineas if l["usa_catalogo"])
    if lineas:
        print(f"     Referencian el catálogo: {cc} de {len(lineas)}"
              f"  ({100*cc/len(lineas):.1f}%)")
    cd = [l for l in lineas if l["tiene_descuento"]]
    print(f"     Con descuento registrado: {len(cd)}"
          f"   monto {sum(l['monto_descuento'] for l in cd):,.2f}")


# ---------------------------------------------------------------
# VERIFICACIÓN DE SALIDA
#
# El modelo de Power BI espera nombres de columna exactos. Si uno cambia,
# Power BI NO da error: deja el visual vacío o colapsado, y eso no se nota
# hasta que alguien mira el tablero.
#
# Esta comprobación corre al final de cada ejecución. Como escribe en
# pantalla, el .bat la deja registrada en log_actualizacion.txt, así que
# una corrida desatendida también queda auditada.
# ---------------------------------------------------------------
COLUMNAS_ESPERADAS = {
    "hechos_facturas.csv": [
        "id_factura", "numero", "clave_unica", "ncf", "prefijo_ncf",
        "segmento_fiscal", "fecha_factura", "fecha_vencimiento",
        "es_migrada", "origen_registro", "antiguedad_confiable",
        "dias_vencido", "tramo_antiguedad", "id_cliente",
        "id_cliente_matriz", "id_entidad", "id_responsable",
        "monto_sin_impuesto", "impuesto", "monto_total",
        "saldo_pendiente", "monto_cobrado", "estado_cobro", "esta_pagada",
    ],
    "hechos_lineas.csv": [
        "id_linea", "id_factura", "descripcion", "id_servicio",
        "servicio_catalogo", "usa_catalogo", "precio_unitario",
        "descuento_pct", "tiene_descuento", "subtotal", "total_linea",
    ],
    "hechos_cobros.csv": [
        "id_cobro", "referencia", "fecha_cobro", "monto_cobrado",
        "id_cliente", "id_entidad", "metodo_pago", "aplicado_a_factura",
        "conciliado_con_banco", "facturas_saldadas",
    ],
    "puente_cobro_factura.csv": [
        "id_cobro", "id_factura", "dias_hasta_cobro", "es_anticipo",
        "valido_para_promedio", "factura_migrada",
    ],
    "dim_clientes.csv": [
        "id_cliente", "cliente", "tiene_rnc", "tiene_correo",
        "tiene_telefono", "tipo", "actividad_economica",
        "id_cliente_matriz", "es_sucursal",
    ],
    "dim_entidades.csv":    ["id_entidad", "entidad"],
    "dim_responsables.csv": ["id_responsable", "responsable"],
    # Las tres con eñe son las que ya rompieron el tablero una vez.
    "dim_calendario.csv": [
        "fecha", "año", "mes_numero", "mes_nombre", "año_mes",
        "trimestre", "año_trimestre", "dia", "dia_semana",
        "es_fin_de_semana",
    ],
}


def verificar_salida():
    L = "=" * 66
    print("\n" + L)
    print("VERIFICACIÓN DE SALIDA")
    print(L)

    problemas = []

    for archivo, esperadas in COLUMNAS_ESPERADAS.items():
        ruta = os.path.join(SALIDA, archivo)

        if not os.path.exists(ruta):
            print(f"  FALTA    {archivo}")
            problemas.append(f"{archivo}: el archivo no se generó")
            continue

        with open(ruta, encoding="utf-8-sig", newline="") as f:
            cabecera = next(csv.reader(f), [])
            n = sum(1 for _ in f)

        faltantes = [c for c in esperadas if c not in cabecera]

        if faltantes:
            print(f"  ERROR    {archivo:<28} {n:>6} filas")
            for c in faltantes:
                print(f"           falta la columna: {c}")
            problemas.append(f"{archivo}: faltan {', '.join(faltantes)}")
        else:
            print(f"  OK       {archivo:<28} {n:>6} filas")

    print(L)
    if problemas:
        print("  LA EXTRACCIÓN TERMINÓ, PERO EL MODELO SE VA A ROMPER.")
        print("  No actualices Power BI hasta resolver esto:")
        for p in problemas:
            print(f"    - {p}")
        print(L)
        # Código de salida distinto de cero: el .bat lo registra como ERROR
        raise SystemExit(2)

    print("  Las 8 tablas tienen las columnas que el tablero espera.")
    print("  Seguro actualizar Power BI.")
    print(L)


if __name__ == "__main__":
    uid, models = conectar()
    facturas = extraer_facturas(models, uid)
    lineas = extraer_lineas(models, uid, [f["id_factura"] for f in facturas])
    cobros, puente = extraer_cobros(models, uid, facturas)
    clientes = extraer_clientes(models, uid)
    extraer_entidades(models, uid)
    extraer_responsables(models, uid)
    generar_calendario(facturas)
    resumen(facturas, lineas, cobros, puente, clientes)
    verificar_salida()

    print("""
    ==============================================================
    CARGA EN POWER BI
    ==============================================================

    RELACIONES
      dim_calendario[fecha]       1 -> * hechos_facturas[fecha_factura]
      dim_clientes[id_cliente]    1 -> * hechos_facturas[id_cliente]
      dim_entidades[id_entidad]   1 -> * hechos_facturas[id_entidad]
      dim_responsables            1 -> * hechos_facturas[id_responsable]
      hechos_facturas             1 -> * hechos_lineas[id_factura]
      hechos_facturas             1 -> * puente_cobro_factura[id_factura]
      hechos_cobros               1 -> * puente_cobro_factura[id_cobro]

    Marca dim_calendario como tabla de fechas sobre el campo 'fecha'.

    MEDIDAS BASE
      Ingreso = SUM(hechos_facturas[monto_sin_impuesto])
      Pendiente = SUM(hechos_facturas[saldo_pendiente])
      Facturas = COUNTROWS(hechos_facturas)
      Ticket Promedio = DIVIDE([Ingreso], [Facturas])

    MEDIDAS QUE RESPETAN LAS CORRECCIONES

      -- Antigüedad solo sobre registros con fecha confiable
      Pendiente Antiguedad Confiable =
          CALCULATE([Pendiente], hechos_facturas[antiguedad_confiable] = 1)

      Pendiente Antiguedad Indeterminada =
          CALCULATE([Pendiente], hechos_facturas[es_migrada] = 1)

      -- Ciclo de cobro sin anticipos
      Dias Cobro Promedio =
          CALCULATE(AVERAGE(puente_cobro_factura[dias_hasta_cobro]),
                    puente_cobro_factura[valido_para_promedio] = 1)

      -- Lo que el promedio anterior no muestra
      Facturas Sin Cobro =
          CALCULATE([Facturas],
                    FILTER(hechos_facturas,
                           ISEMPTY(RELATEDTABLE(puente_cobro_factura))))

      -- Concentración
      Ingreso Top 10 Clientes =
          SUMX(TOPN(10, VALUES(dim_clientes[id_cliente]), [Ingreso]), [Ingreso])
      Concentracion Top 10 = DIVIDE([Ingreso Top 10 Clientes], [Ingreso])

    REGLA PARA EL TABLERO
      Ningún visual de antigüedad de cartera debe mezclar registros migrados
      con nativos. Usa es_migrada como segmentador visible, no como filtro
      oculto: quien lea el tablero tiene que saber que la distinción existe.
""")
