# Medidas DAX — Tablero ERP Odoo
Daniel Castillo · Proyecto Grupo Águilas

Cómo crearlas: en la vista de Informe, pestaña Inicio, botón **Nueva medida**.
Pegas el código completo, incluido el nombre y el signo igual, y das Enter.

Créalas en este orden. Las de abajo dependen de las de arriba.

Después de crear cada grupo, verifica contra la columna "Debe dar" al final
de este documento. Si una cifra no coincide, detente y revisa antes de seguir.

---

## GRUPO 1 — Base

Son las cuatro que sostienen todo lo demás.

```
Ingreso = SUM(hechos_facturas[monto_sin_impuesto])
```
El ingreso real, sin ITBIS. El impuesto no es de la empresa.

```
Facturado Total = SUM(hechos_facturas[monto_total])
```
Con impuestos. Se usa para analizar cobranza, porque el cliente paga el total.

```
Facturas = COUNTROWS(hechos_facturas)
```

```
Ticket Promedio = DIVIDE([Ingreso], [Facturas])
```
Usa DIVIDE y no la barra de división. DIVIDE maneja el cero sin error.

---

## GRUPO 2 — Cobranza

```
Pendiente = SUM(hechos_facturas[saldo_pendiente])
```

```
Cobrado = SUM(hechos_facturas[monto_cobrado])
```

```
% Cobranza = DIVIDE([Cobrado], [Facturado Total])
```
Ojo: se compara contra Facturado Total, no contra Ingreso. Mezclar montos
con y sin impuesto es un error frecuente que produce porcentajes imposibles.

```
Facturas Pagadas = CALCULATE([Facturas], hechos_facturas[esta_pagada] = 1)
```

```
Facturas Pendientes = [Facturas] - [Facturas Pagadas]
```

---

## GRUPO 3 — Antigüedad de cartera

Aquí está la corrección más importante del proyecto. La carga migrada de
agosto trae fechas de vencimiento asignadas al cargar, no las originales.
Mezclarlas subestima la mora real.

```
Pendiente Antiguedad Confiable =
CALCULATE([Pendiente], hechos_facturas[antiguedad_confiable] = 1)
```

```
Pendiente Antiguedad Indeterminada =
CALCULATE([Pendiente], hechos_facturas[es_migrada] = 1)
```

```
Mora Verificable =
CALCULATE(
    [Pendiente],
    hechos_facturas[antiguedad_confiable] = 1,
    hechos_facturas[dias_vencido] > 60
)
```
La mora que el sistema permite afirmar con certeza. La real es mayor,
pero requiere las fechas originales del sistema anterior.

```
Mora Mas de 180 =
CALCULATE(
    [Pendiente],
    hechos_facturas[antiguedad_confiable] = 1,
    hechos_facturas[dias_vencido] > 180
)
```

---

## GRUPO 4 — Ciclo de cobro

```
Dias Cobro Promedio =
CALCULATE(
    AVERAGE(puente_cobro_factura[dias_hasta_cobro]),
    puente_cobro_factura[valido_para_promedio] = 1
)
```
Excluye los anticipos, que son pagos registrados antes de la factura y
tienen días negativos. Nueve casos en el dataset.

```
Dias Cobro Mediana =
CALCULATE(
    MEDIAN(puente_cobro_factura[dias_hasta_cobro]),
    puente_cobro_factura[valido_para_promedio] = 1
)
```
La mediana resiste mejor los extremos. Hay un cobro a 282 días que
distorsiona el promedio.

```
Facturas Sin Cobro =
CALCULATE(
    [Facturas],
    FILTER(hechos_facturas, ISEMPTY(RELATEDTABLE(puente_cobro_factura)))
)
```
**Esta es la medida más honesta del tablero.** El promedio de días solo
describe las facturas que llegaron a cobrarse. Esta dice cuántas no.
Sin ella, el ciclo de cobro miente por omisión.

```
Saldo Sin Cobro =
CALCULATE(
    [Pendiente],
    FILTER(hechos_facturas, ISEMPTY(RELATEDTABLE(puente_cobro_factura)))
)
```

---

## GRUPO 5 — Concentración de ingresos

```
Clientes Facturados = DISTINCTCOUNT(hechos_facturas[id_cliente])
```

