# Validación real en navegador aislado

Playwright y Chromium existentes, puerto 15021, cuenta sintética y mismo usuario PostgreSQL restringido. El proceso verifica que app.root_path corresponde a la copia temporal; se bloquean accesos locales a otros puertos, incluido el ERP normal.

| CASO | FUNCIÓN | ESTADO | RESULTADO |
|---|---|---|---|
| UI-productos-1 | productos | PASS | CERT-37a685b5f4ad	CERT-37a685b5f4ad	Producto Terminado	General	-	-	-	-	-	UN	-	-	No (Opc.)	0	Activo	-	 |
| UI-proveedores-1 | proveedores | PASS | CERT-969299b2eadd |
| UI-ordenes_compra-1 | ordenes_compra | PASS | OC-05706 |
| UI-recepcion-1 | recepcion | PASS | CERT-06b5db05a874 |
| UI-cotizaciones-1 | cotizaciones | PASS | {'neto': 27000, 'iva': 5130, 'total': 32130} |
| UI-ventas-1 | ventas | PASS | 	P-04185	 C CERT-71e327ed217b CERT-71e327ed217b@cert.invalid 	 21/10/2026 00:01:20 	 CERT-37a685b5f4ad (1) 	 $11.900 	 Pendiente	 Sin Boleta Pendiente	 Vence (Cobrar): 21/10/2026 	 CA CERT Administrador |
| UI-inventario-1 | inventario | PASS |                  CERT-37a685b5f4ad                                                               CERT-37a685b5f4ad                                                                                General                                                                                                                             Principal(11)                                                                                                                                                                  |
| UI-produccion-1 | produccion | PASS | OT-09084 |
| UI-cxc-1 | cxc | PASS |  2026-10-21	Hoy	 P-04185 BOL-00554 / 2026-10-21 	 CERT-71e327ed217b 	$11,900	$0	$11,900	⏳ Pendiente	Sin gestión	Sin gestión	—	 Gestión (0) Cobrar |
| UI-cxp-1 | cxp | PASS | CERT-660d6fbe643e |
| UI-gastos-1 | gastos | PASS | CERT-5a93cac406cf |
| UI-bancos-1 | bancos | PASS | CERT-c81a335fc611 |
| UI-flujo_caja-1 | flujo_caja | PASS | {'initial': 0, 'inflows': 0, 'outflows': 24038, 'final': -24038} |
| UI-reportes-1 | reportes | PASS | 3221294355 |
| UI-productos-2 | productos | PASS | CERT-6576a4cc765d	CERT-6576a4cc765d	Producto Terminado	General	-	-	-	-	-	UN	-	-	No (Opc.)	0	Activo	-	 |
| UI-proveedores-2 | proveedores | PASS | CERT-fe56b6cabff3 |
| UI-ordenes_compra-2 | ordenes_compra | PASS | OC-05707 |
| UI-recepcion-2 | recepcion | PASS | CERT-149dbb901d2d |
| UI-cotizaciones-2 | cotizaciones | PASS | {'neto': 27000, 'iva': 5130, 'total': 32130} |
| UI-ventas-2 | ventas | PASS | 	P-04188	 C CERT-d0f9ec76d1ee CERT-d0f9ec76d1ee@cert.invalid 	 21/10/2026 00:01:21 	 CERT-6576a4cc765d (2) 	 $23.800 	 Pendiente	 Sin Boleta Pendiente	 Vence (Cobrar): 21/10/2026 	 CA CERT Administrador |
| UI-inventario-2 | inventario | PASS |                  CERT-6576a4cc765d                                                               CERT-6576a4cc765d                                                                                General                                                                                                                             Principal(12)                                                                                                                                                                  |
| UI-produccion-2 | produccion | PASS | OT-09085 |
| UI-cxc-2 | cxc | PASS |  2026-10-21	Hoy	 P-04188 BOL-00557 / 2026-10-21 	 CERT-d0f9ec76d1ee 	$23,800	$0	$23,800	⏳ Pendiente	Sin gestión	Sin gestión	—	 Gestión (0) Cobrar |
| UI-cxp-2 | cxp | PASS | CERT-73fe3602c667 |
| UI-gastos-2 | gastos | PASS | CERT-3c2d49fe1f81 |
| UI-bancos-2 | bancos | PASS | CERT-4f19b6e8f7e2 |
| UI-flujo_caja-2 | flujo_caja | PASS | {'initial': 0, 'inflows': 0, 'outflows': 24276, 'final': -24276} |
| UI-reportes-2 | reportes | PASS | 3221294355 |
| UI-productos-3 | productos | PASS | CERT-d8bf6c8a1a89	CERT-d8bf6c8a1a89	Producto Terminado	General	-	-	-	-	-	UN	-	-	No (Opc.)	0	Activo	-	 |
| UI-proveedores-3 | proveedores | PASS | CERT-b2c71cb23dda |
| UI-ordenes_compra-3 | ordenes_compra | PASS | OC-05708 |
| UI-recepcion-3 | recepcion | PASS | CERT-17b6d82563a2 |
| UI-cotizaciones-3 | cotizaciones | PASS | {'neto': 27000, 'iva': 5130, 'total': 32130} |
| UI-ventas-3 | ventas | PASS | 	P-04191	 C CERT-4ffcf1db302e CERT-4ffcf1db302e@cert.invalid 	 21/10/2026 00:01:22 	 CERT-d8bf6c8a1a89 (3) 	 $35.700 	 Pendiente	 Sin Boleta Pendiente	 Vence (Cobrar): 21/10/2026 	 CA CERT Administrador |
| UI-inventario-3 | inventario | PASS |                  CERT-d8bf6c8a1a89                                                               CERT-d8bf6c8a1a89                                                                                General                                                                                                                             Principal(13)                                                                                                                                                                  |
| UI-produccion-3 | produccion | PASS | OT-09086 |
| UI-cxc-3 | cxc | PASS |  2026-10-21	Hoy	 P-04191 BOL-00560 / 2026-10-21 	 CERT-4ffcf1db302e 	$35,700	$0	$35,700	⏳ Pendiente	Sin gestión	Sin gestión	—	 Gestión (0) Cobrar |
| UI-cxp-3 | cxp | PASS | CERT-1e4251aa355c |
| UI-gastos-3 | gastos | PASS | CERT-f356a6b64f24 |
| UI-bancos-3 | bancos | PASS | CERT-7225fd46521c |
| UI-flujo_caja-3 | flujo_caja | PASS | {'initial': 0, 'inflows': 0, 'outflows': 24514, 'final': -24514} |
| UI-reportes-3 | reportes | PASS | 3221294355 |
| UI-productos-4 | productos | PASS | CERT-27fcfeea327b	CERT-27fcfeea327b	Producto Terminado	General	-	-	-	-	-	UN	-	-	No (Opc.)	0	Activo	-	 |
| UI-proveedores-4 | proveedores | PASS | CERT-6a6e066c375a |
| UI-ordenes_compra-4 | ordenes_compra | PASS | OC-05709 |
| UI-recepcion-4 | recepcion | PASS | CERT-02f203f48730 |
| UI-cotizaciones-4 | cotizaciones | PASS | {'neto': 27000, 'iva': 5130, 'total': 32130} |
| UI-ventas-4 | ventas | PASS | 	P-04194	 C CERT-0e1ad5689282 CERT-0e1ad5689282@cert.invalid 	 21/10/2026 00:01:23 	 CERT-27fcfeea327b (4) 	 $47.600 	 Pendiente	 Sin Boleta Pendiente	 Vence (Cobrar): 21/10/2026 	 CA CERT Administrador |
| UI-inventario-4 | inventario | PASS |                  CERT-27fcfeea327b                                                               CERT-27fcfeea327b                                                                                General                                                                                                                             Principal(14)                                                                                                                                                                  |
| UI-produccion-4 | produccion | PASS | OT-09087 |
| UI-cxc-4 | cxc | PASS |  2026-10-21	Hoy	 P-04194 BOL-00563 / 2026-10-21 	 CERT-0e1ad5689282 	$47,600	$0	$47,600	⏳ Pendiente	Sin gestión	Sin gestión	—	 Gestión (0) Cobrar |
| UI-cxp-4 | cxp | PASS | CERT-edaf988def32 |
| UI-gastos-4 | gastos | PASS | CERT-eef58219e4aa |
| UI-bancos-4 | bancos | PASS | CERT-00ecf8ae411d |
| UI-flujo_caja-4 | flujo_caja | PASS | {'initial': 0, 'inflows': 0, 'outflows': 24752, 'final': -24752} |
| UI-reportes-4 | reportes | PASS | 3221294355 |
| UI-productos-5 | productos | PASS | CERT-7286074e052e	CERT-7286074e052e	Producto Terminado	General	-	-	-	-	-	UN	-	-	No (Opc.)	0	Activo	-	 |
| UI-proveedores-5 | proveedores | PASS | CERT-02c762033219 |
| UI-ordenes_compra-5 | ordenes_compra | PASS | OC-05710 |
| UI-recepcion-5 | recepcion | PASS | CERT-6b1f1ccd00fd |
| UI-cotizaciones-5 | cotizaciones | PASS | {'neto': 27000, 'iva': 5130, 'total': 32130} |
| UI-ventas-5 | ventas | PASS | 	P-04197	 C CERT-780d43892d0b CERT-780d43892d0b@cert.invalid 	 21/10/2026 00:01:25 	 CERT-7286074e052e (5) 	 $59.500 	 Pendiente	 Sin Boleta Pendiente	 Vence (Cobrar): 21/10/2026 	 CA CERT Administrador |
| UI-inventario-5 | inventario | PASS |                  CERT-7286074e052e                                                               CERT-7286074e052e                                                                                General                                                                                                                             Principal(15)                                                                                                                                                                  |
| UI-produccion-5 | produccion | PASS | OT-09088 |
| UI-cxc-5 | cxc | PASS |  2026-10-21	Hoy	 P-04197 BOL-00566 / 2026-10-21 	 CERT-780d43892d0b 	$59,500	$0	$59,500	⏳ Pendiente	Sin gestión	Sin gestión	—	 Gestión (0) Cobrar |
| UI-cxp-5 | cxp | PASS | CERT-3ef243486f66 |
| UI-gastos-5 | gastos | PASS | CERT-7c9928c34b1a |
| UI-bancos-5 | bancos | PASS | CERT-dcdf21464b05 |
| UI-flujo_caja-5 | flujo_caja | PASS | {'initial': 0, 'inflows': 0, 'outflows': 24990, 'final': -24990} |
| UI-reportes-5 | reportes | PASS | 3221294355 |
| UI-FORM-COT-1 | cotizaciones | PASS | {'neto': '$27.000', 'iva': '$5.130', 'total': '$32.130'} |
| UI-FORM-COT-2 | cotizaciones | PASS | {'neto': '$7.346', 'iva': '$1.396', 'total': '$8.742'} |
| UI-FORM-COT-3 | cotizaciones | PASS | {'neto': '$50', 'iva': '$10', 'total': '$60'} |
| UI-FORM-COT-4 | cotizaciones | PASS | {'neto': '$0', 'iva': '$0', 'total': '$0'} |
| UI-FORM-COT-5 | cotizaciones | PASS | {'neto': '$2.700.000.000', 'iva': '$513.000.000', 'total': '$3.213.000.000'} |
| UI-clientes-1 | clientes | PASS | CERT Cliente Ficticio 01 |
| UI-ppp_fifo-1 | ppp_fifo | PASS | {'target': 'CERT-5991e7ddea66', 'currency_values': [1100, 22000, 22000, 1100, 22000, 1100]} |
| UI-despacho-1 | despacho | PASS | {'neto': '$3.000', 'prod-cost': '$2.000', 'pkg-cost': '$100', 'total-cost': '$2.100', 'margin-val': '$900'} |
| UI-recetas-1 | recetas | PASS | CERT-fdd609fffd52 |
| UI-deudas-1 | deudas | PASS | CERT-cd64a892f45e |
| UI-conciliacion-1 | conciliacion | PASS | 2026-10-20	 CERT-c310f1e128c2 N° CERT-c310f1e128c2 	 CERT-e75bdb5729aa 	-	-	$11,901	-	 -- Sin Categoría -- CERT Transferencia CERT Egreso CERT Ingreso 	 PENDIENTE	  Conciliar |
| UI-seguridad-1 | seguridad | PASS | {'http': 403, 'body': 'Plataforma de Gestión\nUsuario\nCERT Sin Permisos\nAcceso Restringido\n🔍\nSalir\nAcceso denegado: no dispone de permisos suficientes para realizar esta acción.\nAcceso Denegado (Error 403)\n\nSu perfil de usuario (CERT Sin Permisos) no cuenta con los permisos necesarios para acceder a este recurso.\nPermiso requerido: usuarios\n\nIr al Dashboard\nVolver'} |
| UI-ajustes-1 | ajustes | PASS | CERT-5991e7ddea66 |
| UI-embalajes-1 | embalajes | PASS | {'neto': '$3.000', 'prod-cost': '$2.000', 'pkg-cost': '$100', 'total-cost': '$2.100', 'margin-val': '$900'} |
| UI-trazabilidad-1 | trazabilidad | PASS | CERT-1fbb32957d4e |
| UI-operario-1 | operario | PASS | OT-08965 |
| UI-agenda-1 | agenda | PASS | OT-08965 |
| UI-excel_productos-1 | excel_productos | PASS | {'rows': 2} |
| UI-excel_deudas-1 | excel_deudas | PASS | {'rows': 8} |
| UI-usuarios_roles-1 | usuarios_roles | PASS | Administrativo |
| UI-informacion_empresa-1 | informacion_empresa | PASS | {'loaded': True, 'width': 21} |
| UI-clientes-2 | clientes | PASS | CERT Cliente Ficticio 02 |
| UI-ppp_fifo-2 | ppp_fifo | PASS | {'target': 'CERT-ab43547d001a', 'currency_values': [1200, 24000, 24000, 1200, 24000, 1200]} |
| UI-despacho-2 | despacho | PASS | {'neto': '$6.000', 'prod-cost': '$4.000', 'pkg-cost': '$200', 'total-cost': '$4.200', 'margin-val': '$1.800'} |
| UI-recetas-2 | recetas | PASS | CERT-05aceeabfa37 |
| UI-deudas-2 | deudas | PASS | CERT-3590940d4fc9 |
| UI-conciliacion-2 | conciliacion | PASS | 2026-10-20	 CERT-1b777dc6ce4f N° CERT-1b777dc6ce4f 	 CERT-d10fee1d0274 	-	-	$11,902	-	 -- Sin Categoría -- CERT Transferencia CERT Egreso CERT Ingreso 	 PENDIENTE	  Conciliar |
| UI-seguridad-2 | seguridad | PASS | {'http': 403, 'body': 'Plataforma de Gestión\nUsuario\nCERT Sin Permisos\nAcceso Restringido\n🔍\nSalir\nAcceso denegado: no dispone de permisos suficientes para realizar esta acción.\nAcceso Denegado (Error 403)\n\nSu perfil de usuario (CERT Sin Permisos) no cuenta con los permisos necesarios para acceder a este recurso.\nPermiso requerido: usuarios\n\nIr al Dashboard\nVolver'} |
| UI-ajustes-2 | ajustes | PASS | CERT-ab43547d001a |
| UI-embalajes-2 | embalajes | PASS | {'neto': '$6.000', 'prod-cost': '$4.000', 'pkg-cost': '$200', 'total-cost': '$4.200', 'margin-val': '$1.800'} |
| UI-trazabilidad-2 | trazabilidad | PASS | CERT-36d7618ed373 |
| UI-operario-2 | operario | PASS | OT-08966 |
| UI-agenda-2 | agenda | PASS | OT-08966 |
| UI-excel_productos-2 | excel_productos | PASS | {'rows': 2} |
| UI-excel_deudas-2 | excel_deudas | PASS | {'rows': 8} |
| UI-usuarios_roles-2 | usuarios_roles | PASS | Administrativo |
| UI-informacion_empresa-2 | informacion_empresa | PASS | {'loaded': True, 'width': 22} |
| UI-clientes-3 | clientes | PASS | CERT Cliente Ficticio 03 |
| UI-ppp_fifo-3 | ppp_fifo | PASS | {'target': 'CERT-96e3c00eb6d8', 'currency_values': [1300, 26000, 26000, 1300, 26000, 1300]} |
| UI-despacho-3 | despacho | PASS | {'neto': '$9.000', 'prod-cost': '$6.000', 'pkg-cost': '$300', 'total-cost': '$6.300', 'margin-val': '$2.700'} |
| UI-recetas-3 | recetas | PASS | CERT-2470cc454a54 |
| UI-deudas-3 | deudas | PASS | CERT-400a96b39206 |
| UI-conciliacion-3 | conciliacion | PASS | 2026-10-20	 CERT-07985bcdab38 N° CERT-07985bcdab38 	 CERT-dd3e70d746aa 	-	-	$11,903	-	 -- Sin Categoría -- CERT Transferencia CERT Egreso CERT Ingreso 	 PENDIENTE	  Conciliar |
| UI-seguridad-3 | seguridad | PASS | {'http': 403, 'body': 'Plataforma de Gestión\nUsuario\nCERT Sin Permisos\nAcceso Restringido\n🔍\nSalir\nAcceso denegado: no dispone de permisos suficientes para realizar esta acción.\nAcceso Denegado (Error 403)\n\nSu perfil de usuario (CERT Sin Permisos) no cuenta con los permisos necesarios para acceder a este recurso.\nPermiso requerido: administracion\n\nIr al Dashboard\nVolver'} |
| UI-ajustes-3 | ajustes | PASS | CERT-96e3c00eb6d8 |
| UI-embalajes-3 | embalajes | PASS | {'neto': '$9.000', 'prod-cost': '$6.000', 'pkg-cost': '$300', 'total-cost': '$6.300', 'margin-val': '$2.700'} |
| UI-trazabilidad-3 | trazabilidad | PASS | CERT-143da8aa08c7 |
| UI-operario-3 | operario | PASS | OT-08967 |
| UI-agenda-3 | agenda | PASS | OT-08967 |
| UI-excel_productos-3 | excel_productos | PASS | {'rows': 2} |
| UI-excel_deudas-3 | excel_deudas | PASS | {'rows': 8} |
| UI-usuarios_roles-3 | usuarios_roles | PASS | Administrativo |
| UI-informacion_empresa-3 | informacion_empresa | PASS | {'loaded': True, 'width': 23} |
| UI-clientes-4 | clientes | PASS | CERT Cliente Ficticio 04 |
| UI-ppp_fifo-4 | ppp_fifo | PASS | {'target': 'CERT-0b116127c58d', 'currency_values': [1400, 28000, 28000, 1400, 28000, 1400]} |
| UI-despacho-4 | despacho | PASS | {'neto': '$12.000', 'prod-cost': '$8.000', 'pkg-cost': '$400', 'total-cost': '$8.400', 'margin-val': '$3.600'} |
| UI-recetas-4 | recetas | PASS | CERT-1bdb27543461 |
| UI-deudas-4 | deudas | PASS | CERT-d560c545b1e5 |
| UI-conciliacion-4 | conciliacion | PASS | 2026-10-20	 CERT-775b99008717 N° CERT-775b99008717 	 CERT-04b9ea583d59 	-	-	$11,904	-	 -- Sin Categoría -- CERT Transferencia CERT Egreso CERT Ingreso 	 PENDIENTE	  Conciliar |
| UI-seguridad-4 | seguridad | PASS | {'http': 403, 'body': 'Plataforma de Gestión\nUsuario\nCERT Sin Permisos\nAcceso Restringido\n🔍\nSalir\nAcceso denegado: no dispone de permisos suficientes para realizar esta acción.\nAcceso Denegado (Error 403)\n\nSu perfil de usuario (CERT Sin Permisos) no cuenta con los permisos necesarios para acceder a este recurso.\nPermiso requerido: administracion\n\nIr al Dashboard\nVolver'} |
| UI-ajustes-4 | ajustes | PASS | CERT-0b116127c58d |
| UI-embalajes-4 | embalajes | PASS | {'neto': '$12.000', 'prod-cost': '$8.000', 'pkg-cost': '$400', 'total-cost': '$8.400', 'margin-val': '$3.600'} |
| UI-trazabilidad-4 | trazabilidad | PASS | CERT-fc695f4c3df8 |
| UI-operario-4 | operario | PASS | OT-08968 |
| UI-agenda-4 | agenda | PASS | OT-08968 |
| UI-excel_productos-4 | excel_productos | PASS | {'rows': 2} |
| UI-excel_deudas-4 | excel_deudas | PASS | {'rows': 8} |
| UI-usuarios_roles-4 | usuarios_roles | PASS | Administrativo |
| UI-informacion_empresa-4 | informacion_empresa | PASS | {'loaded': True, 'width': 24} |
| UI-clientes-5 | clientes | PASS | CERT Cliente Ficticio 05 |
| UI-ppp_fifo-5 | ppp_fifo | PASS | {'target': 'CERT-c0f952dec546', 'currency_values': [1500, 30000, 30000, 1500, 30000, 1500]} |
| UI-despacho-5 | despacho | PASS | {'neto': '$15.000', 'prod-cost': '$10.000', 'pkg-cost': '$500', 'total-cost': '$10.500', 'margin-val': '$4.500'} |
| UI-recetas-5 | recetas | PASS | CERT-96b344519334 |
| UI-deudas-5 | deudas | PASS | CERT-7249731c7f36 |
| UI-conciliacion-5 | conciliacion | PASS | 2026-10-20	 CERT-309e20187001 N° CERT-309e20187001 	 CERT-3fd2976927da 	-	-	$11,905	-	 -- Sin Categoría -- CERT Transferencia CERT Egreso CERT Ingreso 	 PENDIENTE	  Conciliar |
| UI-seguridad-5 | seguridad | PASS | {'http': 403, 'body': 'Plataforma de Gestión\nUsuario\nCERT Sin Permisos\nAcceso Restringido\n🔍\nSalir\nAcceso denegado: no dispone de permisos suficientes para realizar esta acción.\nAcceso Denegado (Error 403)\n\nSu perfil de usuario (CERT Sin Permisos) no cuenta con los permisos necesarios para acceder a este recurso.\nPermiso requerido: inventario\n\nIr al Dashboard\nVolver'} |
| UI-ajustes-5 | ajustes | PASS | CERT-c0f952dec546 |
| UI-embalajes-5 | embalajes | PASS | {'neto': '$15.000', 'prod-cost': '$10.000', 'pkg-cost': '$500', 'total-cost': '$10.500', 'margin-val': '$4.500'} |
| UI-trazabilidad-5 | trazabilidad | PASS | CERT-8a7ed62af721 |
| UI-operario-5 | operario | PASS | OT-08969 |
| UI-excel_productos-5 | excel_productos | PASS | {'rows': 2} |
| UI-excel_deudas-5 | excel_deudas | PASS | {'rows': 8} |
| UI-usuarios_roles-5 | usuarios_roles | PASS | Administrativo |
| UI-informacion_empresa-5 | informacion_empresa | PASS | {'loaded': True, 'width': 25} |
| UI-precios-1 | precios | PASS | {'target': 'CERT-a14a79718389', 'currency_values': [2000, 2800, 2300]} |
| UI-excel_bancos-1 | excel_bancos | PASS | {'rows': 2} |
| UI-precios-2 | precios | PASS | {'target': 'CERT-63345aa7b8e2', 'currency_values': [2000, 2800, 2300]} |
| UI-excel_bancos-2 | excel_bancos | PASS | {'rows': 2} |
| UI-precios-3 | precios | PASS | {'target': 'CERT-27176d40aaa8', 'currency_values': [2000, 2800, 2300]} |
| UI-excel_bancos-3 | excel_bancos | PASS | {'rows': 2} |
| UI-precios-4 | precios | PASS | {'target': 'CERT-7ace3c8aa73e', 'currency_values': [2000, 2800, 2300]} |
| UI-excel_bancos-4 | excel_bancos | PASS | {'rows': 2} |
| UI-precios-5 | precios | PASS | {'target': 'CERT-c78ca8905a42', 'currency_values': [2000, 2800, 2300]} |
| UI-agenda-5 | agenda | PASS | OT-08969 |
| UI-excel_bancos-5 | excel_bancos | PASS | {'rows': 2} |

Se prueban cinco formularios interactivos de cotización con persistencia y cinco visualizaciones por pantalla cubierta. Las demás comprobaciones de pantalla son lecturas/contrastes, no cinco altas interactivas completas de cada módulo. Esa limitación mantiene módulos YELLOW y no se sustituye con un PASS de API. Las capturas, PDF y manifiesto identifican los datos sintéticos.
