"""
04 - Resolución de los campos marcados REVISAR
la firma | Daniel Castillo

Qué hace:
  Toma los DICCIONARIO_*.csv y resuelve las filas que quedaron en REVISAR,
  añadiendo una columna nueva: la FAMILIA a la que pertenece cada campo.

Por qué la familia importa:
  Los campos de un ERP se repiten en patrones. Una vez que reconoces las
  familias, clasificas cualquier sistema nuevo sin conocerlo. Es el atajo
  que convierte 300 campos desconocidos en 6 grupos conocidos.

Estados posibles:
  SI         -> entra al modelo de datos
  NO         -> no entra, con el motivo explicado
  PREGUNTAR  -> no se puede resolver sin hablar con alguien de la empresa.
                No es una falla: es la frontera honesta del análisis.

CORRECCIÓN: este script escribe en FINAL_*.csv para no sobrescribir archivos
previos. Windows no distingue mayúsculas de minúsculas en nombres de archivo.
"""

import csv
import os

CARPETA = "salida"

# ---------------------------------------------------------------
# LAS SEIS FAMILIAS
# ---------------------------------------------------------------
FAMILIAS = {
    "MONTO": "Cifra de dinero. Es el qué del análisis.",
    "TIEMPO": "Fecha o momento. Es el cuándo, y define todo eje temporal.",
    "RELACION": "Apunta a otra tabla. No es una columna del tablero: es un join.",
    "CLASIFICACION": "Agrupa o segmenta. Es el por quién y el de qué tipo.",
    "ESTADO": "Dice en qué punto del proceso está el registro.",
    "TECNICO": "Existe para que el sistema funcione. No es del negocio.",
    "ESPEJO": "Duplica otro campo con otro formato o signo. Redundante.",
}

