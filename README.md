# Proyecto 1 · Plataforma de Distribución de Mercancías Perecederas

[![CI](https://github.com/mario-perez30/Proyecto-1-Plataforma-de-Distribucion-de-Mercancias-Perecederas/actions/workflows/ci.yml/badge.svg)](https://github.com/mario-perez30/Proyecto-1-Plataforma-de-Distribucion-de-Mercancias-Perecederas/actions/workflows/ci.yml)

Prototipo de IA que calcula las rutas de reparto de **IA DELIVERY SL** desde Mataró (Barcelona) y la **flota mínima de camiones propios** necesaria para dejar de externalizar el transporte de sus productos perecederos a España, Portugal y Andorra.

Proyecto del Máster de FP en Inteligencia Artificial y Big Data (Stucom).

**Equipo:** Mario ([@mario-perez30](https://github.com/mario-perez30)), Olalla Sánchez Bernad y Yixin Huang.

## Estado

| Parte | Estado |
| --- | --- |
| Base de datos `BDIADelivery` (datos, costes, flota, reglas, vistas) | Hecha y validada en CI |
| Optimizador de rutas (OR-Tools y Clarke-Wright) y flota mínima | Hecho y probado en CI |
| Interfaz con mapa de rutas (Streamlit) | Hecha |
| Documentación (memoria) | En curso |

## Estructura

```
database/
  01_crear_base_datos.sql        Crea la BD y carga los datos originales
  02_mejoras_costes_flota.sql    Costes, flota, cadena de frío, escenarios, resultados, funciones y vistas
  03_corregir_coordenadas.sql    Coordenadas realistas para los 1.500 destinos
  04_fechas_caducidad.sql        Fechas de fabricación y caducidad y totales de cada pedido, con triggers
  original/script_sqlserver.sql  Export original de SQL Server (UTF-16), fuente de los scripts
  tests/verificar.sql            Comprobaciones de datos, vistas y costes
  tests/probar_triggers.sql      Prueba de los triggers (se deshace con ROLLBACK)
tools/                           Scripts de Python que generan y validan los SQL
analysis/                        Resultados de análisis (CSV y mapas)
docs/                            Documentación del proyecto
.github/                         Pipeline de CI y plantillas de issues y pull requests
```

## Instalar la base de datos

Requisitos: MySQL 8.0, MySQL 5.7 o MariaDB 10.4 o superior, y MySQL Workbench (o el cliente `mysql`).

En MySQL Workbench, abre y ejecuta **en este orden** cada script con el rayo (*Execute*):

1. `database/01_crear_base_datos.sql`. Borra y vuelve a crear `BDIADelivery`.
2. `database/02_mejoras_costes_flota.sql`
3. `database/03_corregir_coordenadas.sql`
4. `database/04_fechas_caducidad.sql`

Desde la línea de comandos:

```bash
for f in database/0*.sql; do mysql -u root -p < "$f"; done
mysql -u root -p -N BDIADelivery < database/tests/verificar.sql        # todas las filas deben acabar en 1
mysql -u root -p -N BDIADelivery < database/tests/probar_triggers.sql  # ídem
```

### Fechas de caducidad

`Pedidos` guarda, calculadas a partir de sus líneas y productos, las columnas `FechaInicioFabricacion`, `FechaListoEnvio`, `FechaCaducidad`, `FechaLimiteEntrega` (caducidad menos el margen de seguridad) y `HorasDisponiblesReparto`, además de `NumLineas`, `UnidadesTotales` e `ImporteTotal`. Los triggers las recalculan al cambiar las líneas o la fecha del pedido. Si cambias los parámetros de caducidad en `ParametrosSistema`, ejecuta `CALL sp_RecalcularFechasPedidos(NULL);`. La vista `vw_LineasPedidoCaducidad` muestra la caducidad de cada línea y cuál limita el pedido.

## Optimizador de rutas

Paquete `optimizador/` en Python. Lee un escenario de la BD, calcula las rutas y la flota mínima y guarda el resultado en `Planificaciones`, `Rutas` y `ParadasRuta`.

| Algoritmo | Qué hace |
| --- | --- |
| `directo` | Un camión por pedido (línea base) |
| `clarke-wright` | Heurística de ahorros de Clarke-Wright |
| `ortools` | Google OR-Tools: rutas con capacidad y plazos + Guided Local Search |

Después, los viajes se asignan a camiones (un camión puede hacer varios viajes si llega a tiempo). Los horarios respetan el Reglamento (CE) 561/2006: pausa de 45 min cada 4,5 h y descanso de 11 h tras 9 h de conducción.

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
.venv/Scripts/python -m optimizador --algoritmo todos --tipo 1           # compara los tres y los guarda
.venv/Scripts/python -m optimizador --algoritmo ortools --segundos 60 --no-guardar
.venv/Scripts/python -m pytest -q                                         # tests
```

La conexión usa las variables `BDIA_HOST`, `BDIA_PORT`, `BDIA_USER`, `BDIA_PASSWORD` y `BDIA_DB`. Por defecto, MySQL de XAMPP en local con `root` sin contraseña.

## Interfaz (Streamlit)

```bash
.venv/Scripts/streamlit run app.py      # abre http://localhost:8501
```

| Pestaña | Qué hace |
| --- | --- |
| Planificar | Elige escenario, camión y algoritmo; calcula las rutas, muestra camiones, viajes, km, coste, ahorro frente a externalizar y CO2, el mapa y la tabla de viajes; opcionalmente lo guarda |
| Planificaciones | Compara todas las planificaciones guardadas (tabla y gráficos) y muestra el mapa de cualquiera |
| Pedidos | Pedidos con sus fechas de fabricación, caducidad, límite de entrega y horas de reparto |
| Parámetros | Coste por km de cada camión, parámetros del sistema y precios de combustible |

## Regenerar los scripts

Los SQL de `database/` se generan desde el export original con los scripts de `tools/`. El pipeline comprueba que se regeneran idénticos.

```bash
pip install -r requirements.txt
python tools/convertir_sqlserver_a_mysql.py database/original/script_sqlserver.sql database/01_crear_base_datos.sql
python tools/generar_coordenadas.py database/original/script_sqlserver.sql database/03_corregir_coordenadas.sql analysis/mapa_destinos_corregido.png
python tools/simular_envio_directo.py database/original/script_sqlserver.sql database/03_corregir_coordenadas.sql
```

## Integración continua

Cada push a `main` y cada pull request ejecuta [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

- **Python:** análisis estático con `ruff`, tests del optimizador con `pytest` y comprobación de que `01` y `03` se regeneran idénticos.
- **Base de datos:** crea la BD con todos los scripts `database/0*.sql` en MySQL 8.0, MySQL 5.7, MariaDB 10.4 y MariaDB 11.4, y ejecuta las pruebas de `database/tests/` (número de filas, coordenadas, caducidad, costes de la línea base y triggers). Después ejecuta el optimizador contra esa BD y comprueba que la planificación guardada cubre los 133 pedidos sin ninguno fuera de plazo.

## Cómo contribuir

`main` está protegida: todos los cambios entran por rama y pull request con el pipeline en verde. Consulta [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentación

La memoria del proyecto se redacta en un documento compartido del equipo y se exporta a `docs/` en cada entrega. Los enunciados del máster no se publican en este repositorio.
