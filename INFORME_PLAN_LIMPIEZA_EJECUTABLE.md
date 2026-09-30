# Plan de limpieza de `facturacion` — simulación READ ONLY

**Fecha UTC:** 2026-09-27T21:12:16+00:00
**Base verificada:** `facturacion`; transacción read-only `on`; timezone PostgreSQL `UTC`.
**No se ejecutaron INSERT, UPDATE, DELETE, TRUNCATE ni DDL.**

## ROOT SET

- Ventas: 19 (no cotizaciones), escogidas por `created_at` parseado DESC, `id` DESC.
- Cotizaciones: 0, escogidas por `created_at` parseado DESC, `id` DESC.
- OC raíz: 30; OT raíz: 2; deudas raíz: 10.
- Clientes: todos los 10 existentes (máximo 10).
- Cuentas raíz: 11; mínimo observado requerido por pagos/deudas/facturas protegidos: 11 (por encima del objetivo 10).

## Cronología normalizada

El parser usa `datetime.fromisoformat`, interpreta los valores naive en la zona PostgreSQL de la sesión, normaliza a UTC y nunca ordena TEXT lexicográficamente.
| Fuente | Filas | Parseables | NULL/vacíos | No parseables | Formatos encontrados | Muestras no parseables |
|---|---:|---:|---:|---|---|---|
| `sales.created_at` | 19 | 19 | 0 | 0 | ISO-T-naive: 17, ISO-T-with-offset: 2 | Ninguno. |
| `quotes.created_at` | 0 | 0 | 0 | 0 | — | Ninguno. |
| `purchase_orders.created_at` | 1047 | 1047 | 0 | 0 | ISO-T-naive: 16, ISO-T-with-offset: 987, space-naive: 44 | Ninguno. |
| `production_orders.created_at` | 2 | 2 | 0 | 0 | space-naive: 2 | Ninguno. |
| `debts.created_at` | 44 | 44 | 0 | 0 | space-with-offset: 44 | Ninguno. |
| `bank_accounts.created_at` | 175 | 175 | 0 | 0 | space-naive: 175 | Ninguno. |

### IDs exactos de ROOT_SET

El manifiesto `scripts/cleanup_plan_ids.json` contiene los IDs del snapshot para raíces y KEEP_SET parciales. Marca `ready_to_execute=false`; sus `delete_candidate_ids` son sólo candidatos de tablas con regla parcial y no autorizan ejecución.
- Ventas raíz: `10,11,14,16,17,23,27,28,30,31,32,37,38,39,40,41,43,3141,3832`
- Cotizaciones raíz: ``
- OC raíz: `3931,3932,3934,3935,3936,3937,3946,3949,3996,3997,3998,3999,4000,4001,4003,4004,4005,4006,4015,4018,4065,4066,4067,4068,4069,4070,4072,4073,4074,4075`
- OT raíz: `3339,3340`
- Deudas raíz: `225,226,227,228,229,230,231,232,233,234`
- Pares documento/línea con identidad de producto ambigua al leer JSON: 1280; no se asociaron arbitrariamente.

## Cierre recursivo

| Iteración | Productos | Ventas | OC | Recepciones | OT | Lotes | Movimientos | Proveedores | Clientes | Cuentas | Facturas | Deudas |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 22 | 19 | 32 | 4 | 2 | 6 | 15 | 26 | 10 | 11 | 0 | 10 |
| 2 | 22 | 19 | 32 | 7 | 2 | 6 | 16 | 26 | 10 | 11 | 3 | 10 |
| 3 | 22 | 19 | 32 | 7 | 2 | 6 | 16 | 26 | 10 | 11 | 3 | 10 |

Punto fijo alcanzado en 3 iteraciones. El cierre documenta productos/lotes/orígenes seleccionados; movimientos genéricos y snapshots legacy no se convierten en documentos fuente.
Productos obligatorios del cierre calculado: **22**. Productos opcionales elegibles: 1781. Productos simulados finales: **70**.
La selección opcional usa sólo maestros válidos y no eliminados, excluye marcadores de fixtures y exige que no introduzcan stock positivo sin su grafo documental.

## Inventario por producto protegido

