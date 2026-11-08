# Correcciones de Flujo de Caja

La causa raíz de los saldos omitidos era el cierre incorrecto de CxP. Se corrigió allí y se adaptaron lecturas para pagos individuales.

`cash_flow_repo` usa `purchase_payment_events` y `expense_payment_events`. Cada abono tiene su propia fecha y cuenta; los encabezados acumulados no se vuelven a sumar. Se proyecta la diferencia obligación menos acumulado en la fecha de vencimiento. Una conciliación enlaza el evento y deja fuera la cartola duplicada.

Contrato comprobado: obligación11900, pago2000 → real2000 y pendiente9900; con abono acumulado5900 → pendiente6000. Un pago futuro no se agrega al efectivo del mes anterior. Las transferencias internas afectan cuentas, pero son neutras en el consolidado. Los indicadores de efectivo pagado no incluyen compromisos.

La precedencia regla recurrente/ocurrencia de un período se conserva: la ocurrencia materializada sustituye la proyección. Los reportes mensuales/semanales de pagos leen los eventos y el reporte de CxP reconoce abonos de gastos aunque aún no estén pagados totalmente. El maestro recurrente no cambia por los importes reales de dos meses.

Pruebas: diez escenarios test_repairs_flow, originales flujo_caja/cxp/gastos, cinco ciclos E2E y controles de interfaz/exportación. Los fallos derivados iniciales no se contabilizan como otra causa raíz.
