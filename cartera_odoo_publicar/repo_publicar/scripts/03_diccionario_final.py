"""
03 - Diccionario de datos final
la firma | Daniel Castillo

Qué hace:
  Lee los archivos trabajo_*.csv generados por los scripts 02 y 02b,
  aplica el filtro de tres pasadas (técnico / vacío / constante) y produce
  el diccionario de datos definitivo con la columna de significado de negocio.

  Genera además el registro de campos descartados, que es evidencia del
  nivel de adopción del ERP.

No se conecta a Odoo. Trabaja sobre los CSV que ya tienes.

IMPORTANTE: los significados de negocio de este archivo son un borrador
técnico. Revísalos y ajústalos a cómo opera realmente la firma antes de
entregar el documento. Esa validación es tu aporte profesional.
"""

import csv
import os

ENTRADA = "salida"
SALIDA = "salida"

# ---------------------------------------------------------------
# DICCIONARIO DE NEGOCIO
# Formato: campo -> (significado, pregunta que responde, riesgo de calidad)
# ---------------------------------------------------------------

NEGOCIO = {

    # ---------- account.move : FACTURAS ----------
    "name": ("Número del documento. En facturas de cliente es el correlativo interno del sistema.",
             "¿Cómo identifico una factura de forma única?",
             "No confundir con el NCF: el correlativo interno no es el comprobante fiscal."),
    "invoice_date": ("Fecha de emisión de la factura. Es el eje temporal de todo el análisis de ingresos.",
                     "¿Cuánto se facturó en cada mes, trimestre o año?",
                     "Solo 29 fechas distintas en 185 facturas: la facturación es por tandas, no continua."),
    "invoice_date_due": ("Fecha en que vence el pago. Junto con la fecha de emisión revela el plazo de crédito otorgado.",
                         "¿Qué plazo de crédito damos y a quién?",
                         "Indica cuándo DEBÍA pagarse, no cuándo se pagó. El cobro real está en account.payment."),
    "date": ("Fecha contable del asiento. Puede diferir de la fecha de factura por cierres de período.",
             "¿En qué período contable se reconoció el ingreso?",
             "Si difiere de invoice_date, definir cuál usar y documentar la decisión."),
    "amount_untaxed": ("Monto facturado sin impuestos. Es el ingreso real de la empresa.",
                       "¿Cuál es el ingreso genuino, excluyendo el ITBIS que se le retiene a la DGII?",
                       "Es el campo correcto para medir ingresos. Usar amount_total infla la cifra."),
    "amount_tax": ("ITBIS y demás impuestos de la factura. No es ingreso: es dinero de la DGII en tránsito.",
                   "¿Cuánto impuesto se está trasladando?",
                   "Solo 9 valores distintos en 185 facturas. Verificar exenciones y correcta aplicación."),
    "amount_total": ("Monto total facturado, impuestos incluidos. Es lo que el cliente debe pagar.",
                     "¿Cuál es el valor total de la factura emitida?",
                     "Solo 60 montos distintos: indica tarifas recurrentes estándar, no trabajos a medida."),
    "amount_residual": ("Saldo pendiente de cobro. Si está en cero, la factura ya fue pagada.",
                        "¿Cuánto dinero está pendiente de cobrar y de quién?",
                        "No es el monto facturado. Confundirlos invalida todo el análisis de ingresos."),
    "partner_id": ("Cliente al que se emite la factura.",
                   "¿Quién genera el ingreso y qué tan concentrado está?",
                   "Verificar duplicados: hay 188 clientes registrados para 185 facturas."),
    "company_id": ("Entidad emisora. Crítico: el sistema administra 8 entidades distintas.",
                   "¿Cuánto factura cada entidad de la cartera administrada?",
                   "Omitir este campo mezcla la facturación de empresas que no tienen relación entre sí."),
    "currency_id": ("Moneda de la factura.",
                    "¿Estoy sumando valores comparables?",
                    "Un solo valor distinto en el sistema: moneda única. Riesgo bajo, pero dejarlo documentado."),
    "state": ("Estado del documento: borrador, publicado o cancelado.",
              "¿Qué facturas son válidas para el análisis?",
              "Los borradores deben excluirse siempre. Actualmente hay cero, pero eso puede cambiar."),
    "payment_state": ("Estado de cobro: pagada, parcialmente pagada o pendiente.",
                      "¿Qué proporción de lo facturado ya se cobró?",
                      "Es un estado calculado; contrastarlo con amount_residual para verificar coherencia."),
    "move_type": ("Tipo de documento: factura de cliente, nota de crédito, factura de proveedor.",
                  "¿Estoy analizando ingresos o mezclando con notas de crédito y compras?",
                  "Filtrar por out_invoice. Las notas de crédito restan y deben tratarse aparte."),
    "journal_id": ("Diario contable donde se registra el documento.",
                   "¿Por qué canal o tipo de operación entra cada registro?",
                   "Útil para separar operaciones distintas dentro de una misma entidad."),
    "invoice_origin": ("Documento de origen: pedido, contrato o referencia previa.",
                       "¿De dónde nace esta factura?",
                       "Suele estar vacío si no se usa el módulo de ventas."),
    "ref": ("Referencia libre del documento.",
            "¿Hay información del negocio escrita a mano en este campo?",
            "Campo de texto libre: propenso a formatos inconsistentes."),

    # ---------- NCF / localización dominicana ----------
    "l10n_latam_document_number": ("Número de comprobante fiscal (NCF). El prefijo define el tipo.",
                                   "¿Qué proporción del ingreso es B2B (B01) contra consumo final (B02)?",
                                   "Verificar que ninguna factura publicada esté sin NCF asignado."),
    "l10n_latam_document_type_id": ("Tipo de comprobante fiscal según la clasificación de la DGII.",
                                    "¿Qué mezcla de tipos de comprobante emite cada entidad?",
                                    "Es la vía formal de segmentar B2B/B2C sin depender del texto del NCF."),
    "l10n_do_ncf_expiration_date": ("Fecha de vencimiento de la secuencia de comprobantes autorizada.",
                                    "¿Hay secuencias de NCF próximas a vencer?",
                                    "Si vence sin renovar, la entidad no puede facturar. Riesgo operativo real."),
    "l10n_do_itbis_amount": ("Monto de ITBIS de la línea, según la localización dominicana.",
                             "¿Cómo se distribuye el impuesto por servicio?",
                             "Un solo valor distinto en 500 líneas: revisar si el campo está en uso real."),

    # ---------- account.move.line : LÍNEAS ----------
    "product_id": ("Servicio o producto facturado en la línea.",
                   "¿Qué servicios generan el ingreso?",
                   "El catálogo está poco estructurado: 52 servicios con categorización mínima."),
    "quantity": ("Cantidad facturada de la línea.",
                 "¿Se factura por volumen o por concepto fijo?",
                 "En servicios suele ser 1: verificar si aporta información."),
    "price_unit": ("Precio unitario antes de impuestos y descuentos.",
                   "¿Cuál es la tarifa aplicada por servicio?",
                   "Comparar contra el precio de lista para detectar tarifas fuera de política."),
    "price_subtotal": ("Subtotal de la línea sin impuestos.",
                       "¿Cuánto aporta cada servicio al ingreso?",
                       "Es la base para el análisis de mezcla de servicios."),
    "debit": ("Movimiento al debe del asiento contable.",
              "¿Cómo se compone contablemente la operación?",
              "Es información contable, no comercial. Usar con criterio en tableros de negocio."),
    "credit": ("Movimiento al haber del asiento contable.",
               "¿Cómo se compone contablemente la operación?",
               "Igual que debit: contable, no comercial."),
    "balance": ("Diferencia entre debe y haber de la línea.",
                "¿Está cuadrado el asiento?",
                "Útil para validación contable, poco útil para análisis comercial."),
    "discount": ("Descuento porcentual aplicado a la línea.",
                 "¿Se otorgan descuentos y a quién?",
                 "Un solo valor distinto: o no se dan descuentos, o se dan fuera del sistema. Preguntar."),
    "account_id": ("Cuenta contable afectada.",
                   "¿Bajo qué cuenta se clasifica el ingreso?",
                   "Permite agrupar por naturaleza del ingreso si el catálogo contable está bien armado."),
    "tax_ids": ("Impuestos aplicados a la línea.",
                "¿Qué servicios están gravados y cuáles exentos?",
                "Clave para explicar por qué el ITBIS tiene tan pocos valores distintos."),

    # ---------- account.payment : PAGOS ----------
    "amount": ("Monto del pago recibido.",
               "¿Cuánto dinero entró efectivamente?",
               "Un pago puede cubrir varias facturas: no asumir correspondencia uno a uno."),
    "payment_type": ("Dirección del movimiento: cobro o pago a proveedor.",
                     "¿Es dinero que entra o que sale?",
                     "Filtrar por inbound para análisis de cobros."),
    "partner_type": ("Indica si la contraparte es cliente o proveedor.",
                     "¿Estoy analizando cobros o pagos?",
                     "Un solo valor distinto: toda la muestra es del mismo tipo."),
    "payment_method_line_id": ("Método de pago utilizado: efectivo, transferencia, cheque.",
                               "¿Cómo prefieren pagar los clientes?",
                               "5 métodos distintos en uso. Dato aprovechable para el tablero."),
    "destination_account_id": ("Cuenta de destino del dinero cobrado.",
                               "¿A qué cuenta entra el efectivo?",
                               "3 valores distintos, coincide con las 3 entidades activas."),
    "reconciled_invoice_ids": ("Facturas que este pago salda. ES EL ENLACE CRÍTICO.",
                               "¿Cuántos días reales pasan entre facturar y cobrar?",
                               "Si está poblado, habilita el indicador de ciclo de cobro. VERIFICAR PRIMERO."),

    # ---------- res.partner : CLIENTES ----------
    "vat": ("RNC o cédula del cliente. Identificación fiscal.",
            "¿Puedo emitir comprobante de crédito fiscal a este cliente?",
            "50 de 188 clientes sin RNC. Sin RNC no se puede emitir B01, solo B02."),
    "email": ("Correo electrónico del cliente.",
              "¿Puedo entregar comprobantes fiscales electrónicos de forma automática?",
              "181 de 188 sin correo (96%). Riesgo operativo frente a la facturación electrónica."),
    "is_company": ("Distingue empresa de persona física.",
                   "¿Qué proporción de la cartera es B2B contra B2C?",
                   "95 empresas y 93 personas: la cartera está partida casi a la mitad."),
    "customer_rank": ("Indicador de que el contacto es cliente.",
                      "¿Cuántos contactos son realmente clientes y no prospectos?",
                      "188 clientes registrados pero solo 67 con pagos: revisar inactivos y duplicados."),
    "supplier_rank": ("Indicador de que el contacto es proveedor.",
                      "¿Hay contactos que son cliente y proveedor a la vez?",
                      "Los casos duales requieren tratamiento aparte en el modelo."),
    "commercial_partner_id": ("Entidad comercial matriz del contacto. Agrupa sucursales bajo un mismo cliente.",
                              "¿Cuál es la concentración real de ingresos por grupo económico?",
                              "Analizar por partner_id en vez de este campo puede ocultar concentración."),
    "parent_id": ("Contacto padre, cuando el registro es una sucursal o un contacto de empresa.",
                  "¿Estoy contando una empresa varias veces?",
                  "Fuente frecuente de duplicados aparentes en el conteo de clientes."),
    "country_id": ("País del cliente.",
                   "¿Hay clientes en el exterior con tratamiento fiscal distinto?",
                   "Relevante para exenciones de ITBIS en exportación de servicios."),
    "property_payment_term_id": ("Condición de pago pactada con el cliente.",
                                 "¿Qué plazo formal se acordó, más allá del que se aplica en la práctica?",
                                 "Comparar contra el plazo real revela incumplimientos de política."),
    "active": ("Indica si el registro está activo o archivado.",
               "¿Cuántos clientes están vigentes?",
               "Los archivados no aparecen en búsquedas por defecto y pueden distorsionar conteos."),

    # ---------- product.product : SERVICIOS ----------
    "default_code": ("Código interno del servicio.",
                     "¿El catálogo de servicios está codificado y ordenado?",
                     "Solo 36.5% poblado: dos tercios de los servicios no tienen código."),
    "list_price": ("Precio de lista del servicio.",
                   "¿Cuál es la tarifa oficial contra la efectivamente cobrada?",
                   "Si está en cero, el precio se define por factura y no hay política de tarifas."),
    "standard_price": ("Costo del servicio.",
                       "¿Cuál es el margen por servicio?",
                       "En servicios profesionales rara vez refleja costo real sin registro de horas."),
    "categ_id": ("Categoría del servicio.",
                 "¿Cómo se distribuye el ingreso por línea de servicio?",
                 "Sin categorización útil, el análisis por línea de servicio no es viable."),
    "type": ("Tipo de producto: servicio, almacenable o consumible.",
             "¿La firma vende servicios, bienes o ambos?",
             "Confirmar que el catálogo esté marcado como servicio."),
}