La cantidad física simulada se conserva en su fuente actual (lotes para `requires_lot`, ledger para el resto); las reservas se recalculan sólo con ventas pendientes y OT aprobadas retenidas.
| ID | SKU | Lote | Físico antes/objetivo | Reservado antes → simulado | Disponible antes → simulado | Ledger antes | Lotes antes | Ledger tras docs protegidos | Opening requerido | PPP antes | Costo apertura | Clase |
|---:|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | PRD001 | no | 450.0000 | 4.0000 → 4.0000 | 446.0000 → 446.0000 | 450.0000 | 0.0000 | 0.0000 | 450.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 2 | PRD002 | no | 829.0000 | 4.0000 → 4.0000 | 825.0000 → 825.0000 | 829.0000 | 0.0000 | 0.0000 | 829.0000 | 4096.3709 | 4096.370883594693 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 3 | PRD003 | no | 39.0000 | 1.0000 → 1.0000 | 38.0000 → 38.0000 | 39.0000 | 0.0000 | 0.0000 | 39.0000 | 25.8547 | 25.854700854700855 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 4 | PRD004 | no | 239.0000 | 8.0000 → 7.0000 | 231.0000 → 232.0000 | 239.0000 | 0.0000 | -1.0000 | 240.0000 | 24.4963 | 24.39419659961686 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 5 | INS001 | no | 1200.0000 | 0.0000 → 0.0000 | 1200.0000 → 1200.0000 | 1200.0000 | 0.0000 | 0.0000 | 1200.0000 | 5000.0000 | 5000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 6 | INS002 | no | 481.0000 | 0.0000 → 0.0000 | 481.0000 → 481.0000 | 481.0000 | 0.0000 | 0.0000 | 481.0000 | 1000.0000 | 1000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 7 | INS003 | no | 478.0000 | 0.0000 → 0.0000 | 478.0000 → 478.0000 | 478.0000 | 0.0000 | 0.0000 | 478.0000 | 100.0000 | 100.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 11 | prod02f | no | 6.0000 | 6.0000 → 6.0000 | 0.0000 → 0.0000 | 6.0000 | 0.0000 | 0.0000 | 6.0000 | 100.0000 | 100.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 14 | INS-MPR-001 | sí | 885.0000 | 0.0000 → 0.0000 | 885.0000 → 885.0000 | 885.0000 | 885.0000 | 894.0000 | -9.0000 | 2262.1469 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 16 | INS-ENV-002 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 17 | INS-ENV-003 | no | 498.0000 | 0.0000 → 0.0000 | 498.0000 → 498.0000 | 498.0000 | 0.0000 | -2.0000 | 500.0000 | 120.0000 | 119.52 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 18 | INS-ENV-004 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 19 | INS-ENV-005 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 20 | INS-ENV-006 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 21 | INS-ENV-007 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 22 | INS-ENV-008 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 23 | INS-ENV-009 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 24 | INS-ENV-010 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 25 | INS-ETQ-001 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 26 | INS-ETQ-002 | no | 498.0000 | 0.0000 → 0.0000 | 498.0000 → 498.0000 | 498.0000 | 0.0000 | -2.0000 | 500.0000 | 30.0000 | 29.88 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 27 | INS-ETQ-003 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 28 | INS-ETQ-004 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 29 | INS-ETQ-005 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 30 | INS-ETQ-006 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 31 | INS-ETQ-007 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 32 | INS-ETQ-008 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 33 | INS-ETQ-009 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 34 | INS-ETQ-010 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 35 | INS-ETQ-011 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 36 | INS-ETQ-012 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 37 | INS-ETQ-013 | no | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 0.0000 | 0.0000 | 10.0000 | 5000.0000 | 5000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39 | INS-ETQ-015 | no | 498.0000 | 0.0000 → 0.0000 | 498.0000 → 498.0000 | 498.0000 | 0.0000 | -2.0000 | 500.0000 | 120.0000 | 119.52 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 40 | INS-ETQ-016 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 41 | INS-ETQ-017 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 42 | INS-ETQ-018 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 43 | INS-ETQ-019 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 44 | INS-ETQ-020 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 45 | INS-ETQ-021 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 46 | INS-ETQ-022 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 47 | INS-ETQ-023 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 48 | INS-ETQ-024 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 49 | INS-ETQ-025 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 50 | INS-ETQ-026 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 52 | INS-ETQ-028 | no | 2500.0000 | 0.0000 → 0.0000 | 2500.0000 → 2500.0000 | 2500.0000 | 0.0000 | 0.0000 | 2500.0000 | 81.0000 | 81.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 53 | INS-ETQ-029 | no | 1480.0000 | 0.0000 → 0.0000 | 1480.0000 → 1480.0000 | 1480.0000 | 0.0000 | -20.0000 | 1500.0000 | 8.0000 | 7.8933333333333335 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 55 | INS-CAJ-001 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 56 | INS-CAJ-002 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 57 | INS-CAJ-003 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 59 | INS-CAJ-005 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 60 | PT-CLA-001 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 61 | PT-CLA-002 | no | 2.0000 | 0.0000 → 0.0000 | 2.0000 → 2.0000 | 2.0000 | 2.0000 | 2.0000 | 0.0000 | 1750.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 62 | PT-CLA-003 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 63 | PT-CLA-004 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 64 | PT-CLA-005 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 65 | PT-CLA-006 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 66 | PT-CLA-007 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 67 | PT-CLA-008 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 68 | PT-CLA-009 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 69 | PT-CLA-010 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 70 | PT-CLA-011 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 71 | PT-CLA-012 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 72 | PT-CLA-013 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 73 | PT-CLA-014 | no | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 74 | PT-CLA-015 | no | 80.0000 | 0.0000 → 0.0000 | 80.0000 → 80.0000 | 80.0000 | 0.0000 | 80.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 18023 | C1-PT-1790125690463 | sí | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 500.0000 | — | COSTO_NO_DETERMINABLE |
| 18026 | C2-PT-1790125690644 | sí | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 500.0000 | — | COSTO_NO_DETERMINABLE |
| 38587 | NOLOT-17905345987669 | no | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 0.0000 | 10.0000 | 0.0000 | 200.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 38609 | MP-REC-1790534602771 | sí | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 50.0000 | 50.0000 | 0.0000 | 1500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39176 | NOLOT-17905348172005 | no | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 0.0000 | 10.0000 | 0.0000 | 200.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39198 | MP-REC-1790534821120 | sí | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 50.0000 | 50.0000 | 0.0000 | 1500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |

