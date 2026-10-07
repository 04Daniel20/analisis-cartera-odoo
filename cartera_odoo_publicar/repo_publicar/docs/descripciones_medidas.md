# Descripciones de las medidas
Daniel Castillo · Proyecto ERP Odoo

Dónde se ponen: vista de Modelo, seleccionas la medida, panel Propiedades,
campo **Descripción**. La carpeta va en **Carpetas de visualización**.

Cuando alguien pase el cursor sobre la medida en el panel Datos, va a leer
ese texto. Es documentación que vive dentro del modelo.

---

## Cómo escribir una buena descripción

Tres reglas que sigo en todas las de abajo.

**No repitas el nombre.** "Ingreso: suma el ingreso" no aporta nada.
Di qué incluye, qué excluye y para qué sirve.

**Declara las exclusiones.** Si una medida filtra algo, dilo. Es la
información que evita que alguien la use mal.

**Avisa de las trampas.** Si hay una medida parecida que podría
confundirse, o un supuesto que puede romperse, esa advertencia vale
más que la definición.

---

## 01 Base

**Ingreso** · Moneda, 0 decimales
> Monto facturado sin ITBIS. Es el ingreso real de la firma: el impuesto se traslada a la DGII y no le pertenece. Usar esta medida, no Facturado Total, para cualquier análisis de ingresos.

**Facturado Total** · Moneda, 0 decimales
> Monto facturado con impuestos incluidos. Es lo que el cliente debe pagar. Se usa como denominador en los indicadores de cobranza, nunca como medida de ingreso.

**Facturas** · Número entero
> Cantidad de facturas de cliente emitidas y publicadas. Excluye borradores y notas de crédito.

**Ticket Promedio** · Moneda, 0 decimales
> Ingreso medio por factura. Con tarifas recurrentes el valor es estable; una variación brusca indica cambio en la mezcla de servicios o en la política de precios.

---

## 02 Cobranza

**Pendiente** · Moneda, 0 decimales
> Saldo por cobrar sobre el total facturado. Incluye registros migrados, cuya antigüedad no es confiable. Para análisis de mora, usar las medidas del grupo Antigüedad.

**Cobrado** · Moneda, 0 decimales
> Monto efectivamente cobrado, calculado como facturado total menos saldo pendiente.

**% Cobranza** · Porcentaje, 1 decimal
> Proporción cobrada del total facturado. Numerador y denominador incluyen impuestos: mezclar montos con y sin ITBIS produce porcentajes imposibles.

**Facturas Pagadas** · Número entero
> Facturas con saldo pendiente en cero.

**Facturas Pendientes** · Número entero
> Facturas con saldo por cobrar, total o parcial.

---

## 03 Antigüedad de cartera

**Pendiente Antiguedad Confiable** · Moneda, 0 decimales
> Saldo por cobrar de facturas creadas directamente en el sistema, cuya fecha de vencimiento es la real. Es la única base válida para medir mora.

**Pendiente Antiguedad Indeterminada** · Moneda, 0 decimales
> Saldo de las facturas cargadas masivamente en agosto de 2026 desde el sistema anterior. Su vencimiento se asignó al momento de la carga, no es el original. No usar en reportes de antigüedad.

**Mora Verificable** · Moneda, 0 decimales
> Saldo vencido a más de 60 días, solo sobre registros con fecha confiable. La mora real de la firma es mayor: determinarla requiere recuperar las fechas originales del sistema anterior.

**Mora Mas de 180** · Moneda, 0 decimales
> Saldo vencido a más de 180 días sobre registros confiables. Es la porción de cartera con menor probabilidad de recuperación.

---

## 04 Ciclo de cobro

**Dias Cobro Promedio** · Número decimal, 1 decimal
> Días transcurridos entre emisión y cobro. Excluye los anticipos, que son pagos registrados antes de la factura y tienen días negativos. Describe únicamente las facturas que llegaron a cobrarse.

**Dias Cobro Mediana** · Número decimal, 1 decimal
> Mediana de días hasta el cobro. Más representativa que el promedio cuando hay cobros extremos que lo distorsionan.

**Facturas Sin Cobro** · Número entero
> Facturas sin ningún cobro asociado. Es el complemento obligatorio del promedio de días, que las ignora por construcción. Mostrar siempre ambas juntas.

**Saldo Sin Cobro** · Moneda, 0 decimales
> Saldo acumulado de las facturas que nunca recibieron un pago.

---

## 05 Concentración de ingresos

**Clientes Facturados** · Número entero
> Clientes distintos con al menos una factura emitida en el período.

**Ingreso Top 10 Clientes** · Moneda, 0 decimales
> Ingreso acumulado de los diez clientes de mayor facturación.

**Concentracion Top 10** · Porcentaje, 1 decimal
> Participación de los diez mayores clientes en el ingreso total. El denominador ignora el filtro de cliente para que el porcentaje siga siendo comparable al segmentar.

**Ingreso Top 5 Clientes** · Moneda, 0 decimales
> Ingreso acumulado de los cinco clientes de mayor facturación.

**Concentracion Top 5** · Porcentaje, 1 decimal
> Participación de los cinco mayores clientes en el ingreso total. Un valor alto indica dependencia y riesgo ante la pérdida de un solo cliente.

---

## 06 Calidad de datos y adopción

**Clientes Registrados** · Número entero
> Contactos marcados como cliente en el ERP. Incluye inactivos y posibles duplicados: no equivale a clientes activos.

**Clientes Con Correo** · Número entero
> Clientes con dirección de correo registrada.

**% Clientes Con Correo** · Porcentaje, 1 decimal
> Proporción de la cartera con correo registrado. Condiciona la entrega automática de comprobantes fiscales electrónicos.

**Clientes Sin RNC** · Número entero
> Clientes sin identificación fiscal registrada. Sin RNC solo puede emitirse comprobante de consumo final, no de crédito fiscal.

**Clientes Sin Facturar** · Número entero
> Clientes registrados que nunca han recibido una factura. Señal de cartera inflada: prospectos, inactivos o duplicados.

**Cobros Sin Conciliar** · Número entero
> Cobros registrados que no han sido cruzados contra el extracto bancario. Sin conciliación no hay certeza de que el dinero haya ingresado.

**% Cobros Sin Conciliar** · Porcentaje, 1 decimal
> Proporción de cobros pendientes de conciliación bancaria. Es un indicador de control interno, no de cobranza.

---

## 07 Servicios y descuentos

**Descuento Otorgado** · Moneda, 0 decimales
> Descuento registrado en el campo correspondiente de la línea. No captura los descuentos aplicados bajando el precio directamente, que el sistema no distingue de una tarifa menor.

**Lineas Facturadas** · Número entero
> Líneas de servicio facturadas. Excluye apuntes de impuesto y de cuenta por cobrar, que no son líneas de producto.

**% Uso Catalogo** · Porcentaje, 1 decimal
> Proporción de líneas que referencian un servicio del catálogo. El resto se captura como texto libre y no es analizable por tipo de servicio.

---

## Por qué esto importa más de lo que parece

Una medida sin descripción obliga a abrir el código DAX para entenderla.
Dos años después, o cuando otra persona herede el modelo, ese código no
explica las decisiones: explica el cálculo.

La diferencia está en medidas como **Dias Cobro Promedio**. El DAX muestra
que filtra por `valido_para_promedio = 1`. Lo que no muestra es *por qué*:
porque hay anticipos con días negativos que bajarían el promedio sin que
nadie lo note.

Esa es la información que se pierde, y es la que hace que alguien use la
medida mal seis meses después.

Por eso las descripciones no describen el cálculo. Describen el criterio.