# ---------------------------------------------------------------
# RESOLUCIÓN DE LOS CAMPOS EN REVISAR
# campo -> (familia, entra, significado, pregunta_o_motivo)
# ---------------------------------------------------------------
R = {

    # ===== FAMILIA ESPEJO: duplicados con signo =====
    "amount_total_signed": ("ESPEJO", "NO",
        "Mismo monto total, con signo negativo en notas de crédito.",
        "Redundante con amount_total. Solo útil si se suman facturas y notas de crédito juntas."),
    "amount_untaxed_signed": ("ESPEJO", "NO",
        "Mismo monto sin impuestos, con signo.",
        "Redundante con amount_untaxed."),
    "amount_tax_signed": ("ESPEJO", "NO",
        "Mismo impuesto, con signo.",
        "Redundante con amount_tax."),
    "amount_residual_signed": ("ESPEJO", "NO",
        "Mismo saldo pendiente, con signo.",
        "Redundante con amount_residual."),
    "amount_total_in_currency_signed": ("ESPEJO", "NO",
        "Total en moneda del documento, con signo.",
        "Redundante. El sistema opera en una sola moneda."),
    "amount_untaxed_in_currency_signed": ("ESPEJO", "NO",
        "Monto sin impuestos en moneda del documento, con signo.",
        "Redundante. Moneda única."),
    "amount_company_currency_signed": ("ESPEJO", "NO",
        "Monto del pago en moneda de la empresa, con signo.",
        "Redundante con amount."),
    "amount_currency": ("ESPEJO", "NO",
        "Monto de la línea en la moneda del documento.",
        "Con moneda única coincide con balance. Documentar y no usar."),
    "amount_residual_currency": ("ESPEJO", "NO",
        "Saldo de la línea en moneda del documento.",
        "Redundante con amount_residual bajo moneda única."),
    "move_name": ("ESPEJO", "NO",
        "Número de la factura, copiado en cada línea.",
        "Redundante: se obtiene por la relación move_id."),
    "invoice_partner_display_name": ("ESPEJO", "NO",
        "Nombre del cliente copiado en la factura.",
        "Redundante con partner_id. Usar siempre el identificador, no el texto."),
    "complete_name": ("ESPEJO", "NO",
        "Nombre del contacto incluyendo su empresa padre.",
        "Redundante con name más parent_id."),
    "phone_sanitized": ("ESPEJO", "NO",
        "Teléfono normalizado a formato internacional.",
        "Versión limpia de phone. Útil para integraciones, no para análisis."),

    # ===== FAMILIA RELACION: son joins, no columnas =====
    "invoice_line_ids": ("RELACION", "NO",
        "Lista de líneas de la factura.",
        "Define la relación factura-líneas. En el modelo es un join, no una medida."),
    "line_ids": ("RELACION", "NO",
        "Lista de apuntes contables del asiento.",
        "Join hacia account.move.line."),
    "journal_line_ids": ("RELACION", "NO",
        "Versión antigua de line_ids.",
        "La etiqueta del propio sistema dice DEPRECATED. Ignorar."),
    "move_id": ("RELACION", "SI",
        "Factura a la que pertenece la línea. Es la llave que une ambas tablas.",
        "Sin este campo no se puede relacionar el detalle con la cabecera."),
    "product_tmpl_id": ("RELACION", "SI",
        "Plantilla del servicio. Agrupa variantes bajo un mismo concepto.",
        "Con 52 valores para 52 productos, cada servicio es único: no hay variantes."),
    "invoice_ids": ("RELACION", "SI",
        "Facturas que este pago salda. ENLACE CRÍTICO.",
        "Poblado al 100%. Habilita calcular los días reales entre factura y cobro."),
    "matched_payment_ids": ("RELACION", "SI",
        "Pagos que saldan esta factura. El otro lado del mismo enlace.",
        "Poblado al 50%: la mitad de las facturas tiene pago conciliado."),
    "payment_id": ("RELACION", "SI",
        "Pago que originó este apunte contable.",
        "Vía alternativa para unir cobro y factura a nivel de línea."),
    "matched_credit_ids": ("RELACION", "NO",
        "Apuntes de crédito conciliados contra esta línea.",
        "Detalle contable de la conciliación. Innecesario para análisis de gestión."),
    "full_reconcile_id": ("RELACION", "NO",
        "Grupo de conciliación completa.",
        "Fontanería contable. Usar el campo 'reconciled' en su lugar."),
    "outstanding_account_id": ("RELACION", "NO",
        "Cuenta transitoria donde queda el pago antes de conciliarse con el banco.",
        "Concepto contable interno."),
    "move_id_payment": ("RELACION", "NO",
        "Asiento contable generado por el pago.",
        "Trazabilidad contable, no analítica."),

    # ===== FAMILIA TIEMPO =====
    "date_maturity": ("TIEMPO", "SI",
        "Fecha de vencimiento del apunte. En cuentas por cobrar marca cuándo debía pagarse.",
        "Poblado al 63%: solo las líneas de cobro lo tienen, lo cual es correcto."),
    "l10n_do_rnc_last_checked": ("TIEMPO", "SI",
        "Última vez que el RNC se verificó contra la DGII.",
        "Al 48%: la verificación existe y se aplica en la mitad de los casos. Preguntar el criterio."),
    "l10n_do_rnc_operation_start": ("TIEMPO", "SI",
        "Fecha de inicio de operaciones del cliente según la DGII.",
        "Permite medir antigüedad del cliente como empresa. Dato externo y confiable."),

    # ===== FAMILIA CLASIFICACION: aquí está el valor =====
    "l10n_do_ncf": ("CLASIFICACION", "SI",
        "Comprobante fiscal emitido. El prefijo define si es crédito fiscal o consumo.",
        "Al 100%, con 131 valores para 185 facturas. VERIFICAR si hay NCF repetidos."),
    "l10n_do_sequence_prefix": ("CLASIFICACION", "SI",
        "Prefijo de la secuencia de comprobantes. Define el tipo fiscal del documento.",
        "Solo 2 prefijos: la segmentación B2B contra B2C es directa."),
    "l10n_do_sequence_id": ("CLASIFICACION", "SI",
        "Tipo de comprobante electrónico configurado.",
        "4 tipos activos. Confirma qué comprobantes emite realmente la firma."),
    "l10n_do_sequence_number": ("CLASIFICACION", "NO",
        "Número correlativo dentro de la secuencia de NCF.",
        "El prefijo aporta el significado; el correlativo solo ordena."),
    "l10n_do_invoice_ncf_type_ids": ("CLASIFICACION", "NO",
        "Tipos de NCF usados para filtrar impuestos.",
        "Configuración interna del módulo fiscal."),
    "l10n_do_dgii_tax_payer_type": ("CLASIFICACION", "SI",
        "Tipo de contribuyente según la DGII.",
        "Al 100% con 2 valores. Clasificación fiscal oficial de cada cliente."),
    "l10n_do_rnc_economic_activity": ("CLASIFICACION", "SI",
        "Actividad económica del cliente según registro en la DGII.",
        "71 actividades distintas. DA LA SEGMENTACION SECTORIAL DE LA CARTERA."),
    "l10n_do_rnc_payment_regimen": ("CLASIFICACION", "SI",
        "Régimen de pago fiscal del cliente.",
        "3 valores. Distingue tipos de contribuyente con obligaciones distintas."),
    "l10n_do_rnc_status": ("ESTADO", "SI",
        "Estado del RNC en la DGII: activo, suspendido u otro.",
        "Un cliente con RNC no activo es un riesgo al emitir crédito fiscal."),
    "l10n_do_rnc_fiscal_name": ("CLASIFICACION", "NO",
        "Razón social registrada en la DGII.",
        "Útil para validar que el nombre en el sistema coincide con el oficial, no para segmentar."),
    "l10n_do_rnc_input": ("CLASIFICACION", "NO",
        "RNC tal como se capturó antes de validarse.",
        "Campo intermedio del proceso de validación. Usar 'vat'."),
    "l10n_do_rnc_warning": ("ESTADO", "NO",
        "Aviso generado cuando la verificación encuentra discrepancias.",
        "Al 28%. Revisarlo como incidencia puntual, no como dimensión de análisis."),
    "invoice_user_id": ("CLASIFICACION", "SI",
        "Persona responsable de la factura.",
        "5 personas. Habilita analizar la cartera por responsable. Dimensión nueva."),
    "invoice_payment_term_id": ("CLASIFICACION", "SI",
        "Condición de pago pactada: contado, 30 días, etc.",
        "3 condiciones, al 75%. Comparar el plazo pactado contra el cumplido."),
    "display_type": ("CLASIFICACION", "SI",
        "Distingue líneas de servicio de líneas de sección, nota o subtotal.",
        "FILTRO OBLIGATORIO. Sin él se suman líneas de texto como si fueran importes."),
    "commercial_company_name": ("CLASIFICACION", "NO",
        "Razón social de la entidad comercial del contacto.",
        "Redundante para análisis: usar commercial_partner_id."),
    "partner_shipping_id": ("CLASIFICACION", "NO",
        "Dirección de entrega de la factura.",
        "En servicios profesionales coincide con el cliente. Sin valor analítico aquí."),
    "product_uom_id": ("CLASIFICACION", "NO",
        "Unidad de medida del servicio.",
        "Solo 2 valores y al 30%. El catálogo de servicios no la usa de forma consistente."),
    "sequence": ("TECNICO", "NO",
        "Orden de presentación de las líneas dentro de la factura.",
        "Afecta cómo se imprime el documento, no lo que significa."),
    "sequence_number": ("TECNICO", "NO",
        "Correlativo interno del documento.",
        "Numeración del sistema, distinta del comprobante fiscal."),
    "sequence_prefix": ("TECNICO", "NO",
        "Prefijo de la numeración interna.",
        "Equivalente interno del prefijo fiscal. Usar el de NCF."),

    # ===== FAMILIA MONTO =====
    "price_total": ("MONTO", "SI",
        "Total de la línea con impuestos incluidos.",
        "Verificar que la suma de líneas cuadre con el total de la factura."),
    "tax_base_amount": ("MONTO", "SI",
        "Base sobre la que se calcula el impuesto.",
        "Solo 8 valores distintos. Explica por qué el ITBIS tiene tan poca variación."),
    "fh_total_credit": ("MONTO", "PREGUNTAR",
        "Campo añadido por una personalización externa al núcleo de Odoo.",
        "El prefijo fh_ no pertenece a Odoo estándar. Preguntar al implementador qué calcula."),
    "fh_total_debit": ("MONTO", "PREGUNTAR",
        "Campo añadido por una personalización externa al núcleo de Odoo.",
        "Mismo caso. No documentarlo por suposición: preguntarlo."),

    # ===== FAMILIA ESTADO =====
    "reconciled": ("ESTADO", "SI",
        "Indica si el apunte ya fue cruzado contra un pago.",
        "Al 38%. Complementa el análisis de cobranza."),
    "is_reconciled": ("ESTADO", "SI",
        "Indica si el pago ya fue aplicado a facturas.",
        "Al 96%: casi todos los pagos están aplicados. Buena señal de orden contable."),
    "is_matched": ("ESTADO", "SI",
        "Indica si el pago fue cruzado contra el extracto bancario.",
        "Solo al 33%. Dos tercios de los pagos no están conciliados con el banco. HALLAZGO."),
    "matching_number": ("TECNICO", "NO",
        "Identificador del grupo de conciliación.",
        "Etiqueta interna del proceso contable."),

    # ===== FAMILIA TECNICO =====
    "audit_trail_message_ids": ("TECNICO", "NO",
        "Registro automático de cambios del documento.",
        "Lo genera el sistema. Sirve para auditoría, no para análisis."),
    "memo": ("TECNICO", "NO",
        "Nota libre escrita en el pago.",
        "Texto sin estructura. Revisable a mano, no modelable."),
    "payment_reference": ("TECNICO", "NO",
        "Referencia de pago impresa en la factura.",
        "Normalmente repite el número del documento."),
    "property_stock_customer": ("TECNICO", "NO",
        "Ubicación de inventario asociada al cliente.",
        "Pertenece al módulo de almacén. Irrelevante en una firma de servicios."),
    "property_stock_supplier": ("TECNICO", "NO",
        "Ubicación de inventario asociada al proveedor.",
        "Mismo caso."),
    "partner_share": ("TECNICO", "NO",
        "Marca si el contacto puede acceder al portal externo.",
        "Configuración de accesos."),
    "tz": ("TECNICO", "NO",
        "Zona horaria del contacto.",
        "Todos operan en el mismo país."),
    "phone": ("CLASIFICACION", "SI",
        "Teléfono del cliente.",
        "Al 58%. Contrastar con el 4% que tiene correo: hay canal de contacto, pero no digital."),
}


