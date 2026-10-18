"""
00 - Generador del dataset de ejemplo
=====================================

QUE HACE

  Produce los ocho CSV de la carpeta dataset_ejemplo/ a partir de numeros
  aleatorios. Ningun dato de este repositorio proviene de una empresa real.

POR QUE EXISTE

  El modelo, los scripts y las medidas DAX de este proyecto se construyeron
  contra un ERP en produccion. Esos datos son de su propietario y no se
  publican. Para que el trabajo sea reproducible y revisable hace falta un
  dataset con la misma FORMA: los mismos esquemas, los mismos volumenes,
  las mismas asimetrias y, sobre todo, los mismos defectos de calidad, que
  son los que justifican la mitad de las decisiones del modelo.

  Este generador construye ese dataset. Sale de una semilla fija, asi que
  cualquiera puede ejecutarlo y obtener exactamente los mismos archivos.

QUE REPRODUCE A PROPOSITO

  - Facturacion por tandas, no continua: pocas fechas de emision distintas.
  - Ingreso muy concentrado: una decena de clientes explica la mayor parte.
  - Un lote de facturas migradas de un sistema anterior cuya fecha de
    vencimiento quedo sobrescrita con la fecha de emision. La antiguedad de
    cartera de ese lote no es confiable, y el modelo lo marca.
  - Cobros sin conciliar con banco en proporcion alta.
  - Lineas de factura que no usan el catalogo de servicios.
  - Clientes duplicados por grafia: el mismo nombre escrito de dos formas.
  - Campos de contacto y de registro fiscal a medio poblar.

  Esos no son errores del generador. Son el objeto de estudio.

COMO SE EJECUTA

      python 00_generar_dataset_ejemplo.py

  Escribe en ../dataset_ejemplo/ si lo ejecutas desde scripts/, o en
  ./dataset_ejemplo/ si lo ejecutas desde la raiz del repositorio.
"""

import csv
import os
import random
import hashlib
import datetime as dt

# ---------------------------------------------------------------------
# PARAMETROS
# ---------------------------------------------------------------------
SEMILLA = 90218

FECHA_INICIO = dt.date(2025, 3, 1)
FECHA_FIN = dt.date(2026, 12, 31)   # el calendario cubre hasta fin de ano
FECHA_CORTE = dt.date(2026, 9, 30)  # ultimo dia con movimiento

N_CLIENTES = 188
N_ENTIDADES = 8
N_RESPONSABLES = 14
N_FACTURAS = 186
N_FECHAS_EMISION = 29      # la facturacion ocurre en tandas
N_LINEAS_EXTRA = 27        # facturas con mas de una linea
N_COBROS = 93

PCT_MIGRADAS = 0.538       # 100 de 186
PCT_SIN_CONCILIAR = 0.677  # 63 de 93
ITBIS = 0.18

rnd = random.Random(SEMILLA)

# ---------------------------------------------------------------------
# CATALOGOS INVENTADOS
# ---------------------------------------------------------------------
GIROS = ["Constructora", "Inversiones", "Distribuidora", "Comercial",
         "Servicios", "Transporte", "Agropecuaria", "Inmobiliaria",
         "Importadora", "Consultores", "Suministros", "Logistica",
         "Farmaceutica", "Textiles", "Metalurgica", "Editorial",
         "Seguridad", "Tecnologia", "Alimentos", "Refrigeracion",
         "Ferreteria", "Automotriz", "Papelera", "Panificadora"]

LUGARES = ["del Caribe", "del Este", "Hispaniola", "Duarte", "del Norte",
           "Quisqueya", "Samana", "Bavaro", "Cibao", "Ozama", "Haina",
           "Jarabacoa", "La Vega", "Higuey", "Barahona", "Monte Plata",
           "San Isidro", "Los Alcarrizos", "Boca Chica", "Villa Mella",
           "del Sur", "Las Terrenas", "Moca", "Bani"]

FORMAS = ["SRL", "SA", "EIRL", "SRL", "SAS", "SRL"]