Opening balances de cantidad requeridos: 15; positivos: 14; negativos (no representables como apertura): 1. Con costo derivable: 13; con fuente marcada confiable pero apertura aún no resuelta: 1; sin costo defendible: 1.
Los costos mostrados son sólo diagnósticos; no se usó `products.cost` como sustituto. La simulación de PPP no es completa porque requiere reproducir por orden cronológico los movimientos retenidos y la apertura al final; el planner marca este punto como bloqueador si no hay una fuente valorizada.

## Ledger vs lotes

| Caso | Productos | Delta absoluto | Clasificación del plan |
|---|---:|---:|---|
| V2 recalculado en snapshot actual | 182 | 3485.0000 | Productos activos `requires_lot`; comparar con informe V2 anterior si cambió el universo. |
| D — fuera del KEEP_SET pero sin marcador concluyente; requiere clasificación manual | 1 | 3.0000 | Provisional, no altera cantidades. |
| A — fuera del KEEP_SET y con marcador fixture explícito; candidato a desaparecer con su grafo | 181 | 3482.0000 | Provisional, no altera cantidades. |
| Diferencia protegida | Ver productos de inventario arriba | — | Requiere decisión de origen/apertura antes de redactar SQL. |

## Legacy snapshots

`page_data.inventory_items`: 954 items parseados; 932 no coinciden por SKU con el catálogo protegido simulado. La fila completa se conserva en esta simulación; filtrarla requiere una operación JSON específica pendiente.

## PPP y reservas

- Entradas de costo cero/nulo antes: 1383.
- Movimientos de costo cero/nulo retenidos por referencia documental identificable: 0; el resto sólo es candidato a borrar tras resolver la apertura.
- Líneas de reserva ambiguas antes: 406; simuladas en ventas/OT retenidas: 0. Reservas resueltas por producto: 76 productos antes, 70 después.
- El valor PPP posterior no se declara definitivo: no se simularon completamente lotes valorizados ni reejecución oficial del motor PPP.

## KEEP_SET / DELETE_SET por tabla