def familia_por_tipo(tipo):
    """Clasificación de respaldo cuando el campo no está en el diccionario."""
    return {
        "monetary": "MONTO", "float": "MONTO", "integer": "MONTO",
        "date": "TIEMPO", "datetime": "TIEMPO",
        "many2one": "RELACION", "one2many": "RELACION", "many2many": "RELACION",
        "selection": "ESTADO", "boolean": "ESTADO",
        "char": "CLASIFICACION", "text": "CLASIFICACION",
    }.get(tipo, "TECNICO")


def procesar(modelo):
    origen = os.path.join(CARPETA, f"diccionario_{modelo}.csv")
    if not os.path.exists(origen):
        print(f"  No encontrado: {origen}")
        return None

    with open(origen, encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))

    resueltos = pendientes = 0

    for fila in filas:
        campo = fila["campo_tecnico"]

        if fila.get("entra_al_modelo") == "REVISAR":
            if campo in R:
                fam, entra, sig, nota = R[campo]
                fila["familia"] = fam
                fila["significado_negocio"] = sig
                fila["entra_al_modelo"] = entra
                if entra == "SI":
                    fila["riesgo_calidad"] = nota
                else:
                    fila["riesgo_calidad"] = nota
                resueltos += 1
            else:
                fila["familia"] = familia_por_tipo(fila.get("tipo", ""))
                fila["entra_al_modelo"] = "PREGUNTAR"
                fila["riesgo_calidad"] = "Sin significado conocido. Consultar con la empresa."
                pendientes += 1
        else:
            fila["familia"] = (R[campo][0] if campo in R
                               else familia_por_tipo(fila.get("tipo", "")))

    campos = ["campo_tecnico", "etiqueta", "tipo", "familia", "pct_poblado",
              "valores_distintos", "significado_negocio",
              "pregunta_que_responde", "riesgo_calidad", "entra_al_modelo"]

    destino = os.path.join(CARPETA, f"FINAL_{modelo}.csv")
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)

    si = sum(1 for f in filas if f["entra_al_modelo"] == "SI")
    preg = sum(1 for f in filas if f["entra_al_modelo"] == "PREGUNTAR")

    print(f"  Resueltos: {resueltos}  |  Entran al modelo: {si}  "
          f"|  A preguntar: {preg}")
    print(f"  -> {destino}")

    return {"modelo": modelo, "si": si, "preguntar": preg, "total": len(filas)}


