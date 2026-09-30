# Plan de limpieza de `facturacion` — simulación READ ONLY

**Fecha UTC:** 2026-09-27T22:58:47+00:00
**Base verificada:** `facturacion`; transacción read-only `on`; timezone PostgreSQL `UTC`.
**No se ejecutaron INSERT, UPDATE, DELETE, TRUNCATE ni DDL.**

## ROOT SET

- Ventas: 30 (no cotizaciones), escogidas por `created_at` parseado DESC, `id` DESC.
- Cotizaciones: 30, escogidas por `created_at` parseado DESC, `id` DESC.
- OC raíz: 30; OT raíz: 10; deudas raíz: 10.
- Clientes: todos los 10 existentes (máximo 10).
- Cuentas raíz: 14; mínimo observado requerido por pagos/deudas/facturas protegidos: 14 (por encima del objetivo 10).

## Cronología normalizada

El parser usa `datetime.fromisoformat`, interpreta los valores naive en la zona PostgreSQL de la sesión, normaliza a UTC y nunca ordena TEXT lexicográficamente.
| Fuente | Filas | Parseables | NULL/vacíos | No parseables | Formatos encontrados | Muestras no parseables |
|---|---:|---:|---:|---|---|---|
| `sales.created_at` | 1904 | 1904 | 0 | 0 | ISO-T-naive: 25, ISO-T-with-offset: 1676, space-naive: 203 | Ninguno. |
| `quotes.created_at` | 34 | 34 | 0 | 0 | space-naive: 34 | Ninguno. |
| `purchase_orders.created_at` | 1715 | 1715 | 0 | 0 | ISO-T-naive: 17, ISO-T-with-offset: 1341, space-naive: 357 | Ninguno. |
| `production_orders.created_at` | 2105 | 2105 | 0 | 0 | space-naive: 2105 | Ninguno. |
| `debts.created_at` | 44 | 44 | 0 | 0 | space-with-offset: 44 | Ninguno. |
| `bank_accounts.created_at` | 176 | 176 | 0 | 0 | space-naive: 176 | Ninguno. |

### IDs exactos de ROOT_SET

El manifiesto `scripts/cleanup_plan_ids.json` contiene los IDs del snapshot para raíces y KEEP_SET parciales. Marca `ready_to_execute=false`; sus `delete_candidate_ids` son sólo candidatos de tablas con regla parcial y no autorizan ejecución.
- Ventas raíz: `13112,13118,13119,13456,13457,13459,13462,13473,13479,13481,13487,13488,13825,13826,13828,13831,13842,13848,13850,13856,13857,14194,14195,14197,14200,14211,14217,14219,14225,14226`
- Cotizaciones raíz: `4687,4748,4809,4870,5203,5374,5934,6226,6518,6709,6895,7079,7263,7463,7782,7972,8023,8334,8520,9264,9816,10917,11469,12021,12390,12759,13128,13497,13866,14235`
- OC raíz: `4003,4004,4005,4006,4014,4015,4017,4018,4019,4054,4055,4056,4057,4058,4059,4060,4061,4062,4063,4064,4065,4066,4067,4068,4069,4070,4072,4073,4074,4075`
- OT raíz: `5783,5787,5845,5849,5907,5911,5969,5973,6031,6035`
- Deudas raíz: `225,226,227,228,229,230,231,232,233,234`
- Pares documento/línea con identidad de producto ambigua al leer JSON: 1280; no se asociaron arbitrariamente.
- Raíces que pasan cronología/identidad y filtros cuantitativos: ventas 30/30, cotizaciones 30/30, OC 30/30, OT 10/10. Los marcadores de fixture no se excluyen por sí solos.

### Roots descartados y sustituciones

| Tipo | Root original | Motivo | Sustituto | Fecha del sustituto/root descartado |
|---|---:|---|---:|---|
| VENTA | 14007 | fecha futura; probable fixture | 14226 | 2026-09-27T18:48:32+00:00 |
| VENTA | 14006 | fecha futura; probable fixture | 14225 | 2026-09-27T18:48:31+00:00 |
| VENTA | 13638 | fecha futura; probable fixture | 14219 | 2026-09-27T18:48:28+00:00 |
| VENTA | 13637 | fecha futura; probable fixture | 14217 | 2026-09-27T18:48:27+00:00 |
| VENTA | 13269 | fecha futura; probable fixture | 14211 | 2026-09-27T18:48:25+00:00 |
| VENTA | 13268 | fecha futura; probable fixture | 14200 | 2026-09-27T18:47:09.217804+00:00 |
| VENTA | 12900 | fecha futura; probable fixture | 14197 | 2026-09-27T18:47:06.001235+00:00 |
| VENTA | 12899 | fecha futura; probable fixture | 14195 | 2026-09-27T18:47:04.722697+00:00 |
| VENTA | 12531 | fecha futura; probable fixture | 14194 | 2026-09-27T18:47:04.546407+00:00 |
| VENTA | 12530 | fecha futura; probable fixture | 13857 | 2026-09-27T18:44:53+00:00 |
| VENTA | 12162 | fecha futura; probable fixture | 13856 | 2026-09-27T18:44:52+00:00 |
| VENTA | 12161 | fecha futura; probable fixture | 13850 | 2026-09-27T18:44:49+00:00 |
| VENTA | 11793 | fecha futura; probable fixture | 13848 | 2026-09-27T18:44:48+00:00 |
| VENTA | 11792 | fecha futura; probable fixture | 13842 | 2026-09-27T18:44:46+00:00 |
| VENTA | 11241 | fecha futura; probable fixture | 13831 | 2026-09-27T18:43:31.572832+00:00 |
| VENTA | 11240 | fecha futura; probable fixture | 13828 | 2026-09-27T18:43:28.183854+00:00 |
| VENTA | 10689 | fecha futura; probable fixture | 13826 | 2026-09-27T18:43:26.750778+00:00 |
| VENTA | 10688 | fecha futura; probable fixture | 13825 | 2026-09-27T18:43:26.499682+00:00 |
| VENTA | 9588 | fecha futura; probable fixture | 13488 | 2026-09-27T18:09:31+00:00 |
| VENTA | 9587 | fecha futura; probable fixture | 13487 | 2026-09-27T18:09:30+00:00 |
| VENTA | 9036 | fecha futura; probable fixture | 13481 | 2026-09-27T18:09:27+00:00 |
| VENTA | 9035 | fecha futura; probable fixture | 13479 | 2026-09-27T18:09:26+00:00 |
| VENTA | 8475 | fecha futura; probable fixture | 13473 | 2026-09-27T18:09:25+00:00 |
| VENTA | 8474 | fecha futura; probable fixture | 13462 | 2026-09-27T18:08:10.382351+00:00 |
| VENTA | 8289 | fecha futura; probable fixture | 13459 | 2026-09-27T18:08:07.129719+00:00 |
| VENTA | 8288 | fecha futura; probable fixture | 13457 | 2026-09-27T18:08:05.694193+00:00 |
| VENTA | 8041 | fecha futura; probable fixture | 13456 | 2026-09-27T18:08:05.468609+00:00 |
| VENTA | 8040 | fecha futura; probable fixture | 13119 | 2026-09-27T18:04:36+00:00 |
| VENTA | 7927 | fecha futura; probable fixture | 13118 | 2026-09-27T18:04:35+00:00 |
| VENTA | 7926 | fecha futura; probable fixture | 13112 | 2026-09-27T18:04:32+00:00 |
| OC | 4016 | producto involucrado en delta ledger-vs-lotes | 4003 | 2026-09-27T18:45:11+00:00 |
| OT | 6030 | producto involucrado en delta ledger-vs-lotes | 5845 | 2026-09-27 18:03:04.738876+00 |
| OT | 5968 | producto involucrado en delta ledger-vs-lotes | 5787 | 2026-09-27 16:19:44.497503+00 |
| OT | 5906 | producto involucrado en delta ledger-vs-lotes | 5783 | 2026-09-27 16:19:40.460446+00 |