El KEEP_SET cuantificado abajo es parcial por diseño. Tablas sin política explícita se mantienen enteras; no se presentan como DELETE_SET final.
| Tabla | Total | Keep simulado | Delete candidato | Motivo |
|---|---:|---:|---:|---|
| `bank_accounts` | 186 | 11 | 175 | KEEP_SET simulado |
| `bank_reconciliation_audit` | 55 | 3 | 52 | KEEP_SET simulado |
| `bank_transaction_categories` | 10 | 10 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `bank_transaction_imports` | 5 | 1 | 4 | KEEP_SET simulado |
| `bank_transactions` | 77 | 9 | 68 | KEEP_SET simulado |
| `client_categories` | 13 | 13 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `clients` | 10 | 10 | 0 | KEEP_SET simulado |
| `collection_actions` | 0 | 0 | 0 | KEEP_SET simulado |
| `debt_audit` | 83 | 18 | 65 | KEEP_SET simulado |
| `debt_installments` | 139 | 33 | 106 | KEEP_SET simulado |
| `debt_payments` | 34 | 7 | 27 | KEEP_SET simulado |
| `debt_types` | 7 | 7 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `debts` | 44 | 10 | 34 | KEEP_SET simulado |
| `excel_import_previews` | 0 | 0 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `expense_categories` | 1 | 1 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `inventory_adjustment_audit` | 7 | 6 | 1 | KEEP_SET simulado |
| `inventory_adjustment_requests` | 4 | 3 | 1 | KEEP_SET simulado |
| `inventory_entries` | 2077 | 7 | 2070 | KEEP_SET simulado |
| `inventory_entry_items` | 1060 | 7 | 1053 | KEEP_SET simulado |
| `inventory_movements` | 8389 | 16 | 8373 | KEEP_SET simulado |
| `lot_stock` | 2003 | 6 | 1997 | KEEP_SET simulado |
| `lots` | 2003 | 6 | 1997 | KEEP_SET simulado |
| `operational_expense_audit` | 193 | 1 | 192 | KEEP_SET simulado |
| `operational_expense_occurrences` | 28 | 24 | 4 | KEEP_SET simulado |
| `operational_expenses` | 29 | 29 | 0 | KEEP_SET simulado |
| `page_data` | 25 | 25 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `product_margins` | 1 | 1 | 0 | KEEP_SET simulado |
| `product_recipe_items` | 3711 | 11 | 3700 | KEEP_SET simulado |
| `product_recipes` | 1840 | 3 | 1837 | KEEP_SET simulado |
| `product_suppliers` | 0 | 0 | 0 | KEEP_SET simulado |
| `production_lot_consumptions` | 267 | 1 | 266 | KEEP_SET simulado |
| `production_lot_outputs` | 266 | 1 | 265 | KEEP_SET simulado |
| `production_order_additional_items` | 1 | 1 | 0 | KEEP_SET simulado |
| `production_order_items` | 3950 | 8 | 3942 | KEEP_SET simulado |
| `production_orders` | 2105 | 2 | 2103 | KEEP_SET simulado |
| `products` | 15048 | 70 | 14978 | KEEP_SET simulado |
| `purchase_invoices` | 518 | 3 | 515 | KEEP_SET simulado |
| `purchase_order_items` | 1858 | 32 | 1826 | KEEP_SET simulado |
| `purchase_orders` | 1715 | 32 | 1683 | KEEP_SET simulado |
| `roles` | 7 | 7 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `sale_items` | 305 | 2 | 303 | KEEP_SET simulado |
| `sale_lot_movements` | 176 | 0 | 176 | KEEP_SET simulado |
| `sale_packaging_items` | 1094 | 0 | 1094 | KEEP_SET simulado |
| `sale_payment_items` | 133 | 1 | 132 | KEEP_SET simulado |
| `sale_payments` | 723 | 15 | 708 | KEEP_SET simulado |
| `sales` | 1938 | 19 | 1919 | KEEP_SET simulado |
| `sales_entries` | 0 | 0 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `sales_payment_history` | 142 | 5 | 137 | KEEP_SET simulado |
| `sales_status_history` | 1161 | 29 | 1132 | KEEP_SET simulado |
| `schema_migrations` | 23 | 23 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `supplier_contacts` | 7 | 0 | 7 | KEEP_SET simulado |
| `suppliers` | 1711 | 26 | 1685 | KEEP_SET simulado |
| `users` | 6 | 6 | 0 | sin política de eliminación; se conserva para no inferir DELETE |