if __name__ == "__main__":
    modelos = ["account_move", "account_move_line", "res_partner",
               "account_payment", "product_product"]

    print("=" * 66)
    print("RESOLUCIÓN DE CAMPOS PENDIENTES")
    print("=" * 66)

    res = []
    for m in modelos:
        print(f"\n{m}")
        r = procesar(m)
        if r:
            res.append(r)

    print("\n" + "=" * 66)
    print("MODELO DE DATOS DEFINITIVO")
    print("=" * 66)
    for r in res:
        print(f"  {r['modelo']:<22} {r['si']:>3} campos")
    print(f"\n  TOTAL: {sum(r['si'] for r in res)} campos entran al modelo")
    print(f"  A preguntar en la empresa: {sum(r['preguntar'] for r in res)}")

    print("""
  LAS SEIS FAMILIAS — memorízalas y clasificas cualquier ERP

    MONTO          cifras de dinero. El qué.
    TIEMPO         fechas. El cuándo. Definen todo eje temporal.
    RELACION       apuntan a otra tabla. Son joins, no columnas.
    CLASIFICACION  agrupan y segmentan. El quién y el de qué tipo.
    ESTADO         en qué punto del proceso está el registro.
    TECNICO        existen para que el sistema funcione. Fuera.

    Séptima categoría, la que más engaña:
    ESPEJO         duplican otro campo con distinto formato o signo.
                   Parecen útiles porque están 100% poblados. No lo son.
""")