### Candidatos rechazados por causa

Los marcadores TEST/E2E/FIXTURE se reportan como indicios y por sí solos no descartan un documento.
| Tipo | Motivo objetivo de rechazo | Documentos |
|---|---|---:|
| sales | fecha futura; probable fixture | 43 |
| sales | líneas de producto legacy ambiguas/no resueltas | 2 |
| sales | producto involucrado en delta ledger-vs-lotes | 52 |
| sales | sin productos identificables | 1370 |
| purchase_orders | producto involucrado en delta ledger-vs-lotes | 45 |
| production_orders | producto involucrado en delta ledger-vs-lotes | 88 |

## Cierre recursivo

| Iteración | Productos | Ventas | OC | Recepciones | OT | Lotes | Movimientos | Proveedores | Clientes | Cuentas | Facturas | Deudas |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 99 | 60 | 30 | 16 | 15 | 28 | 80 | 21 | 10 | 10 | 5 | 10 |
| 2 | 104 | 60 | 35 | 16 | 15 | 33 | 85 | 26 | 10 | 10 | 5 | 10 |
| 3 | 104 | 60 | 35 | 21 | 15 | 33 | 85 | 26 | 10 | 10 | 5 | 10 |
| 4 | 104 | 60 | 35 | 21 | 15 | 33 | 85 | 26 | 10 | 10 | 5 | 10 |

Punto fijo alcanzado en 4 iteraciones. El cierre documenta productos/lotes/orígenes seleccionados; movimientos genéricos y snapshots legacy no se convierten en documentos fuente.
Productos obligatorios del cierre calculado: **104**. Productos opcionales elegibles: 1782. Productos simulados finales: **104**.
La selección opcional usa sólo maestros válidos y no eliminados, excluye marcadores de fixtures y exige que no introduzcan stock positivo sin su grafo documental.

## Inventario por producto protegido