## Simulación de claves foráneas

Claves foráneas inspeccionadas: 82.
Referencias que quedarían huérfanas según KEEP_SET parcial: 1 (preexistentes: 0; nuevas: 1).
| Hija.columna | Padre.columna | ID hijo | ID padre | Estado |
|---|---|---:|---:|---|
| `lot_stock.entry_id` | `inventory_entries.id` | 3155 | 1356 | would_orphan |

Las referencias polimórficas de `inventory_movements.reference_type/reference_id` no tienen FK; requieren conservar origen o reemplazo explícito. Conteos candidatos: PO movement refs to deleted docs: 888, sale movement refs to deleted docs: 1751, OT movement refs to deleted docs: 443.

## Conteos finales simulados

No se consideran finales hasta cerrar movimientos, apertura/valuación, finanzas y referencias polimórficas.
| Entidad | Actual | Simulado en cierre actual |
|---|---:|---:|
| Productos | 15048 | 70 |
| Ventas | 1904 | 19 |
| Cotizaciones | 34 | 0 |
| OC | 1715 | 32 |
| Recepciones | 2077 | 7 |
| Movimientos | 8389 | 16 |
| Lotes | 2003 | 6 |
| lot_stock | 2003 | 6 |
| OT | 2105 | 2 |
| Clientes | 10 | 10 |
| Proveedores | 1711 | 26 |
| Cuentas | 186 | 11 |
| Deudas | 44 | 10 |

## Orden de borrado

Orden topológico candidato hijo→padre calculado sobre el grafo FK completo: bank_reconciliation_audit, bank_transactions, bank_transaction_categories, bank_transaction_imports, client_categories, clients, collection_actions, debt_audit, debt_payments, debt_installments, debts, debt_types, excel_import_previews, inventory_adjustment_audit, inventory_adjustment_requests, inventory_entry_items, lot_stock, operational_expense_audit, operational_expense_occurrences, operational_expenses, expense_categories, page_data, product_margins, product_recipe_items, product_recipes, product_suppliers, production_lot_consumptions, production_lot_outputs, production_order_additional_items, production_order_items, purchase_invoices, purchase_order_items, sale_items, sale_lot_movements, sale_packaging_items, inventory_movements, lots, inventory_entries, production_orders, products, purchase_orders, sale_payment_items, bank_accounts, sale_payments, sales_entries, sales_payment_history, sales_status_history, sales, schema_migrations, supplier_contacts, suppliers, users, roles.
Tablas bloqueadas por ciclos en el grafo FK: ninguna.
No se generó `scripts/cleanup_development_database.sql`: el DELETE_SET no está completo ni la simulación de negocio/valuación está cerrada. Un orden parcial topológico sería engañoso frente a 82 FK, referencias polimórficas y relaciones de inventario con RESTRICT.
Orden conceptual que deberá concretarse antes de generar el SQL: acciones/auditorías hijas → pagos/items/historiales → movimientos y lotes no protegidos → entradas/facturas/OT/OC/ventas/deudas descartadas → productos/proveedores/cuentas descartados; nunca deshabilitar FK. Los ciclos polimórficos se deben resolver con orden explícito por grafo, no con constraints desactivadas.

## Bloqueadores y semáforo

- Cronología: GREEN
- KEEP_SET: GREEN para raíces; RED para cierre integral de historial/movimientos.
- GRAPH CLOSURE: RED — se alcanzó punto fijo en relaciones modeladas, pero el cierre no cubre aún grafos completos ni referencias polimórficas.
- INVENTARIO: RED — PPP y apertura cantidad/costo no reproducidos completamente.
- LOTES: RED — orígenes adicionales detectados; requiere decidir mantener origen versus migración auditable.
- PPP: RED — apertura valorizada no certificada.
- FINANZAS: RED — cierre de conciliación y referencias de pagos/transferencias aún incompleto.
- FK: RED — 1 referencias problemáticas en la simulación parcial.
- DELETE PLAN: RED.

**READY TO EXECUTE: NO**.

No se generó SQL de limpieza, porque el propio criterio de aceptación exige un plan determinístico GREEN. Sí se genera un verificador READ ONLY separado.