NOM_H = ["Rafael", "Juan", "Pedro", "Luis", "Jose", "Miguel", "Carlos",
         "Ramon", "Francisco", "Angel", "Eduardo", "Hector", "Manuel",
         "Julio", "Victor", "Fernando", "Alberto", "Ernesto", "Rodolfo",
         "Amaury", "Wilson", "Elvis"]

NOM_M = ["Altagracia", "Rosa", "Mercedes", "Yokasta", "Ingrid", "Carmen",
         "Milagros", "Yudelka", "Scarlet", "Nurys", "Dalia", "Ivelisse",
         "Esperanza", "Minerva", "Clara", "Josefina", "Belkis", "Noemi",
         "Massiel", "Yaquelin", "Ruth", "Katiuska"]

APE = ["Peralta", "Jimenez", "Rosario", "Ventura", "Encarnacion", "Medina",
       "Polanco", "Abreu", "Tavarez", "Guerrero", "Lantigua", "Bautista",
       "Sanchez", "Pujols", "Reynoso", "Castro", "Cedeno", "Montero",
       "Severino", "Valdez", "Hiciano", "Mejia", "Dominguez", "Nunez",
       "Carrasco", "Objio", "Terrero", "Zorrilla"]

# Catalogo de servicios de una consultoria contable y fiscal generica.
# Incluye a proposito dos pares escritos de dos formas distintas y una
# errata: son el material del hallazgo de calidad sobre el catalogo.
SERVICIOS = [
    ("Iguala Contable Mensual", 0.26),
    ("Iguala Fiscal", 0.17),
    ("Gestion de Nomina y Seguridad Social", 0.11),
    ("Declaracion Jurada Anual", 0.08),
    ("Constitucion de Empresa", 0.06),
    ("CONSTITUCION DE EMPRESA", 0.02),      # mismo servicio, otra grafia
    ("Modificacion Societaria", 0.05),
    ("Auditoria de Estados Financieros", 0.04),
    ("AUDITORIA DE ESTADOS FINACIEROS", 0.01),  # errata real de catalogo
    ("Recurso de Reconsideracion", 0.03),
    ("Asesoria Fiscal Puntual", 0.03),
    ("Registro de Marca", 0.02),
    ("Certificacion de Ingresos", 0.02),
    ("Conciliacion Bancaria", 0.02),
    ("Reporte 606 y 607", 0.02),
    ("Regularizacion ante la administracion tributaria", 0.02),
    ("Liquidacion de Personal", 0.02),
]

ACTIVIDADES = [
    "COMERCIO AL POR MENOR EN ESTABLECIMIENTOS NO ESPECIALIZADOS",
    "CONSTRUCCION DE EDIFICIOS RESIDENCIALES",
    "TRANSPORTE DE CARGA POR CARRETERA",
    "ACTIVIDADES DE CONSULTORIA DE GESTION",
    "SERVICIOS DE COMIDAS Y BEBIDAS",
    "VENTA AL POR MAYOR DE ALIMENTOS Y BEBIDAS",
    "ACTIVIDADES INMOBILIARIAS CON BIENES PROPIOS",
    "REPARACION DE VEHICULOS AUTOMOTORES",
    "ENSENANZA PREPRIMARIA Y PRIMARIA",
    "ACTIVIDADES DE ATENCION DE LA SALUD HUMANA",
    "FABRICACION DE PRODUCTOS METALICOS",
    "ACTIVIDADES DE ASOCIACIONES N.C.P.",
]

METODOS = ["Transferencia bancaria", "Cheque", "Efectivo", "Deposito en banco"]

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado",
        "Domingo"]

_usados = set()


def nombre_empresa():
    for _ in range(300):
        n = "%s %s %s" % (rnd.choice(GIROS), rnd.choice(LUGARES),
                          rnd.choice(FORMAS))
        if n not in _usados:
            _usados.add(n)
            return n
    return "Empresa %d SRL" % rnd.randint(1000, 9999)