La cantidad física simulada se conserva en su fuente actual (lotes para `requires_lot`, ledger para el resto); las reservas se recalculan sólo con ventas pendientes y OT aprobadas retenidas.
| ID | SKU | Lote | Físico antes/objetivo | Reservado antes → simulado | Disponible antes → simulado | Ledger antes | Lotes antes | Ledger tras docs protegidos | Opening requerido | PPP antes | Costo apertura | Clase |
|---:|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | PRD001 | no | 450.0000 | 4.0000 → 0.0000 | 446.0000 → 450.0000 | 450.0000 | 0.0000 | 0.0000 | 450.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 36821 | MP-A-17905259801548 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 100.0000 | 60.0000 | 100.0000 | -40.0000 | 2500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 36822 | SEMI-A-17905259801548 | sí | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 0.0000 | 20.0000 | 0.0000 | 20.0000 | 3000.0000 | — | COSTO_NO_DETERMINABLE |
| 36823 | FINAL-A-17905259801548 | sí | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 4500.0000 | — | COSTO_NO_DETERMINABLE |
| 36843 | MP-OT-1790525984358 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 60.0000 | 60.0000 | -40.0000 | 100.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 36844 | PT-OT-1790525984358 | sí | 40.0000 | 0.0000 → 0.0000 | 40.0000 → 40.0000 | 40.0000 | 40.0000 | 40.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 37410 | MP-A-17905321844177 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 100.0000 | 60.0000 | 100.0000 | -40.0000 | 2500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 37411 | SEMI-A-17905321844177 | sí | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 0.0000 | 20.0000 | 0.0000 | 20.0000 | 3000.0000 | — | COSTO_NO_DETERMINABLE |
| 37412 | FINAL-A-17905321844177 | sí | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 4500.0000 | — | COSTO_NO_DETERMINABLE |
| 37432 | MP-OT-1790532188233 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 60.0000 | 60.0000 | -40.0000 | 100.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 37433 | PT-OT-1790532188233 | sí | 40.0000 | 0.0000 → 0.0000 | 40.0000 → 40.0000 | 40.0000 | 40.0000 | 40.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 37723 | BOX-S-1790532272077 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37724 | BOX-L-1790532272134 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37725 | MIEL-500G-1790532272193 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37738 | BOX-S-1790532275284 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37739 | BOX-L-1790532275329 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37740 | MIEL-500G-1790532275382 | no | 30.0000 | 0.0000 → 0.0000 | 30.0000 → 30.0000 | 30.0000 | 0.0000 | -20.0000 | 50.0000 | 3000.0000 | 1800.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37742 | BOX-L-1790532276402 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37743 | MIEL-500G-1790532276466 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37999 | MP-A-17905324781165 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 100.0000 | 60.0000 | 100.0000 | -40.0000 | 2500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 38000 | SEMI-A-17905324781165 | sí | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 0.0000 | 20.0000 | 0.0000 | 20.0000 | 3000.0000 | — | COSTO_NO_DETERMINABLE |
| 38001 | FINAL-A-17905324781165 | sí | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 4500.0000 | — | COSTO_NO_DETERMINABLE |
| 38021 | MP-OT-1790532482202 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 60.0000 | 60.0000 | -40.0000 | 100.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 38022 | PT-OT-1790532482202 | sí | 40.0000 | 0.0000 → 0.0000 | 40.0000 → 40.0000 | 40.0000 | 40.0000 | 40.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 38023 | SALE-PPP-811DD5 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 2500.0000 | 2400.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38024 | HIST-COST-982407 | no | 196.0000 | 0.0000 → 0.0000 | 196.0000 → 196.0000 | 196.0000 | 0.0000 | -4.0000 | 200.0000 | 3265.3061 | 3200.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38029 | LOT-REST-9F59CA | sí | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 10.0000 | 0.0000 | 10.0000 | 2500.0000 | 0.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38030 | BOX-REST-768FCF | no | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 20.0000 | 0.0000 | 0.0000 | 20.0000 | 800.0000 | 680.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38037 | NO-DEL-DF0F9A | no | 15.0000 | 0.0000 → 0.0000 | 15.0000 → 15.0000 | 15.0000 | 0.0000 | -5.0000 | 20.0000 | 1500.0000 | 1125.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38289 | BOX-L-1790532564978 | no | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 20.0000 | 0.0000 | 0.0000 | 20.0000 | 1000.0000 | 1000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38306 | BOX-S-1790532566607 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38307 | BOX-L-1790532566660 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38308 | MIEL-500G-1790532566718 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38312 | BOX-S-1790532567109 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38313 | BOX-L-1790532567158 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38314 | MIEL-500G-1790532567196 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38327 | BOX-S-1790532570167 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38328 | BOX-L-1790532570215 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38329 | MIEL-500G-1790532570274 | no | 30.0000 | 0.0000 → 0.0000 | 30.0000 → 30.0000 | 30.0000 | 0.0000 | -20.0000 | 50.0000 | 3000.0000 | 1800.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38331 | BOX-L-1790532571204 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38332 | MIEL-500G-1790532571266 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38588 | MP-A-17905345990680 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 100.0000 | 60.0000 | 100.0000 | -40.0000 | 2500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 38589 | SEMI-A-17905345990680 | sí | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 0.0000 | 20.0000 | 0.0000 | 20.0000 | 3000.0000 | — | COSTO_NO_DETERMINABLE |
| 38590 | FINAL-A-17905345990680 | sí | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 4500.0000 | — | COSTO_NO_DETERMINABLE |
| 38610 | MP-OT-1790534603181 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 60.0000 | 60.0000 | -40.0000 | 100.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 38611 | PT-OT-1790534603181 | sí | 40.0000 | 0.0000 → 0.0000 | 40.0000 → 40.0000 | 40.0000 | 40.0000 | 40.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 38612 | SALE-PPP-6ADCC2 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 2500.0000 | 2400.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38613 | HIST-COST-8442C8 | no | 196.0000 | 0.0000 → 0.0000 | 196.0000 → 196.0000 | 196.0000 | 0.0000 | -4.0000 | 200.0000 | 3265.3061 | 3200.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38618 | LOT-REST-86756D | sí | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 10.0000 | 0.0000 | 10.0000 | 2500.0000 | 0.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38619 | BOX-REST-BA77E2 | no | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 20.0000 | 0.0000 | 0.0000 | 20.0000 | 800.0000 | 680.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38626 | NO-DEL-090188 | no | 15.0000 | 0.0000 → 0.0000 | 15.0000 → 15.0000 | 15.0000 | 0.0000 | -5.0000 | 20.0000 | 1500.0000 | 1125.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38878 | BOX-L-1790534686909 | no | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 20.0000 | 0.0000 | 0.0000 | 20.0000 | 1000.0000 | 1000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38895 | BOX-S-1790534688471 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38896 | BOX-L-1790534688530 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38897 | MIEL-500G-1790534688592 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38901 | BOX-S-1790534689036 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38902 | BOX-L-1790534689084 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38903 | MIEL-500G-1790534689145 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38916 | BOX-S-1790534692139 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38917 | BOX-L-1790534692175 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38918 | MIEL-500G-1790534692226 | no | 30.0000 | 0.0000 → 0.0000 | 30.0000 → 30.0000 | 30.0000 | 0.0000 | -20.0000 | 50.0000 | 3000.0000 | 1800.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38920 | BOX-L-1790534693253 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38921 | MIEL-500G-1790534693311 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39169 | MP-A-17905348170380 | sí | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 2500.0000 | — | COSTO_NO_DETERMINABLE |
| 39176 | NOLOT-17905348172005 | no | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 0.0000 | 10.0000 | 0.0000 | 200.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39177 | MP-A-17905348174767 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 100.0000 | 60.0000 | 100.0000 | -40.0000 | 2500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39178 | SEMI-A-17905348174767 | sí | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 0.0000 | 20.0000 | 0.0000 | 20.0000 | 3000.0000 | — | COSTO_NO_DETERMINABLE |
| 39179 | FINAL-A-17905348174767 | sí | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 4500.0000 | — | COSTO_NO_DETERMINABLE |
| 39197 | MP-MOB-1790534820871 | sí | 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1000.0000 | — | COSTO_NO_DETERMINABLE |
| 39198 | MP-REC-1790534821120 | sí | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 50.0000 | 50.0000 | 0.0000 | 1500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39199 | MP-OT-1790534821491 | sí | 60.0000 | 0.0000 → 0.0000 | 60.0000 → 60.0000 | 60.0000 | 60.0000 | -40.0000 | 100.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 39200 | PT-OT-1790534821491 | sí | 40.0000 | 0.0000 → 0.0000 | 40.0000 → 40.0000 | 40.0000 | 40.0000 | 40.0000 | 0.0000 | 0.0000 | — | COSTO_NO_DETERMINABLE |
| 39201 | SALE-PPP-FF420E | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 2500.0000 | 2400.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39202 | HIST-COST-9CDA15 | no | 196.0000 | 0.0000 → 0.0000 | 196.0000 → 196.0000 | 196.0000 | 0.0000 | -4.0000 | 200.0000 | 3265.3061 | 3200.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39207 | LOT-REST-D20A7C | sí | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 10.0000 | 0.0000 | 10.0000 | 2500.0000 | 0.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39208 | BOX-REST-DF1F6F | no | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 20.0000 | 0.0000 | 0.0000 | 20.0000 | 800.0000 | 680.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39212 | E2E-MP-C323B8 | sí | 80.0000 | 0.0000 → 0.0000 | 80.0000 → 80.0000 | 80.0000 | 80.0000 | 100.0000 | -20.0000 | 1000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39215 | NO-DEL-4E9F9A | no | 15.0000 | 0.0000 → 0.0000 | 15.0000 → 15.0000 | 15.0000 | 0.0000 | -5.0000 | 20.0000 | 1500.0000 | 1125.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39408 | PROD1-96f31f | no | 100.0000 | 0.0000 → 0.0000 | 100.0000 → 100.0000 | 100.0000 | 0.0000 | 100.0000 | 0.0000 | 1500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39409 | PROD2-717915 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 50.0000 | 0.0000 | 2000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39410 | CANT-4e874b | no | 45.0000 | 0.0000 → 0.0000 | 45.0000 → 45.0000 | 45.0000 | 0.0000 | 45.0000 | 0.0000 | 1200.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39411 | PART-A-a12388 | no | 100.0000 | 0.0000 → 0.0000 | 100.0000 → 100.0000 | 100.0000 | 100.0000 | 100.0000 | 0.0000 | 1000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39412 | PART-B-f94559 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 50.0000 | 50.0000 | 0.0000 | 2000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39413 | SUPP-6847e7 | no | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 0.0000 | 10.0000 | 0.0000 | 500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39414 | DOC-7c722e | no | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 0.0000 | 10.0000 | 0.0000 | 800.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39415 | TOTA-2901e5 | no | 100.0000 | 0.0000 → 0.0000 | 100.0000 → 100.0000 | 100.0000 | 0.0000 | 100.0000 | 0.0000 | 1500.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39416 | TOTB-c5bfe1 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 50.0000 | 0.0000 | 2000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39417 | SKU-28b652 | no | 10.0000 | 0.0000 → 0.0000 | 10.0000 → 10.0000 | 10.0000 | 0.0000 | 10.0000 | 0.0000 | 5000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39418 | SKU-db4ee1 | no | 13.0000 | 0.0000 → 0.0000 | 13.0000 → 13.0000 | 13.0000 | 0.0000 | 13.0000 | 0.0000 | 5000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39419 | SKU-ed34e0 | no | 13.0000 | 0.0000 → 0.0000 | 13.0000 → 13.0000 | 13.0000 | 0.0000 | 13.0000 | 0.0000 | 5000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39420 | SKU-24976a | no | 13.0000 | 0.0000 → 0.0000 | 13.0000 → 13.0000 | 13.0000 | 0.0000 | 13.0000 | 0.0000 | 5000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39421 | SKU-dbd143 | no | 13.0000 | 0.0000 → 0.0000 | 13.0000 → 13.0000 | 13.0000 | 0.0000 | 13.0000 | 0.0000 | 5000.0000 | — | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39467 | BOX-L-1790534905815 | no | 20.0000 | 0.0000 → 0.0000 | 20.0000 → 20.0000 | 20.0000 | 0.0000 | 0.0000 | 20.0000 | 1000.0000 | 1000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39484 | BOX-S-1790534907536 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39485 | BOX-L-1790534907583 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39486 | MIEL-500G-1790534907638 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39490 | BOX-S-1790534908043 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39491 | BOX-L-1790534908104 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39492 | MIEL-500G-1790534908149 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39505 | BOX-S-1790534910886 | no | 96.0000 | 0.0000 → 0.0000 | 96.0000 → 96.0000 | 96.0000 | 0.0000 | -4.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39506 | BOX-L-1790534910929 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39507 | MIEL-500G-1790534910969 | no | 30.0000 | 0.0000 → 0.0000 | 30.0000 → 30.0000 | 30.0000 | 0.0000 | -20.0000 | 50.0000 | 3000.0000 | 1800.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39509 | BOX-L-1790534912039 | no | 18.0000 | 0.0000 → 0.0000 | 18.0000 → 18.0000 | 18.0000 | 0.0000 | -2.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39510 | MIEL-500G-1790534912072 | no | 50.0000 | 0.0000 → 0.0000 | 50.0000 → 50.0000 | 50.0000 | 0.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |

Opening balances de cantidad requeridos: 76; positivos: 70; negativos (no representables como apertura): 6. Con costo derivable: 59; con fuente marcada confiable pero apertura aún no resuelta: 6; sin costo defendible: 11.
| Producto | SKU | Root que lo introduce/origen del lote | Marcador fixture | Físico | Ledger | Lotes | Opening | PPP | Costo disponible/estado | Diagnóstico |
|---:|---|---|:---:|---:|---:|---:|---:|---:|---|---|
| 1 | PRD001 | OC 4003 (2026-09-27T18:45:11+00:00); OC 4004 (2026-09-27T18:45:11+00:00); OC 4005 (2026-09-27T18:45:11+00:00); OC 4006 (2026-09-27T18:45:11+00:00); OC 4065 (2026-09-27T18:48:48+00:00); OC 4066 (2026-09-27T18:48:48+00:00); OC 4067 (2026-09-27T18:48:49+00:00); OC 4068 (2026-09-27T18:48:49+00:00); OC 4069 (2026-09-27T18:48:49+00:00); OC 4070 (2026-09-27T18:48:49+00:00); OC 4072 (2026-09-27T18:48:49+00:00); OC 4073 (2026-09-27T18:48:50+00:00); OC 4074 (2026-09-27T18:48:50+00:00); OC 4075 (2026-09-27T18:48:50+00:00) | no | 450.0000 | 450.0000 | 0.0000 | 450.0000 | 0.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 36821 | MP-A-17905259801548 | lote 5160 PURCHASE:2346 PO:3740 entrada:2346 OT:None | sí | 60.0000 | 100.0000 | 60.0000 | -40.0000 | 2500.0000 | sin costo apertura defendible | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 36822 | SEMI-A-17905259801548 | lote 5161 PRODUCTION:5782 PO:None entrada:None OT:5782 | sí | 20.0000 | 0.0000 | 20.0000 | 20.0000 | 3000.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 36843 | MP-OT-1790525984358 | OT 5787 (2026-09-27 16:19:44.497503+00) | sí | 60.0000 | 60.0000 | 60.0000 | 100.0000 | 0.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 37410 | MP-A-17905321844177 | lote 5214 PURCHASE:2371 PO:3809 entrada:2371 OT:None | sí | 60.0000 | 100.0000 | 60.0000 | -40.0000 | 2500.0000 | sin costo apertura defendible | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 37411 | SEMI-A-17905321844177 | lote 5215 PRODUCTION:5844 PO:None entrada:None OT:5844 | sí | 20.0000 | 0.0000 | 20.0000 | 20.0000 | 3000.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 37432 | MP-OT-1790532188233 | OT 5849 (2026-09-27 18:03:08.363871+00) | sí | 60.0000 | 60.0000 | 60.0000 | 100.0000 | 0.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 37723 | BOX-S-1790532272077 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37724 | BOX-L-1790532272134 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37725 | MIEL-500G-1790532272193 | VENTA/COTIZACIÓN 13112 (2026-09-27T18:04:32+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37738 | BOX-S-1790532275284 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37739 | BOX-L-1790532275329 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37740 | MIEL-500G-1790532275382 | VENTA/COTIZACIÓN 13118 (2026-09-27T18:04:35+00:00) | no | 30.0000 | 30.0000 | 0.0000 | 50.0000 | 3000.0000 | 1800.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37742 | BOX-L-1790532276402 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37743 | MIEL-500G-1790532276466 | VENTA/COTIZACIÓN 13119 (2026-09-27T18:04:36+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 37999 | MP-A-17905324781165 | lote 5268 PURCHASE:2396 PO:3878 entrada:2396 OT:None | sí | 60.0000 | 100.0000 | 60.0000 | -40.0000 | 2500.0000 | sin costo apertura defendible | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 38000 | SEMI-A-17905324781165 | lote 5269 PRODUCTION:5906 PO:None entrada:None OT:5906 | sí | 20.0000 | 0.0000 | 20.0000 | 20.0000 | 3000.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 38021 | MP-OT-1790532482202 | OT 5911 (2026-09-27 18:08:02.340531+00) | sí | 60.0000 | 60.0000 | 60.0000 | 100.0000 | 0.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 38023 | SALE-PPP-811DD5 | VENTA/COTIZACIÓN 13456 (2026-09-27T18:08:05.468609+00:00) | sí | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 2500.0000 | 2400.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38024 | HIST-COST-982407 | VENTA/COTIZACIÓN 13457 (2026-09-27T18:08:05.694193+00:00) | sí | 196.0000 | 196.0000 | 0.0000 | 200.0000 | 3265.3061 | 3200.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38029 | LOT-REST-9F59CA | VENTA/COTIZACIÓN 13459 (2026-09-27T18:08:07.129719+00:00) | sí | 10.0000 | 10.0000 | 10.0000 | 10.0000 | 2500.0000 | 0.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38030 | BOX-REST-768FCF | sin referencia directa a raíz | sí | 20.0000 | 20.0000 | 0.0000 | 20.0000 | 800.0000 | 680.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38037 | NO-DEL-DF0F9A | VENTA/COTIZACIÓN 13462 (2026-09-27T18:08:10.382351+00:00) | sí | 15.0000 | 15.0000 | 0.0000 | 20.0000 | 1500.0000 | 1125.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38289 | BOX-L-1790532564978 | VENTA/COTIZACIÓN 13473 (2026-09-27T18:09:25+00:00) | no | 20.0000 | 20.0000 | 0.0000 | 20.0000 | 1000.0000 | 1000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38306 | BOX-S-1790532566607 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38307 | BOX-L-1790532566660 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38308 | MIEL-500G-1790532566718 | VENTA/COTIZACIÓN 13479 (2026-09-27T18:09:26+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38312 | BOX-S-1790532567109 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38313 | BOX-L-1790532567158 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38314 | MIEL-500G-1790532567196 | VENTA/COTIZACIÓN 13481 (2026-09-27T18:09:27+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38327 | BOX-S-1790532570167 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38328 | BOX-L-1790532570215 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38329 | MIEL-500G-1790532570274 | VENTA/COTIZACIÓN 13487 (2026-09-27T18:09:30+00:00) | no | 30.0000 | 30.0000 | 0.0000 | 50.0000 | 3000.0000 | 1800.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38331 | BOX-L-1790532571204 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38332 | MIEL-500G-1790532571266 | VENTA/COTIZACIÓN 13488 (2026-09-27T18:09:31+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38588 | MP-A-17905345990680 | lote 5322 PURCHASE:2421 PO:3947 entrada:2421 OT:None | sí | 60.0000 | 100.0000 | 60.0000 | -40.0000 | 2500.0000 | sin costo apertura defendible | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 38589 | SEMI-A-17905345990680 | lote 5323 PRODUCTION:5968 PO:None entrada:None OT:5968 | sí | 20.0000 | 0.0000 | 20.0000 | 20.0000 | 3000.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 38610 | MP-OT-1790534603181 | OT 5973 (2026-09-27 18:43:23.295479+00) | sí | 60.0000 | 60.0000 | 60.0000 | 100.0000 | 0.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 38612 | SALE-PPP-6ADCC2 | VENTA/COTIZACIÓN 13825 (2026-09-27T18:43:26.499682+00:00) | sí | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 2500.0000 | 2400.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38613 | HIST-COST-8442C8 | VENTA/COTIZACIÓN 13826 (2026-09-27T18:43:26.750778+00:00) | sí | 196.0000 | 196.0000 | 0.0000 | 200.0000 | 3265.3061 | 3200.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38618 | LOT-REST-86756D | VENTA/COTIZACIÓN 13828 (2026-09-27T18:43:28.183854+00:00) | sí | 10.0000 | 10.0000 | 10.0000 | 10.0000 | 2500.0000 | 0.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38619 | BOX-REST-BA77E2 | sin referencia directa a raíz | sí | 20.0000 | 20.0000 | 0.0000 | 20.0000 | 800.0000 | 680.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38626 | NO-DEL-090188 | VENTA/COTIZACIÓN 13831 (2026-09-27T18:43:31.572832+00:00) | sí | 15.0000 | 15.0000 | 0.0000 | 20.0000 | 1500.0000 | 1125.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38878 | BOX-L-1790534686909 | VENTA/COTIZACIÓN 13842 (2026-09-27T18:44:46+00:00) | no | 20.0000 | 20.0000 | 0.0000 | 20.0000 | 1000.0000 | 1000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38895 | BOX-S-1790534688471 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38896 | BOX-L-1790534688530 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38897 | MIEL-500G-1790534688592 | VENTA/COTIZACIÓN 13848 (2026-09-27T18:44:48+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38901 | BOX-S-1790534689036 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38902 | BOX-L-1790534689084 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38903 | MIEL-500G-1790534689145 | VENTA/COTIZACIÓN 13850 (2026-09-27T18:44:49+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38916 | BOX-S-1790534692139 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38917 | BOX-L-1790534692175 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38918 | MIEL-500G-1790534692226 | VENTA/COTIZACIÓN 13856 (2026-09-27T18:44:52+00:00) | no | 30.0000 | 30.0000 | 0.0000 | 50.0000 | 3000.0000 | 1800.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38920 | BOX-L-1790534693253 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 38921 | MIEL-500G-1790534693311 | VENTA/COTIZACIÓN 13857 (2026-09-27T18:44:53+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39177 | MP-A-17905348174767 | lote 5376 PURCHASE:2446 PO:4016 entrada:2446 OT:None | sí | 60.0000 | 100.0000 | 60.0000 | -40.0000 | 2500.0000 | sin costo apertura defendible | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39178 | SEMI-A-17905348174767 | lote 5377 PRODUCTION:6030 PO:None entrada:None OT:6030 | sí | 20.0000 | 0.0000 | 20.0000 | 20.0000 | 3000.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 39199 | MP-OT-1790534821491 | OT 6035 (2026-09-27 18:47:01.598141+00) | sí | 60.0000 | 60.0000 | 60.0000 | 100.0000 | 0.0000 | sin costo apertura defendible | COSTO_NO_DETERMINABLE |
| 39201 | SALE-PPP-FF420E | VENTA/COTIZACIÓN 14194 (2026-09-27T18:47:04.546407+00:00) | sí | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 2500.0000 | 2400.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39202 | HIST-COST-9CDA15 | VENTA/COTIZACIÓN 14195 (2026-09-27T18:47:04.722697+00:00) | sí | 196.0000 | 196.0000 | 0.0000 | 200.0000 | 3265.3061 | 3200.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39207 | LOT-REST-D20A7C | VENTA/COTIZACIÓN 14197 (2026-09-27T18:47:06.001235+00:00) | sí | 10.0000 | 10.0000 | 10.0000 | 10.0000 | 2500.0000 | 0.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39208 | BOX-REST-DF1F6F | sin referencia directa a raíz | sí | 20.0000 | 20.0000 | 0.0000 | 20.0000 | 800.0000 | 680.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39212 | E2E-MP-C323B8 | OC 4019 (2026-09-27T18:47:07+00:00) | sí | 80.0000 | 80.0000 | 80.0000 | -20.0000 | 1000.0000 | sin costo apertura defendible | COSTO_CONFIABLE — PPP ledger sin entradas cero/nulas |
| 39215 | NO-DEL-4E9F9A | VENTA/COTIZACIÓN 14200 (2026-09-27T18:47:09.217804+00:00) | sí | 15.0000 | 15.0000 | 0.0000 | 20.0000 | 1500.0000 | 1125.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39467 | BOX-L-1790534905815 | VENTA/COTIZACIÓN 14211 (2026-09-27T18:48:25+00:00) | no | 20.0000 | 20.0000 | 0.0000 | 20.0000 | 1000.0000 | 1000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39484 | BOX-S-1790534907536 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39485 | BOX-L-1790534907583 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39486 | MIEL-500G-1790534907638 | VENTA/COTIZACIÓN 14217 (2026-09-27T18:48:27+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39490 | BOX-S-1790534908043 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39491 | BOX-L-1790534908104 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39492 | MIEL-500G-1790534908149 | VENTA/COTIZACIÓN 14219 (2026-09-27T18:48:28+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39505 | BOX-S-1790534910886 | sin referencia directa a raíz | no | 96.0000 | 96.0000 | 0.0000 | 100.0000 | 500.0000 | 480.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39506 | BOX-L-1790534910929 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39507 | MIEL-500G-1790534910969 | VENTA/COTIZACIÓN 14225 (2026-09-27T18:48:31+00:00) | no | 30.0000 | 30.0000 | 0.0000 | 50.0000 | 3000.0000 | 1800.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39509 | BOX-L-1790534912039 | sin referencia directa a raíz | no | 18.0000 | 18.0000 | 0.0000 | 20.0000 | 1000.0000 | 900.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
| 39510 | MIEL-500G-1790534912072 | VENTA/COTIZACIÓN 14226 (2026-09-27T18:48:32+00:00) | no | 50.0000 | 50.0000 | 0.0000 | 50.0000 | 3000.0000 | 3000.0 | COSTO_DERIVABLE — preserva PPP antes desde ledger documentado |
Los costos mostrados son sólo diagnósticos; no se usó `products.cost` como sustituto. La simulación de PPP no es completa porque requiere reproducir por orden cronológico los movimientos retenidos y la apertura al final; el planner marca este punto como bloqueador si no hay una fuente valorizada.

## Ledger vs lotes

| Caso | Productos | Delta absoluto | Clasificación del plan |
|---|---:|---:|---|
| V2 recalculado en snapshot actual | 182 | 3485.0000 | Productos activos `requires_lot`; comparar con informe V2 anterior si cambió el universo. |
| D — fuera del KEEP_SET pero sin marcador concluyente; requiere clasificación manual | 1 | 3.0000 | Provisional, no altera cantidades. |
| A — fuera del KEEP_SET y con marcador fixture explícito; candidato a desaparecer con su grafo | 171 | 3182.0000 | Provisional, no altera cantidades. |
| B — protegido; diferencia permanece y requiere decisión | 5 | 200.0000 | Provisional, no altera cantidades. |
| D — protegido; investigación manual de costo/origen | 5 | 100.0000 | Provisional, no altera cantidades. |
| Diferencia protegida | Ver productos de inventario arriba | — | Requiere decisión de origen/apertura antes de redactar SQL. |

## Lotes protegidos y origen documental

Lotes protegidos en el cierre simulado: 33. Cada lote debe tener cantidad/costo y un origen retenido o una referencia polimórfica resuelta antes de autorizar borrado.
| Lote | Producto | SKU | Disponible | Costo unitario | Documento origen y estado |
|---:|---:|---|---:|---:|---|
| 5160 | 36821 | MP-A-17905259801548 | 60.0000 | — | OC 3740 (KEEP); RECEPCIÓN 2346 (KEEP) |
| 5161 | 36822 | SEMI-A-17905259801548 | 20.0000 | — | OT 5782 (KEEP) |
| 5162 | 36823 | FINAL-A-17905259801548 | 0.0000 | — | OT 5783 (KEEP) |
| 5172 | 36843 | MP-OT-1790525984358 | 60.0000 | — | PURCHASE:None (polimórfico/no resuelto) |
| 5173 | 36844 | PT-OT-1790525984358 | 40.0000 | — | OT 5787 (KEEP) |
| 5214 | 37410 | MP-A-17905321844177 | 60.0000 | — | OC 3809 (KEEP); RECEPCIÓN 2371 (KEEP) |
| 5215 | 37411 | SEMI-A-17905321844177 | 20.0000 | — | OT 5844 (KEEP) |
| 5216 | 37412 | FINAL-A-17905321844177 | 0.0000 | — | OT 5845 (KEEP) |
| 5226 | 37432 | MP-OT-1790532188233 | 60.0000 | — | PURCHASE:None (polimórfico/no resuelto) |
| 5227 | 37433 | PT-OT-1790532188233 | 40.0000 | — | OT 5849 (KEEP) |
| 5268 | 37999 | MP-A-17905324781165 | 60.0000 | — | OC 3878 (KEEP); RECEPCIÓN 2396 (KEEP) |
| 5269 | 38000 | SEMI-A-17905324781165 | 20.0000 | — | OT 5906 (KEEP) |
| 5270 | 38001 | FINAL-A-17905324781165 | 0.0000 | — | OT 5907 (KEEP) |
| 5280 | 38021 | MP-OT-1790532482202 | 60.0000 | — | PURCHASE:None (polimórfico/no resuelto) |
| 5281 | 38022 | PT-OT-1790532482202 | 40.0000 | — | OT 5911 (KEEP) |
| 5283 | 38029 | LOT-REST-9F59CA | 10.0000 | — | PURCHASE:None (polimórfico/no resuelto) |
| 5322 | 38588 | MP-A-17905345990680 | 60.0000 | — | OC 3947 (KEEP); RECEPCIÓN 2421 (KEEP) |
| 5323 | 38589 | SEMI-A-17905345990680 | 20.0000 | — | OT 5968 (KEEP) |
| 5324 | 38590 | FINAL-A-17905345990680 | 0.0000 | — | OT 5969 (KEEP) |
| 5334 | 38610 | MP-OT-1790534603181 | 60.0000 | — | PURCHASE:None (polimórfico/no resuelto) |
| 5335 | 38611 | PT-OT-1790534603181 | 40.0000 | — | OT 5973 (KEEP) |
| 5337 | 38618 | LOT-REST-86756D | 10.0000 | — | PURCHASE:None (polimórfico/no resuelto) |
| 5376 | 39177 | MP-A-17905348174767 | 60.0000 | — | OC 4016 (KEEP); RECEPCIÓN 2446 (KEEP) |
| 5377 | 39178 | SEMI-A-17905348174767 | 20.0000 | — | OT 6030 (KEEP) |
| 5378 | 39179 | FINAL-A-17905348174767 | 0.0000 | — | OT 6031 (KEEP) |
| 5387 | 39198 | MP-REC-1790534821120 | 50.0000 | — | OC 4018 (KEEP); RECEPCIÓN 2447 (KEEP) |
| 5388 | 39199 | MP-OT-1790534821491 | 60.0000 | — | PURCHASE:None (polimórfico/no resuelto) |
| 5389 | 39200 | PT-OT-1790534821491 | 40.0000 | — | OT 6035 (KEEP) |
| 5391 | 39207 | LOT-REST-D20A7C | 10.0000 | — | PURCHASE:None (polimórfico/no resuelto) |
| 5394 | 39212 | E2E-MP-C323B8 | 80.0000 | — | OC 4019 (KEEP); RECEPCIÓN 2449 (KEEP) |
| 5426 | 39411 | PART-A-a12388 | 40.0000 | — | OC 4056 (KEEP); RECEPCIÓN 2454 (KEEP) |
| 5427 | 39411 | PART-A-a12388 | 60.0000 | — | OC 4056 (KEEP); RECEPCIÓN 2455 (KEEP) |
| 5428 | 39412 | PART-B-f94559 | 50.0000 | — | OC 4056 (KEEP); RECEPCIÓN 2455 (KEEP) |

## Ventas protegidas y documentos hijos

En cotizaciones se valida el snapshot JSON de líneas (no existe obligación de reserva/movimiento de stock); en ventas se valida línea relacional o snapshot. Los hijos de pago, empaque, lote e historial que existen se verifican en la cobertura del grafo siguiente.
| Documento | Estado | Items relacionales | Líneas snapshot | Pagos | Historial estado |
|---:|---|---:|---:|---:|---:|
| 4687 | Cotización | 0 | 1 | 0 | 0 |
| 4748 | Cotización | 0 | 1 | 0 | 0 |
| 4809 | Cotización | 0 | 1 | 0 | 0 |
| 4870 | Cotización | 0 | 1 | 0 | 0 |
| 5203 | Cotización | 0 | 1 | 0 | 0 |
| 5374 | Cotización | 0 | 1 | 0 | 0 |
| 5934 | Cotización | 0 | 1 | 0 | 0 |
| 6226 | Cotización | 0 | 1 | 0 | 0 |
| 6518 | Cotización | 0 | 1 | 0 | 0 |
| 6709 | Cotización | 0 | 1 | 0 | 0 |
| 6895 | Cotización | 0 | 1 | 0 | 0 |
| 7079 | Cotización | 0 | 1 | 0 | 0 |
| 7263 | Cotización | 0 | 1 | 0 | 0 |
| 7463 | Cotización | 0 | 1 | 0 | 0 |
| 7782 | Cotización | 0 | 1 | 0 | 0 |
| 7972 | Cotización | 0 | 1 | 0 | 0 |
| 8023 | Cotización | 0 | 1 | 0 | 0 |
| 8334 | Cotización | 0 | 1 | 0 | 0 |
| 8520 | Cotización | 0 | 1 | 0 | 0 |
| 9264 | Cotización | 0 | 1 | 0 | 0 |
| 9816 | Cotización | 0 | 1 | 0 | 0 |
| 10917 | Cotización | 0 | 1 | 0 | 0 |
| 11469 | Cotización | 0 | 1 | 0 | 0 |
| 12021 | Cotización | 0 | 1 | 0 | 0 |
| 12390 | Cotización | 0 | 1 | 0 | 0 |
| 12759 | Cotización | 0 | 1 | 0 | 0 |
| 13112 | En Preparación | 0 | 1 | 0 | 0 |
| 13118 | Completada | 1 | 1 | 1 | 2 |
| 13119 | En Preparación | 0 | 1 | 0 | 0 |
| 13128 | Cotización | 0 | 1 | 0 | 0 |
| 13456 | Completada | 1 | 1 | 0 | 0 |
| 13457 | Completada | 1 | 1 | 0 | 0 |
| 13459 | Cancelada | 1 | 1 | 1 | 1 |
| 13462 | Completada | 1 | 1 | 0 | 0 |
| 13473 | En Preparación | 0 | 1 | 0 | 0 |
| 13479 | En Preparación | 0 | 1 | 0 | 0 |
| 13481 | En Preparación | 0 | 1 | 0 | 0 |
| 13487 | Completada | 1 | 1 | 1 | 2 |
| 13488 | En Preparación | 0 | 1 | 0 | 0 |
| 13497 | Cotización | 0 | 1 | 0 | 0 |
| 13825 | Completada | 1 | 1 | 0 | 0 |
| 13826 | Completada | 1 | 1 | 0 | 0 |
| 13828 | Cancelada | 1 | 1 | 1 | 1 |
| 13831 | Completada | 1 | 1 | 0 | 0 |
| 13842 | En Preparación | 0 | 1 | 0 | 0 |
| 13848 | En Preparación | 0 | 1 | 0 | 0 |
| 13850 | En Preparación | 0 | 1 | 0 | 0 |
| 13856 | Completada | 1 | 1 | 1 | 2 |
| 13857 | En Preparación | 0 | 1 | 0 | 0 |
| 13866 | Cotización | 0 | 1 | 0 | 0 |
| 14194 | Completada | 1 | 1 | 0 | 0 |
| 14195 | Completada | 1 | 1 | 0 | 0 |
| 14197 | Cancelada | 1 | 1 | 1 | 1 |
| 14200 | Completada | 1 | 1 | 0 | 0 |
| 14211 | En Preparación | 0 | 1 | 0 | 0 |
| 14217 | En Preparación | 0 | 1 | 0 | 0 |
| 14219 | En Preparación | 0 | 1 | 0 | 0 |
| 14225 | Completada | 1 | 1 | 1 | 2 |
| 14226 | En Preparación | 0 | 1 | 0 | 0 |
| 14235 | Cotización | 0 | 1 | 0 | 0 |

## Cobertura de hijos por grafo

Comprobación fila a fila: cada hijo existente que referencia a un padre protegido debe pertenecer también al KEEP_SET.
| Grafo | Hijos omitidos de padres protegidos |
|---|---:|
| SALES | 0 |
| PURCHASE | 0 |
| PRODUCTION | 0 |
| RECIPES | 0 |
| FINANCE | 0 |
| LOT STOCK | 0 |

## Referencias polimórficas de movimientos conservados

Movimientos retenidos con referencia inválida/eliminada o tipo genérico sin política explícita: 0.
| Movimiento | reference_type | reference_id | Diagnóstico |
|---:|---|---:|---|

### Universo de reference_type

| reference_type | Movimientos actuales | Conservados en simulación |
|---|---:|---:|
| <NULL> | 3887 | 0 |
| sale | 1399 | 45 |
| MANUAL_ENTRY | 1337 | 0 |
| purchase_order | 894 | 24 |
| production_order | 449 | 10 |
| sale_cancellation | 354 | 6 |
| inventory_entry_item | 32 | 0 |
| reconciliation_orphan | 26 | 0 |
| initial_seed | 7 | 0 |
| reconciliation | 3 | 0 |
| inventory_adjustment | 1 | 0 |

## Legacy snapshots

`page_data.inventory_items`: 954 items parseados; 931 no coinciden por SKU con el catálogo protegido simulado. La fila completa se conserva en esta simulación; filtrarla requiere una operación JSON específica pendiente.

## PPP y reservas

- Entradas de costo cero/nulo antes: 1383.
- Movimientos de costo cero/nulo retenidos por referencia documental identificable: 5; el resto sólo es candidato a borrar tras resolver la apertura.
- Líneas de reserva ambiguas antes: 406; simuladas en ventas/OT retenidas: 0. Reservas resueltas por producto: 114 productos antes, 104 después.
- El valor PPP posterior no se declara definitivo: no se simularon completamente lotes valorizados ni reejecución oficial del motor PPP.

## KEEP_SET / DELETE_SET por tabla

El KEEP_SET cuantificado abajo es parcial por diseño. Tablas sin política explícita se mantienen enteras; no se presentan como DELETE_SET final.
| Tabla | Total | Keep simulado | Delete candidato | Motivo |
|---|---:|---:|---:|---|
| `bank_accounts` | 186 | 14 | 172 | KEEP_SET simulado |
| `bank_reconciliation_audit` | 55 | 5 | 50 | KEEP_SET simulado |
| `bank_transaction_categories` | 10 | 10 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `bank_transaction_imports` | 5 | 0 | 5 | KEEP_SET simulado |
| `bank_transactions` | 77 | 5 | 72 | KEEP_SET simulado |
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
| `inventory_adjustment_audit` | 7 | 4 | 3 | KEEP_SET simulado |
| `inventory_adjustment_requests` | 4 | 2 | 2 | KEEP_SET simulado |
| `inventory_entries` | 2077 | 21 | 2056 | KEEP_SET simulado |
| `inventory_entry_items` | 1060 | 24 | 1036 | KEEP_SET simulado |
| `inventory_movements` | 8389 | 85 | 8304 | KEEP_SET simulado |
| `lot_stock` | 2003 | 33 | 1970 | KEEP_SET simulado |
| `lots` | 2003 | 33 | 1970 | KEEP_SET simulado |
| `operational_expense_audit` | 193 | 0 | 193 | KEEP_SET simulado |
| `operational_expense_occurrences` | 28 | 28 | 0 | KEEP_SET simulado |
| `operational_expenses` | 29 | 28 | 1 | KEEP_SET simulado |
| `page_data` | 25 | 25 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `product_margins` | 1 | 0 | 1 | KEEP_SET simulado |
| `product_recipe_items` | 3711 | 0 | 3711 | KEEP_SET simulado |
| `product_recipes` | 1840 | 0 | 1840 | KEEP_SET simulado |
| `product_suppliers` | 0 | 0 | 0 | KEEP_SET simulado |
| `production_lot_consumptions` | 267 | 15 | 252 | KEEP_SET simulado |
| `production_lot_outputs` | 266 | 15 | 251 | KEEP_SET simulado |
| `production_order_additional_items` | 1 | 0 | 1 | KEEP_SET simulado |
| `production_order_items` | 3950 | 5 | 3945 | KEEP_SET simulado |
| `production_orders` | 2105 | 15 | 2090 | KEEP_SET simulado |
| `products` | 15048 | 104 | 14944 | KEEP_SET simulado |
| `purchase_invoices` | 518 | 5 | 513 | KEEP_SET simulado |
| `purchase_order_items` | 1858 | 38 | 1820 | KEEP_SET simulado |
| `purchase_orders` | 1715 | 35 | 1680 | KEEP_SET simulado |
| `roles` | 7 | 7 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `sale_items` | 305 | 16 | 289 | KEEP_SET simulado |
| `sale_lot_movements` | 176 | 3 | 173 | KEEP_SET simulado |
| `sale_packaging_items` | 1094 | 29 | 1065 | KEEP_SET simulado |
| `sale_payment_items` | 133 | 0 | 133 | KEEP_SET simulado |
| `sale_payments` | 723 | 7 | 716 | KEEP_SET simulado |
| `sales` | 1938 | 60 | 1878 | KEEP_SET simulado |
| `sales_entries` | 0 | 0 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `sales_payment_history` | 142 | 4 | 138 | KEEP_SET simulado |
| `sales_status_history` | 1161 | 11 | 1150 | KEEP_SET simulado |
| `schema_migrations` | 23 | 23 | 0 | sin política de eliminación; se conserva para no inferir DELETE |
| `supplier_contacts` | 7 | 0 | 7 | KEEP_SET simulado |
| `suppliers` | 1711 | 26 | 1685 | KEEP_SET simulado |
| `users` | 6 | 6 | 0 | sin política de eliminación; se conserva para no inferir DELETE |

## Simulación de claves foráneas

Claves foráneas inspeccionadas: 82.
Referencias que quedarían huérfanas según KEEP_SET parcial: 0 (preexistentes: 0; nuevas: 0).
| Hija.columna | Padre.columna | ID hijo | ID padre | Estado |
|---|---|---:|---:|---|

Las referencias polimórficas de `inventory_movements.reference_type/reference_id` no tienen FK; requieren conservar origen o reemplazo explícito. Conteos candidatos: PO movement refs to deleted docs: 870, sale movement refs to deleted docs: 1702, OT movement refs to deleted docs: 439.

## Conteos finales simulados

No se consideran finales hasta cerrar movimientos, apertura/valuación, finanzas y referencias polimórficas.
| Entidad | Actual | Simulado en cierre actual |
|---|---:|---:|
| Productos | 15048 | 104 |
| Ventas | 1904 | 30 |
| Cotizaciones | 34 | 30 |
| OC | 1715 | 35 |
| Recepciones | 2077 | 21 |
| Movimientos | 8389 | 85 |
| Lotes | 2003 | 33 |
| lot_stock | 2003 | 33 |
| OT | 2105 | 15 |
| Clientes | 10 | 10 |
| Proveedores | 1711 | 26 |
| Cuentas | 186 | 14 |
| Deudas | 44 | 10 |

## Orden de borrado

Orden topológico candidato hijo→padre calculado sobre el grafo FK completo: bank_reconciliation_audit, bank_transactions, bank_transaction_categories, bank_transaction_imports, client_categories, clients, collection_actions, debt_audit, debt_payments, debt_installments, debts, debt_types, excel_import_previews, inventory_adjustment_audit, inventory_adjustment_requests, inventory_entry_items, lot_stock, operational_expense_audit, operational_expense_occurrences, operational_expenses, expense_categories, page_data, product_margins, product_recipe_items, product_recipes, product_suppliers, production_lot_consumptions, production_lot_outputs, production_order_additional_items, production_order_items, purchase_invoices, purchase_order_items, sale_items, sale_lot_movements, sale_packaging_items, inventory_movements, lots, inventory_entries, production_orders, products, purchase_orders, sale_payment_items, bank_accounts, sale_payments, sales_entries, sales_payment_history, sales_status_history, sales, schema_migrations, supplier_contacts, suppliers, users, roles.
Tablas bloqueadas por ciclos en el grafo FK: ninguna.
No se generó `scripts/cleanup_development_database.sql`: el DELETE_SET no está completo ni la simulación de negocio/valuación está cerrada. Un orden parcial topológico sería engañoso frente a 82 FK, referencias polimórficas y relaciones de inventario con RESTRICT.
Orden conceptual que deberá concretarse antes de generar el SQL: acciones/auditorías hijas → pagos/items/historiales → movimientos y lotes no protegidos → entradas/facturas/OT/OC/ventas/deudas descartadas → productos/proveedores/cuentas descartados; nunca deshabilitar FK. Los ciclos polimórficos se deben resolver con orden explícito por grafo, no con constraints desactivadas.

## Bloqueadores y semáforo

- CRONOLOGÍA: GREEN
- ROOT SET: GREEN — disponibles ventas 30/30, cotizaciones 30/30, OC 30/30, OT 10/10 tras criterio de coherencia.
- GRAPH CLOSURE: RED — el cierre técnico llega a punto fijo en 4 iteraciones, pero movimientos/orígenes y grafos hijos aún no están completos.
- INVENTARIO: RED — openings positivos 70, negativos 6, sin costo defendible 11; inventario/PPP no certificados.
- LOTES: RED — se requiere origen retenido y costo de lote identificable para los 33 lotes protegidos.
- PPP: RED — no se reprodujo el motor oficial completo ni se certificó costo de apertura.
- FINANZAS: GREEN — hijos financieros de las cuentas/deudas protegidas revisados.
- SALES CHILDREN: GREEN — líneas/snapshot y todos los hijos existentes de las raíces.
- PURCHASE CHILDREN: GREEN — items, recepciones, facturas y lotes de padres protegidos.
- PRODUCTION CHILDREN: GREEN — items, consumos, salidas, lotes y recetas requeridas.
- PAGE_DATA: RED — 931 snapshots no corresponden al catálogo simulado y la mutación JSON segura aún no está definida.
- POLYMORPHIC REFERENCES: GREEN — referencias inválidas/genéricas retenidas: 0.
- FK: GREEN — 0 referencias problemáticas en la simulación parcial.
- DELETE PLAN: RED — no se generan DELETEs mientras cualquier gate esté RED.

**READY TO EXECUTE: NO**.

No se generó SQL de limpieza, porque el propio criterio de aceptación exige un plan determinístico GREEN. Sí se genera un verificador READ ONLY separado.