```
Ingreso Top 10 Clientes =
VAR Top10 = TOPN(10, ALL(dim_clientes[id_cliente]), [Ingreso], DESC)
RETURN CALCULATE([Ingreso], Top10)
```

```
Concentracion Top 10 = DIVIDE([Ingreso Top 10 Clientes], CALCULATE([Ingreso], ALL(dim_clientes)))
```
El denominador lleva ALL para que el porcentaje no cambie al filtrar
por cliente. Sin eso, al seleccionar un cliente daría siempre 100%.

```
Ingreso Top 5 Clientes =
VAR Top5 = TOPN(5, ALL(dim_clientes[id_cliente]), [Ingreso], DESC)
RETURN CALCULATE([Ingreso], Top5)
```

```
Concentracion Top 5 = DIVIDE([Ingreso Top 5 Clientes], CALCULATE([Ingreso], ALL(dim_clientes)))
```

---

## GRUPO 6 — Calidad de datos y adopción

```
Clientes Registrados = COUNTROWS(dim_clientes)
```

```
Clientes Con Correo = SUM(dim_clientes[tiene_correo])
```

```
% Clientes Con Correo = DIVIDE([Clientes Con Correo], [Clientes Registrados])
```

```
Clientes Sin RNC = [Clientes Registrados] - SUM(dim_clientes[tiene_rnc])
```

```
Clientes Sin Facturar = [Clientes Registrados] - [Clientes Facturados]
```

```
Cobros Sin Conciliar =
CALCULATE(
    COUNTROWS(hechos_cobros),
    hechos_cobros[conciliado_con_banco] = 0
)
```

```
% Cobros Sin Conciliar =
DIVIDE([Cobros Sin Conciliar], COUNTROWS(hechos_cobros))
```

---

## GRUPO 7 — Servicios y descuentos

```
Descuento Otorgado = SUM(hechos_lineas[monto_descuento])
```
Mide solo lo registrado como descuento. Los descuentos aplicados bajando
el precio directamente no aparecen aquí y no son medibles.

```
Lineas Facturadas = COUNTROWS(hechos_lineas)
```

```
% Uso Catalogo = DIVIDE(SUM(hechos_lineas[usa_catalogo]), [Lineas Facturadas])
```

---

## VERIFICACIÓN

Crea una tabla visual sin filtros y arrastra estas medidas. Deben dar
exactamente esto, porque son las cifras que salieron del script de Python.

| Medida | Debe dar |
|---|---|
| Ingreso | 3,706,039.24 |
| Facturas | 186 |
| Pendiente | 2,726,260.35 |
| Facturas Pagadas | 90 |
| Facturas Sin Cobro | 91 |
| Dias Cobro Promedio | 31.3 |
| Dias Cobro Mediana | 25 |
| Clientes Registrados | 188 |
| Clientes Facturados | 105 |
| Clientes Con Correo | 7 |
| Clientes Sin RNC | 50 |
| Cobros Sin Conciliar | 63 |
| Concentracion Top 10 | 72.1% |
| Concentracion Top 5 | 53.4% |
| Descuento Otorgado | 5,000.00 |
| Lineas Facturadas | 213 |
| % Uso Catalogo | 90.6% |

Si alguna no coincide, el problema está en el modelo o en los tipos de dato,
no en la medida. Revisa antes de construir visuales encima.

---

## FORMATO

Después de crear cada medida, selecciónala en el panel Datos y en
Herramientas de medidas define el formato:

- Montos: Moneda, 0 decimales, símbolo RD$
- Porcentajes: Porcentaje, 1 decimal
- Conteos: Número entero, separador de miles
- Días: Número decimal, 1 decimal

El formato se define una sola vez en la medida y se respeta en todos
los visuales. Formatear visual por visual es trabajo perdido.

---

## ORGANIZACIÓN

Cuando tengas las 30 medidas, el panel se vuelve difícil de navegar.
Crea una tabla vacía para agruparlas: Inicio, Introducir datos, la dejas
sin columnas y la llamas `_Medidas`. Después arrastras cada medida a esa
tabla desde Herramientas de medidas, campo Tabla de inicio.

El guion bajo al inicio del nombre la deja arriba en el panel.