# Campos que se descartan aunque estén poblados: son ruido de Odoo
RUIDO_CONOCIDO = {
    "color", "partner_latitude", "partner_longitude", "suggest_days",
    "suggest_percent", "reminder_date_before_receipt", "calendar_last_notif_ack",
    "is_favorite", "volume", "weight", "credit_limit",
}


def clasificar(fila):
    """
    Filtro de tres pasadas. Devuelve (entra, motivo).
    """
    campo = fila["campo_tecnico"]
    try:
        pct = float(fila["pct_poblado"])
    except (ValueError, KeyError):
        pct = 0.0
    try:
        distintos = int(fila["valores_distintos"])
    except (ValueError, KeyError, TypeError):
        distintos = 0

    if pct == 0:
        return "NO", "Siempre vacío: campo disponible y sin uso"
    if distintos <= 1:
        return "NO", "Constante: un solo valor, no permite segmentar"
    if campo in RUIDO_CONOCIDO:
        return "NO", "Valor por defecto de Odoo, sin significado de negocio"
    if campo in NEGOCIO:
        return "SI", "Responde una pregunta de negocio"
    if pct < 20:
        return "NO", f"Poblado solo {pct}%: insuficiente para construir indicador"
    return "REVISAR", "Poblado y variable, pero sin significado documentado"