def nombre_persona():
    for _ in range(300):
        n = "%s %s %s" % (rnd.choice(rnd.choice([NOM_H, NOM_M])),
                          rnd.choice(APE), rnd.choice(APE))
        if n not in _usados:
            _usados.add(n)
            return n
    return "Persona %d" % rnd.randint(1000, 9999)


def elegir(pares):
    """Elige respetando los pesos de una lista de (valor, peso)."""
    total = sum(p for _, p in pares)
    x = rnd.random() * total
    acum = 0.0
    for v, p in pares:
        acum += p
        if x <= acum:
            return v
    return pares[-1][0]


def dinero(x):
    return round(float(x) + 0.0, 2)


# =====================================================================
# 1. CALENDARIO
# =====================================================================
def generar_calendario():
    filas = []
    d = FECHA_INICIO
    while d <= FECHA_FIN:
        filas.append({
            "fecha": d.isoformat(),
            "año": d.year,
            "mes_numero": d.month,
            "mes_nombre": MESES[d.month - 1],
            "año_mes": "%d-%02d" % (d.year, d.month),
            "trimestre": "T%d" % ((d.month - 1) // 3 + 1),
            "año_trimestre": "%d-T%d" % (d.year, (d.month - 1) // 3 + 1),
            "dia": d.day,
            "dia_semana": DIAS[d.weekday()],
            "es_fin_de_semana": 1 if d.weekday() >= 5 else 0,
        })
        d += dt.timedelta(days=1)
    return filas


# =====================================================================
# 2. ENTIDADES  (las sociedades que emiten las facturas)
# =====================================================================
def generar_entidades():
    return [{"id_entidad": i,
             "entidad": nombre_empresa(),
             "tiene_rnc": 1}
            for i in range(1, N_ENTIDADES + 1)]


# =====================================================================
# 3. RESPONSABLES
# =====================================================================
def generar_responsables():
    ids = rnd.sample(range(2, 60), N_RESPONSABLES)
    return [{"id_responsable": i, "responsable": nombre_persona()}
            for i in sorted(ids)]


# =====================================================================
# 4. CLIENTES
# =====================================================================
def generar_clientes():
    ids = sorted(rnd.sample(range(100, 900), N_CLIENTES))
    filas = []
    for pos, idc in enumerate(ids):
        es_empresa = pos < 95
        nombre = nombre_empresa() if es_empresa else nombre_persona()

        # Los campos fiscales solo estan poblados en los clientes que
        # alguien se tomo el trabajo de verificar contra la DGII.
        verificado = 1 if rnd.random() < 0.58 else 0
        tiene_rnc = 1 if rnd.random() < 0.735 else 0

        if verificado:
            estado = elegir([("ACTIVO", 0.59), ("SUSPENDIDO", 0.39),
                             ("CESE TEMPORAL", 0.02)])
            actividad = rnd.choice(ACTIVIDADES)
            regimen = elegir([("NORMAL", 0.93), ("RST", 0.07)])
            pais = "Dominican Republic" if rnd.random() < 0.26 else "Sin registrar"
            inicio = (FECHA_INICIO - dt.timedelta(
                days=rnd.randint(400, 7000))).isoformat()
        else:
            estado = "Sin verificar"
            actividad = "Sin registrar"
            regimen = "Sin registrar"
            pais = "Sin registrar"
            inicio = ""

        filas.append({
            "id_cliente": idc,
            "cliente": nombre,
            "tiene_rnc": tiene_rnc,
            "tiene_correo": 1 if rnd.random() < 0.037 else 0,
            "tiene_telefono": 1 if rnd.random() < 0.64 else 0,
            "tipo": "Empresa" if es_empresa else "Persona física",
            "tipo_contribuyente": "taxpayer",
            "actividad_economica": actividad,
            "estado_dgii": estado,
            "regimen_pago": regimen,
            "inicio_operaciones": inicio,
            "verificado_dgii": verificado,
            "id_cliente_matriz": idc,
            "es_sucursal": 0,
            "pais": pais,
        })

    # Un contribuyente extranjero: rompe el supuesto de que todos son RNC.
    filas[-1]["tipo_contribuyente"] = "foreigner"
    filas[-1]["pais"] = "Argentina"

    # Tres sucursales que cuelgan de una matriz. Si el modelo agrupa por
    # id_cliente y no por id_cliente_matriz, la concentracion sale menor
    # de lo que es.
    for f in filas[5:8]:
        f["es_sucursal"] = 1
        f["id_cliente_matriz"] = filas[4]["id_cliente"]

    # Dos clientes duplicados por grafia. Son la misma empresa escrita de
    # dos maneras, con dos id distintos: el hallazgo que obliga a revisar
    # cualquier ranking de concentracion antes de darlo por bueno.
    base = filas[1]["cliente"]
    partes = base.split()
    variante = " ".join(partes[:-1]).upper() + " " + partes[-1].replace(
        "SRL", "S.R.L.").replace("SAS", "S.A.S.").replace("SA", "S.A.")
    filas[2]["cliente"] = variante
    filas[2]["tipo"] = "Empresa"

    return filas


# =====================================================================
# 5. FACTURAS
# =====================================================================
def generar_facturas(clientes, entidades, responsables):
    # Pesos de cliente muy desiguales: unos pocos explican casi todo.
    pesos = {}
    for i, c in enumerate(clientes):
        if i < 10:
            pesos[c["id_cliente"]] = rnd.uniform(9, 21)
        elif i < 50:
            pesos[c["id_cliente"]] = rnd.uniform(1.4, 3.6)
        else:
            pesos[c["id_cliente"]] = rnd.uniform(0.25, 1.1)
    ids_cli = [c["id_cliente"] for c in clientes]
    w = [pesos[i] for i in ids_cli]

    # La facturacion sale en tandas: pocas fechas, muchas facturas cada vez.
    dias_habiles = []
    d = FECHA_INICIO
    while d <= FECHA_CORTE:
        if d.weekday() < 5:
            dias_habiles.append(d)
        d += dt.timedelta(days=1)
    fechas_tanda = sorted(rnd.sample(dias_habiles, N_FECHAS_EMISION))

    matriz = {c["id_cliente"]: c["id_cliente_matriz"] for c in clientes}
    ids_ent = [e["id_entidad"] for e in entidades]
    peso_ent = [0.44, 0.40, 0.055, 0.04, 0.03, 0.02, 0.01, 0.005]
    ids_resp = [r["id_responsable"] for r in responsables]

    n_migradas = int(round(N_FACTURAS * PCT_MIGRADAS))
    migradas = set(rnd.sample(range(N_FACTURAS), n_migradas))

    filas = []
    correlativo_b01 = 0
    correlativo_b02 = 0

    for k in range(N_FACTURAS):
        idf = 300 + k
        fecha = rnd.choice(fechas_tanda)
        es_migrada = k in migradas

        # Credito fiscal cuando el cliente tiene RNC; consumo final si no.
        idc = rnd.choices(ids_cli, weights=w, k=1)[0]
        cli = next(c for c in clientes if c["id_cliente"] == idc)
        b2b = cli["tiene_rnc"] == 1 and rnd.random() < 0.93

        if b2b:
            correlativo_b01 += 1
            ncf = "B01%08d" % correlativo_b01
            prefijo, segmento = "B01", "B2B - Crédito Fiscal"
        else:
            correlativo_b02 += 1
            ncf = "B02%08d" % correlativo_b02
            prefijo, segmento = "B02", "B2C - Consumo Final"

        # Monto: cola larga. La mayoria son igualas pequenas, unas pocas
        # son trabajos grandes que mueven el total entero.
        base = rnd.lognormvariate(9.08, 0.92)
        base = max(1800.0, min(base, 390000.0))
        sin_imp = dinero(round(base, -1))
        impuesto = dinero(sin_imp * ITBIS) if b2b else 0.0
        total = dinero(sin_imp + impuesto)

        condicion = elegir([("30 Days", 0.55), ("", 0.26),
                            ("Immediate Payment", 0.19)])
        plazo = {"30 Days": 30, "Immediate Payment": 0}.get(condicion,
                                                            rnd.choice([0, 4, 9, 10, 10, 30]))

        if es_migrada:
            # El defecto central del dataset: la carga masiva escribio la
            # fecha de emision tambien en el vencimiento. El plazo real se
            # perdio y la antiguedad de ese lote no se puede calcular.
            vencimiento = fecha
            plazo = 0
            confiable = 0
            origen = "Migrado de sistema anterior"
        else:
            vencimiento = fecha + dt.timedelta(days=plazo)
            confiable = 1
            origen = "Creado en el sistema"

        filas.append({
            "id_factura": idf,
            "numero": "FAC/%d/%05d" % (fecha.year, k + 1),
            "clave_unica": "1-FAC/%d/%05d" % (fecha.year, k + 1),
            "ncf": ncf,
            "prefijo_ncf": prefijo,
            "segmento_fiscal": segmento,
            "fecha_factura": fecha.isoformat(),
            "fecha_vencimiento": vencimiento.isoformat(),
            "fecha_contable": fecha.isoformat(),
            "plazo_credito_dias": plazo,
            "es_migrada": 1 if es_migrada else 0,
            "origen_registro": origen,
            "antiguedad_confiable": confiable,
            "dias_vencido": 0,          # se calcula abajo
            "tramo_antiguedad": "",     # se calcula abajo
            "id_cliente": idc,
            "id_cliente_matriz": matriz[idc],
            "id_entidad": rnd.choices(ids_ent, weights=peso_ent, k=1)[0],
            "id_responsable": rnd.choice(ids_resp),
            "condicion_pago": condicion,
            "monto_sin_impuesto": sin_imp,
            "impuesto": impuesto,
            "monto_total": total,
            "saldo_pendiente": total,   # se recalcula tras los cobros
            "monto_cobrado": 0.0,
            "estado_cobro": "not_paid",
            "esta_pagada": 0,
        })
    return filas


# =====================================================================
# 6. LINEAS DE FACTURA
# =====================================================================
def generar_lineas(facturas):
    con_extra = set(rnd.sample(range(len(facturas)), N_LINEAS_EXTRA))
    servicios = [s for s, _ in SERVICIOS]
    id_serv = {s: 40 + i for i, s in enumerate(servicios)}

    filas = []
    idl = 600
    for k, f in enumerate(facturas):
        n = 2 if k in con_extra else 1
        restante_sin = f["monto_sin_impuesto"]
        restante_tot = f["monto_total"]

        for j in range(n):
            ultimo = (j == n - 1)
            if ultimo:
                sub = dinero(restante_sin)
                tot = dinero(restante_tot)
            else:
                frac = rnd.uniform(0.3, 0.6)
                sub = dinero(f["monto_sin_impuesto"] * frac)
                tot = dinero(f["monto_total"] * frac)
                restante_sin -= sub
                restante_tot -= tot

            # Una de cada diez lineas se escribio a mano y no engancha con
            # el catalogo: el ranking por servicio queda incompleto.
            usa_catalogo = 1 if rnd.random() < 0.906 else 0
            serv = elegir(SERVICIOS)
            if usa_catalogo:
                descripcion = serv
                catalogo = serv
                ids = id_serv[serv]
            else:
                descripcion = rnd.choice([
                    "Servicios profesionales del mes",
                    "Honorarios segun acuerdo",
                    "Trabajo adicional solicitado",
                    "Gestion varias", "Servicios varios",
                    "Asistencia administrativa",
                ])
                catalogo = ""
                ids = ""

            cantidad = 1.0
            descuento = 0
            monto_desc = 0.0
            if rnd.random() < 0.012:
                descuento = 20.0
                monto_desc = dinero(sub * 0.2)

            filas.append({
                "id_linea": idl,
                "id_factura": f["id_factura"],
                "descripcion": descripcion,
                "id_servicio": ids,
                "servicio_catalogo": catalogo,
                "usa_catalogo": usa_catalogo,
                "cantidad": cantidad,
                "precio_unitario": sub,
                "descuento_pct": descuento,
                "monto_descuento": monto_desc,
                "tiene_descuento": 1 if descuento else 0,
                "subtotal": sub,
                "total_linea": tot,
                "id_cliente": f["id_cliente"],
                "id_entidad": f["id_entidad"],
            })
            idl += 1
    return filas


# =====================================================================
# 7. COBROS Y PUENTE
# =====================================================================
def generar_cobros(facturas, clientes, entidades):
    """
    Un cobro puede saldar varias facturas y una factura puede recibir
    varios cobros. Por eso existe la tabla puente: la relacion es de
    muchos a muchos y no se puede resolver con una clave en la factura.
    """
    nombre_ent = {e["id_entidad"]: e["entidad"] for e in entidades}

    # Las facturas que se cobran son, sobre todo, las de los clientes
    # grandes: quien factura mas, cobra antes. Ese sesgo es real y es el
    # que hace que el promedio de dias de cobro sea optimista.
    indices = list(range(len(facturas)))
    rnd.shuffle(indices)
    pagadas = set(indices[:90])
    parciales = set(indices[90:103])

    cobros = []
    puente = []
    idc = 1

    objetivo = list(pagadas) + list(parciales)
    rnd.shuffle(objetivo)

    # Agrupamos facturas del mismo cliente para que algunos cobros salden
    # mas de una.
    por_cliente = {}
    for i in objetivo:
        clave = (facturas[i]["id_cliente"], facturas[i]["fecha_factura"])
        por_cliente.setdefault(clave, []).append(i)

    grupos = []
    for idcli, lista in por_cliente.items():
        while lista:
            n = 1
            if len(lista) >= 5 and rnd.random() < 0.10:
                n = 5
            elif len(lista) >= 2 and rnd.random() < 0.10:
                n = 2
            grupos.append(lista[:n])
            lista = lista[n:]
    rnd.shuffle(grupos)
    grupos = grupos[:N_COBROS]

    for g in grupos:
        g = sorted(g, key=lambda i: facturas[i]["fecha_factura"])
        f0 = facturas[g[-1]]
        fecha_fac = dt.date.fromisoformat(f0["fecha_factura"])

        # Dias hasta el cobro: la mayoria rapido, unos pocos muy lentos.
        # Es lo que separa la mediana (25) del promedio (31).
        dias = int(max(1, min(rnd.lognormvariate(3.09, 0.80), 240)))
        fecha_cob = fecha_fac + dt.timedelta(days=dias)
        if fecha_cob > FECHA_CORTE:
            fecha_cob = FECHA_CORTE
            dias = (fecha_cob - fecha_fac).days

        monto = 0.0
        for i in g:
            f = facturas[i]
            if i in parciales:
                parte = dinero(f["monto_total"] * rnd.uniform(0.2, 0.7))
            else:
                parte = f["monto_total"]
            monto = dinero(monto + parte)

            ffac = dt.date.fromisoformat(f["fecha_factura"])
            d = (fecha_cob - ffac).days
            puente.append({
                "id_cobro": idc,
                "id_factura": f["id_factura"],
                "fecha_cobro": fecha_cob.isoformat(),
                "fecha_factura": f["fecha_factura"],
                "dias_hasta_cobro": d,
                "es_anticipo": 1 if d < 0 else 0,
                # Un cobro anterior a su factura no mide nada: se excluye
                # del promedio en lugar de ensuciarlo.
                "valido_para_promedio": 1 if d >= 0 else 0,
                "factura_migrada": f["es_migrada"],
            })
            f["monto_cobrado"] = dinero(f["monto_cobrado"] + parte)

        metodo = rnd.choice(METODOS)
        if metodo == "Efectivo":
            # El texto del metodo arrastra el nombre de la sociedad que
            # recibe. Es un campo de texto libre, no una clave.
            metodo = "Pago manual (Efectivo %s)" % nombre_ent[f0["id_entidad"]]

        cobros.append({
            "id_cobro": idc,
            "referencia": "COB/%d/%05d" % (fecha_cob.year, idc),
            "fecha_cobro": fecha_cob.isoformat(),
            "monto_cobrado": monto,
            "id_cliente": f0["id_cliente"],
            "id_entidad": f0["id_entidad"],
            "metodo_pago": metodo,
            "estado": elegir([("paid", 0.925), ("in_process", 0.064),
                              ("canceled", 0.011)]),
            "aplicado_a_factura": 1,
            # Dos de cada tres cobros no se han cruzado con el extracto
            # bancario. Sin conciliacion no hay certeza de que el dinero
            # haya entrado.
            "conciliado_con_banco": 1,   # se fija abajo, en bloque
            "facturas_saldadas": len(g),
        })
        idc += 1

    # Unos pocos cobros sin aplicar a ninguna factura: dinero que entro y
    # quedo flotando. No aparecen en el puente, y por eso el total cobrado
    # de la tabla de cobros no cuadra con el de las facturas.
    for _ in range(4):
        f0 = facturas[rnd.randrange(len(facturas))]
        fecha_cob = dt.date.fromisoformat(f0["fecha_factura"]) + \
            dt.timedelta(days=rnd.randint(1, 40))
        if fecha_cob > FECHA_CORTE:
            fecha_cob = FECHA_CORTE
        cobros.append({
            "id_cobro": idc,
            "referencia": "COB/%d/%05d" % (fecha_cob.year, idc),
            "fecha_cobro": fecha_cob.isoformat(),
            "monto_cobrado": dinero(rnd.uniform(3000, 40000)),
            "id_cliente": f0["id_cliente"],
            "id_entidad": f0["id_entidad"],
            "metodo_pago": rnd.choice(METODOS),
            "estado": "paid",
            "aplicado_a_factura": 0,
            "conciliado_con_banco": 0,
            "facturas_saldadas": 0,
        })
        idc += 1

    # Se marca un numero exacto de cobros sin conciliar en lugar de tirar
    # una moneda por fila: con 90 cobros el azar se desvia demasiado.
    aplicados = [c for c in cobros if c["aplicado_a_factura"] == 1]
    n_sin = int(round(len(aplicados) * PCT_SIN_CONCILIAR))
    for c in rnd.sample(aplicados, n_sin):
        c["conciliado_con_banco"] = 0

    return cobros, puente


# =====================================================================
# 8. CIERRE: estado de cada factura y antiguedad
# =====================================================================
def cerrar_facturas(facturas):
    for f in facturas:
        total = f["monto_total"]
        cobrado = min(f["monto_cobrado"], total)
        f["monto_cobrado"] = dinero(cobrado)
        f["saldo_pendiente"] = dinero(total - cobrado)

        if f["saldo_pendiente"] <= 0.01:
            f["estado_cobro"] = "paid"
            f["esta_pagada"] = 1
            f["saldo_pendiente"] = 0.0
        elif cobrado > 0.01:
            f["estado_cobro"] = "partial"
            f["esta_pagada"] = 0
        else:
            f["estado_cobro"] = "not_paid"
            f["esta_pagada"] = 0

        venc = dt.date.fromisoformat(f["fecha_vencimiento"])
        dias = (FECHA_CORTE - venc).days
        f["dias_vencido"] = dias if dias > 0 else 0

        if f["esta_pagada"]:
            tramo = "Cobrada"
        elif dias <= 0:
            tramo = "Por vencer"
        elif dias <= 30:
            tramo = "1-30 días"
        elif dias <= 60:
            tramo = "31-60 días"
        elif dias <= 90:
            tramo = "61-90 días"
        elif dias <= 180:
            tramo = "91-180 días"
        else:
            tramo = "Más de 180 días"
        f["tramo_antiguedad"] = tramo


# =====================================================================
# ESCRITURA
# =====================================================================
def escribir(carpeta, nombre, filas):
    ruta = os.path.join(carpeta, nombre)
    with open(ruta, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    return len(filas)


def main():
    aqui = os.path.dirname(os.path.abspath(__file__))
    destino = os.path.join(aqui, "dataset_ejemplo")
    if not os.path.isdir(destino):
        destino = os.path.join(os.path.dirname(aqui), "dataset_ejemplo")
    os.makedirs(destino, exist_ok=True)

    L = "=" * 68
    print(L)
    print("GENERADOR DEL DATASET DE EJEMPLO")
    print("Datos sinteticos. Semilla %d." % SEMILLA)
    print(L)

    calendario = generar_calendario()
    entidades = generar_entidades()
    responsables = generar_responsables()
    clientes = generar_clientes()
    facturas = generar_facturas(clientes, entidades, responsables)
    lineas = generar_lineas(facturas)
    cobros, puente = generar_cobros(facturas, clientes, entidades)
    cerrar_facturas(facturas)

    print()
    for nombre, filas in [
        ("dim_calendario.csv", calendario),
        ("dim_clientes.csv", clientes),
        ("dim_entidades.csv", entidades),
        ("dim_responsables.csv", responsables),
        ("hechos_facturas.csv", facturas),
        ("hechos_lineas.csv", lineas),
        ("hechos_cobros.csv", cobros),
        ("puente_cobro_factura.csv", puente),
    ]:
        n = escribir(destino, nombre, filas)
        print("  %-28s %5d filas" % (nombre, n))

    # ---- resumen, para que las cifras del README salgan de aqui -------
    ingreso = sum(f["monto_total"] for f in facturas)
    pendiente = sum(f["saldo_pendiente"] for f in facturas)
    pagadas = sum(1 for f in facturas if f["esta_pagada"])
    sin_cobro = sum(1 for f in facturas if f["estado_cobro"] == "not_paid")

    pend_sin_parcial = sum(f["saldo_pendiente"] for f in facturas
                           if f["estado_cobro"] == "not_paid")
    por_cliente = {}
    for f in facturas:
        k = f["id_cliente_matriz"]
        por_cliente[k] = por_cliente.get(k, 0.0) + f["monto_total"]
    top = sorted(por_cliente.values(), reverse=True)

    dcobro = sorted(p["dias_hasta_cobro"] for p in puente
                    if p["valido_para_promedio"] == 1)
    media = sum(dcobro) / len(dcobro)
    mediana = dcobro[len(dcobro) // 2]
    sin_conc = sum(1 for c in cobros if c["conciliado_con_banco"] == 0)

    print()
    print(L)
    print("RESUMEN DEL DATASET GENERADO")
    print(L)
    print("  Ingreso facturado          %15s" % "{:,.2f}".format(ingreso))
    print("  Saldo pendiente            %15s" % "{:,.2f}".format(pendiente))
    print("  Facturas                   %15d" % len(facturas))
    print("  Facturas cobradas          %15d" % pagadas)
    print("  Facturas sin ningun cobro  %15d" % sin_cobro)
    print("  Clientes facturados        %15d" % len(por_cliente))
    print()
    print("  Concentracion Top 5        %14.1f%%"
          % (100 * sum(top[:5]) / ingreso))
    print("  Concentracion Top 10       %14.1f%%"
          % (100 * sum(top[:10]) / ingreso))
    print("  Pendiente sin cobro parcial%14.1f%%"
          % (100 * pend_sin_parcial / pendiente))
    print("  Cobros sin conciliar       %14.1f%%"
          % (100 * sin_conc / len(cobros)))
    print("  Dias de cobro, promedio    %15.1f" % media)
    print("  Dias de cobro, mediana     %15d" % mediana)
    print()
    print("  Carpeta: %s" % destino)
    print(L)


if __name__ == "__main__":
    main()