def procesar(nombre_archivo):
    ruta = os.path.join(ENTRADA, nombre_archivo)
    if not os.path.exists(ruta):
        print(f"  No encontrado: {ruta}")
        return None

    with open(ruta, encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))

    incluidos, descartados, revisar = [], [], []

    for fila in filas:
        entra, motivo = clasificar(fila)
        campo = fila["campo_tecnico"]

        if entra == "SI":
            sig, preg, riesgo = NEGOCIO[campo]
            fila["significado_negocio"] = sig
            fila["pregunta_que_responde"] = preg
            fila["riesgo_calidad"] = riesgo
            fila["entra_al_modelo"] = "SI"
            incluidos.append(fila)
        elif entra == "REVISAR":
            fila["significado_negocio"] = ""
            fila["pregunta_que_responde"] = ""
            fila["riesgo_calidad"] = ""
            fila["entra_al_modelo"] = "REVISAR"
            revisar.append(fila)
        else:
            fila["significado_negocio"] = ""
            fila["pregunta_que_responde"] = ""
            fila["riesgo_calidad"] = motivo
            fila["entra_al_modelo"] = "NO"
            descartados.append(fila)

    base = nombre_archivo.replace("trabajo_", "").replace(".csv", "")

    # Diccionario final: lo que entra al modelo, más lo pendiente de revisar
    final = incluidos + revisar
    if final:
        salida = os.path.join(SALIDA, f"DICCIONARIO_{base}.csv")
        campos = ["campo_tecnico", "etiqueta", "tipo", "pct_poblado",
                  "valores_distintos", "significado_negocio",
                  "pregunta_que_responde", "riesgo_calidad", "entra_al_modelo"]
        with open(salida, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            w.writerows(final)

    # Registro de descartes: es evidencia de adopción del ERP
    if descartados:
        salida_d = os.path.join(SALIDA, f"DESCARTADOS_{base}.csv")
        campos_d = ["campo_tecnico", "etiqueta", "tipo", "pct_poblado",
                    "valores_distintos", "riesgo_calidad"]
        with open(salida_d, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=campos_d, extrasaction="ignore")
            w.writeheader()
            w.writerows(descartados)

    return {
        "modelo": base,
        "total": len(filas),
        "incluidos": len(incluidos),
        "revisar": len(revisar),
        "descartados": len(descartados),
        "vacios": sum(1 for f in descartados
                      if "vacío" in f.get("riesgo_calidad", "")),
        "constantes": sum(1 for f in descartados
                          if "Constante" in f.get("riesgo_calidad", "")),
    }


if __name__ == "__main__":
    archivos = [
        "trabajo_account_move.csv",
        "trabajo_account_move_line.csv",
        "trabajo_res_partner.csv",
        "trabajo_account_payment.csv",
        "trabajo_product_product.csv",
    ]

    print("=" * 66)
    print("CONSTRUCCIÓN DEL DICCIONARIO DE DATOS")
    print("=" * 66)

    resumen = []
    for a in archivos:
        print(f"\n{a}")
        r = procesar(a)
        if r:
            print(f"  Campos analizados:   {r['total']}")
            print(f"  Entran al modelo:    {r['incluidos']}")
            print(f"  Pendientes revisar:  {r['revisar']}")
            print(f"  Descartados:         {r['descartados']}"
                  f"  (vacíos: {r['vacios']}, constantes: {r['constantes']})")
            resumen.append(r)

    print("\n" + "=" * 66)
    print("RESUMEN GLOBAL")
    print("=" * 66)
    tot = sum(r["total"] for r in resumen)
    inc = sum(r["incluidos"] for r in resumen)
    rev = sum(r["revisar"] for r in resumen)
    vac = sum(r["vacios"] for r in resumen)
    con = sum(r["constantes"] for r in resumen)

    print(f"  Campos evaluados:              {tot}")
    print(f"  Campos que entran al modelo:   {inc}")
    print(f"  Pendientes de tu revisión:     {rev}")
    print(f"  Vacíos (disponibles sin uso):  {vac}")
    print(f"  Constantes (sin variación):    {con}")
    if tot:
        print(f"\n  Aprovechamiento del ERP: {round(100*inc/tot, 1)}% "
              f"de los campos disponibles contiene información útil.")

    print("""
  ARCHIVOS GENERADOS
    DICCIONARIO_*.csv  -> tu entregable. Revisa cada significado y ajústalo
                          a como opera la firma. Las filas marcadas REVISAR
                          las completas tú.
    DESCARTADOS_*.csv  -> no es basura. Es la evidencia de qué partes del
                          sistema no se están usando. Sustenta el indicador
                          de adopción del ERP.
""")
