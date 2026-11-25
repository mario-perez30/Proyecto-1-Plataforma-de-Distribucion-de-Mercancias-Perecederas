"""Genera database/03_corregir_coordenadas.sql: coordenadas realistas para los 1.500 destinos.

Uso: python tools/generar_coordenadas.py database/original/script_sqlserver.sql \n         database/03_corregir_coordenadas.sql analysis/mapa_destinos_corregido.png

- España: se mantiene IdProvincia; el destino se sitúa alrededor de la capital de su provincia.
- Portugal: se reparten entre los 18 distritos continentales (nuevas filas en Provincias, IdPais='PT').
- Andorra: se reparten entre las 7 parroquias (IdPais='AD').
Reproducible (semilla fija). Comprueba que cada punto cae en tierra y en el país correcto.
"""
import re, math, random, sys, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path

src, out_sql, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
t = open(src, encoding="utf-16").read()
rnd = random.Random(2026)

# (nombre provincia BD, ciudad capital, lat, lon, prefijo CP INE)
ES = [("Álava","Vitoria-Gasteiz",42.8467,-2.6716,"01"),("Albacete","Albacete",38.9943,-1.8585,"02"),
("Alicante","Alicante",38.3452,-0.4810,"03"),("Almería","Almería",36.8340,-2.4637,"04"),
("Asturias","Oviedo",43.3614,-5.8494,"33"),("Ávila","Ávila",40.6566,-4.6818,"05"),
("Badajoz","Badajoz",38.8794,-6.9707,"06"),("Barcelona","Barcelona",41.3874,2.1686,"08"),
("Burgos","Burgos",42.3439,-3.6969,"09"),("Cáceres","Cáceres",39.4753,-6.3724,"10"),
("Cádiz","Cádiz",36.5271,-6.2886,"11"),("Cantabria","Santander",43.4623,-3.8100,"39"),
("Castellón","Castellón de la Plana",39.9864,-0.0513,"12"),("Ciudad Real","Ciudad Real",38.9848,-3.9274,"13"),
("Córdoba","Córdoba",37.8882,-4.7794,"14"),("A Coruña","A Coruña",43.3623,-8.4115,"15"),
("Cuenca","Cuenca",40.0704,-2.1374,"16"),("Girona","Girona",41.9794,2.8214,"17"),
("Granada","Granada",37.1773,-3.5986,"18"),("Guadalajara","Guadalajara",40.6329,-3.1669,"19"),
("Guipúzcoa","Donostia-San Sebastián",43.3183,-1.9812,"20"),("Huelva","Huelva",37.2614,-6.9447,"21"),
("Huesca","Huesca",42.1401,-0.4089,"22"),("Jaén","Jaén",37.7796,-3.7849,"23"),
("León","León",42.5987,-5.5671,"24"),("Lleida","Lleida",41.6176,0.6200,"25"),
("Lugo","Lugo",43.0097,-7.5568,"27"),("Madrid","Madrid",40.4168,-3.7038,"28"),
("Málaga","Málaga",36.7213,-4.4214,"29"),("Murcia","Murcia",37.9922,-1.1307,"30"),
("Navarra","Pamplona",42.8125,-1.6458,"31"),("Ourense","Ourense",42.3358,-7.8639,"32"),
("Palencia","Palencia",42.0095,-4.5288,"34"),("Pontevedra","Pontevedra",42.4310,-8.6444,"36"),
("La Rioja","Logroño",42.4627,-2.4450,"26"),("Salamanca","Salamanca",40.9701,-5.6635,"37"),
("Segovia","Segovia",40.9429,-4.1088,"40"),("Sevilla","Sevilla",37.3891,-5.9845,"41"),
("Soria","Soria",41.7666,-2.4790,"42"),("Tarragona","Tarragona",41.1189,1.2445,"43"),
("Teruel","Teruel",40.3456,-1.1065,"44"),("Toledo","Toledo",39.8628,-4.0273,"45"),
("Valencia","Valencia",39.4699,-0.3763,"46"),("Valladolid","Valladolid",41.6523,-4.7245,"47"),
("Vizcaya","Bilbao",43.2630,-2.9350,"48"),("Zamora","Zamora",41.5035,-5.7446,"49"),
("Zaragoza","Zaragoza",41.6488,-0.8891,"50")]
# Distritos de Portugal continental (capital = mismo nombre): (nombre, lat, lon, prefijo CP)
PT = [("Aveiro",40.6405,-8.6538,"3800"),("Beja",38.0151,-7.8632,"7800"),("Braga",41.5454,-8.4265,"4700"),
("Bragança",41.8061,-6.7567,"5300"),("Castelo Branco",39.8222,-7.4909,"6000"),("Coimbra",40.2033,-8.4103,"3000"),
("Évora",38.5714,-7.9135,"7000"),("Faro",37.0194,-7.9322,"8000"),("Guarda",40.5373,-7.2658,"6300"),
("Leiria",39.7436,-8.8071,"2400"),("Lisboa",38.7223,-9.1393,"1000"),("Portalegre",39.2967,-7.4285,"7300"),
("Porto",41.1579,-8.6291,"4000"),("Santarém",39.2362,-8.6859,"2000"),("Setúbal",38.5244,-8.8882,"2900"),
("Viana do Castelo",41.6932,-8.8329,"4900"),("Vila Real",41.3006,-7.7441,"5000"),("Viseu",40.6566,-7.9125,"3500")]
# Parroquias de Andorra: (nombre, lat, lon, código postal)
AD = [("Canillo",42.5671,1.5978,"AD100"),("Encamp",42.5347,1.5801,"AD200"),("Ordino",42.5563,1.5332,"AD300"),
("La Massana",42.5450,1.5149,"AD400"),("Andorra la Vella",42.5063,1.5218,"AD500"),
("Sant Julià de Lòria",42.4637,1.4913,"AD600"),("Escaldes-Engordany",42.5092,1.5389,"AD700")]

# Contorno aproximado de la península (lat, lon), afinado en costas con capitales
IBERIA = [(42.32,3.32),(42.43,3.17),(42.6,1.7),(42.8,0.7),(42.7,-0.3),(43.05,-1.4),(43.37,-1.79),(43.45,-3.0),
(43.47,-3.8),(43.56,-5.7),(43.6,-7.0),(43.79,-7.7),(43.55,-8.3),(43.2,-9.3),(42.4,-8.95),(41.87,-8.88),
(41.69,-8.87),(41.15,-8.69),(40.2,-8.9),(39.35,-9.4),(38.7,-9.5),(38.4,-8.8),(37.95,-8.87),(37.0,-8.95),
(37.08,-8.2),(36.97,-7.93),(37.17,-7.4),(37.15,-6.95),(36.78,-6.42),(36.45,-6.32),(36.18,-6.04),(36.0,-5.6),
(36.15,-5.35),(36.7,-4.4),(36.7,-3.0),(36.75,-2.1),(37.6,-0.7),(38.0,-0.65),(38.33,-0.45),(38.75,0.2),
(39.45,-0.3),(39.98,0.02),(40.7,0.85),(41.1,1.3),(41.37,2.2),(41.7,2.85),(42.0,3.2)]
BORDER_PT = [(41.87,-8.88),(42.05,-8.2),(41.95,-7.2),(41.97,-6.6),(41.6,-6.2),(41.0,-6.9),(40.35,-6.85),
(39.65,-7.53),(39.0,-7.0),(38.2,-7.3),(37.17,-7.4)]
PORTUGAL = BORDER_PT + [(36.97,-7.93),(37.08,-8.2),(37.0,-8.95),(37.95,-8.87),(38.4,-8.8),(38.7,-9.5),
(39.35,-9.4),(40.2,-8.9),(41.15,-8.69),(41.69,-8.87)]
iberia = Path([(lo, la) for la, lo in IBERIA]); portugal = Path([(lo, la) for la, lo in PORTUGAL])

def pais_de(lat, lon):
    if 42.43 <= lat <= 42.66 and 1.41 <= lon <= 1.79: return "AD"
    if not iberia.contains_point((lon, lat)): return "MAR"
    return "PT" if portugal.contains_point((lon, lat)) else "ES"

# Todas las capitales deben caer en su país con este contorno
for e in ES: assert pais_de(e[2], e[3]) == "ES", e
for p in PT: assert pais_de(p[1], p[2]) == "PT", p
for a in AD: assert pais_de(a[1], a[2]) == "AD", a

def km(a, b, c, d):
    r = math.radians
    x = math.sin(r(c-a)/2)**2 + math.cos(r(a))*math.cos(r(c))*math.sin(r(d-b)/2)**2
    return 6371.0088*2*math.atan2(math.sqrt(x), math.sqrt(1-x))

def jitter(lat, lon, rmax, pais):
    """Punto aleatorio a <= rmax km del centro, en tierra y en el país pedido."""
    for _ in range(5000):
        r = rmax * math.sqrt(rnd.random()); a = rnd.random() * 2 * math.pi
        nlat = lat + (r * math.cos(a)) / 111.32
        nlon = lon + (r * math.sin(a)) / (111.32 * math.cos(math.radians(lat)))
        if pais_de(nlat, nlon) == pais: return round(nlat, 7), round(nlon, 7)
    raise RuntimeError((lat, lon, pais))

names_db = [n for _, n in re.findall(r"\[Provincias\].*VALUES \((\d+), N'([^']*)'", t)]
assert [e[0] for e in ES] == names_db
dest = re.findall(r"\[Destinos\].*VALUES \((\d+), N'[^']*', N'[^']*', (\d+|NULL), N'([^']*)'", t)

new_prov = [(48 + i, p[0], "PT") for i, p in enumerate(PT)] + [(66 + i, p[0], "AD") for i, p in enumerate(AD)]
out = []; first = set(); cnt = collections.Counter(); n_pt = n_ad = 0
for sid, sprov, pais in dest:
    i = int(sid)
    if pais == "España":
        p = int(sprov); _, ciudad, lat, lon, cp = ES[p - 1]
        rmax = 25 if p in first else 3; first.add(p)          # el 1º de cada provincia, junto a la capital
        la, lo = jitter(lat, lon, rmax, "ES"); cpost = cp + f"{rnd.randint(0, 999):03d}"
    elif pais == "Portugal":
        k = n_pt % len(PT); ciudad, lat, lon, cp = PT[k]; p = 48 + k
        la, lo = jitter(lat, lon, 3 if n_pt < len(PT) else 15, "PT"); n_pt += 1
        cpost = f"{cp}-{rnd.randint(1, 999):03d}"
    else:
        k = n_ad % len(AD); ciudad, lat, lon, cp = AD[k]; p = 66 + k
        la, lo = jitter(lat, lon, 2, "AD"); n_ad += 1; cpost = cp
    cnt[pais] += 1
    out.append((i, p, ciudad, cpost, la, lo, pais, km(la, lo, lat, lon)))

def q(s): return "'" + s.replace("'", "''") + "'"
L = []
L.append("""-- =====================================================================
-- BDIADelivery - CORRECCIÓN DE COORDENADAS DE LOS DESTINOS
-- Ejecutar DESPUÉS de 01_crear_base_datos.sql y 02_mejoras_costes_flota.sql.
--
-- Las coordenadas originales eran aleatorias (lat 36-43, lon -8..2): muchas en
-- el mar y lejos de su provincia. Este script:
--   * añade los 18 distritos de Portugal y las 7 parroquias de Andorra a Provincias
--   * sitúa cada destino alrededor de la capital de su provincia/distrito/parroquia
--     (el primero de cada una, a <= 3 km de la capital; el resto a <= 25 km en
--      España, <= 15 km en Portugal y <= 2 km en Andorra), siempre en tierra
--   * actualiza IdProvincia, Ciudad, CodigoPostal, Latitud, Longitud y Coordenadas
--     (ahora Coordenadas = POINT(Longitud, Latitud), ya coinciden)
--   * recalcula DistanciaKmOrigen
-- Se puede volver a ejecutar: siempre deja los mismos valores.
-- =====================================================================

USE `BDIADelivery`;
SET NAMES utf8mb4;
SET @OLD_SQL_SAFE_UPDATES = @@SQL_SAFE_UPDATES, SQL_SAFE_UPDATES = 0;

-- 1. Distritos de Portugal y parroquias de Andorra
INSERT INTO `Provincias` (`IdProvincia`, `Nombre`, `IdPais`) VALUES""")
L.append(",\n".join(f"({i}, {q(n)}, '{c}')" for i, n, c in new_prov))
L.append("ON DUPLICATE KEY UPDATE `Nombre` = VALUES(`Nombre`), `IdPais` = VALUES(`IdPais`);\n")
L.append("""-- 2. Nuevas coordenadas (tabla temporal)
DROP TEMPORARY TABLE IF EXISTS `tmp_CoordenadasDestinos`;
CREATE TEMPORARY TABLE `tmp_CoordenadasDestinos` (
  `IdDestino`    INT NOT NULL PRIMARY KEY,
  `IdProvincia`  INT NOT NULL,
  `Ciudad`       VARCHAR(100) NOT NULL,
  `CodigoPostal` VARCHAR(10)  NOT NULL,
  `Latitud`      DECIMAL(10,7) NOT NULL,
  `Longitud`     DECIMAL(10,7) NOT NULL
);
""")
for s in range(0, len(out), 500):
    L.append("INSERT INTO `tmp_CoordenadasDestinos` (`IdDestino`, `IdProvincia`, `Ciudad`, `CodigoPostal`, `Latitud`, `Longitud`) VALUES")
    L.append(",\n".join(f"({i}, {p}, {q(c)}, {q(cp)}, {la:.7f}, {lo:.7f})" for i, p, c, cp, la, lo, *_ in out[s:s+500]) + ";")
L.append("""
-- 3. Aplicar a Destinos
UPDATE `Destinos` d
  JOIN `tmp_CoordenadasDestinos` t ON t.`IdDestino` = d.`IdDestino`
   SET d.`IdProvincia`  = t.`IdProvincia`,
       d.`Ciudad`       = t.`Ciudad`,
       d.`CodigoPostal` = t.`CodigoPostal`,
       d.`Latitud`      = t.`Latitud`,
       d.`Longitud`     = t.`Longitud`,
       d.`Coordenadas`  = POINT(t.`Longitud`, t.`Latitud`);

DROP TEMPORARY TABLE `tmp_CoordenadasDestinos`;

-- 4. Distancias desde Mataró
CALL sp_RecalcularDistancias();

SET SQL_SAFE_UPDATES = @OLD_SQL_SAFE_UPDATES;

-- =====================================================================
-- Comprobaciones
-- =====================================================================
-- Destinos por país (ProvinciaDeOtroPais debe salir 0)
SELECT d.`IdPais`, COUNT(*) AS Destinos,
       SUM(p.`IdPais` <> d.`IdPais`) AS ProvinciaDeOtroPais,
       ROUND(MIN(d.`Latitud`), 2) AS LatMin, ROUND(MAX(d.`Latitud`), 2) AS LatMax,
       ROUND(MIN(d.`Longitud`), 2) AS LonMin, ROUND(MAX(d.`Longitud`), 2) AS LonMax,
       ROUND(AVG(d.`DistanciaKmOrigen`), 0) AS KmMedioDesdeMataro
FROM `Destinos` d JOIN `Provincias` p ON p.`IdProvincia` = d.`IdProvincia`
GROUP BY d.`IdPais`;

-- Provincias/distritos/parroquias sin ningún destino (debe salir 0)
SELECT COUNT(*) AS ProvinciasSinDestino
FROM `Provincias` p
WHERE NOT EXISTS (SELECT 1 FROM `Destinos` d WHERE d.`IdProvincia` = p.`IdProvincia`);

-- Coordenadas y Latitud/Longitud coinciden (debe salir 0)
SELECT COUNT(*) AS CoordenadasDistintas
FROM `Destinos`
WHERE ABS(ST_X(`Coordenadas`) - `Longitud`) > 0.000001 OR ABS(ST_Y(`Coordenadas`) - `Latitud`) > 0.000001;
""")
open(out_sql, "w", encoding="utf-8", newline="\n").write("\n".join(L))

# Verificación
ok = sum(pais_de(la, lo) == {"España": "ES", "Portugal": "PT", "Andorra": "AD"}[pa] for _, _, _, _, la, lo, pa, _ in out)
d = sorted(x[-1] for x in out)
cov = collections.Counter(x[1] for x in out)
print("destinos:", len(out), dict(cnt), "| en su país y en tierra:", ok,
      "| km a su capital: mediana %.1f, máx %.1f" % (d[len(d)//2], d[-1]),
      "| provincias/distritos/parroquias con destino:", len(cov), "de", 47 + len(PT) + len(AD))

fig, ax = plt.subplots(figsize=(9, 7.5))
xs, ys = zip(*[(b, a) for a, b in IBERIA + [IBERIA[0]]]); ax.plot(xs, ys, color="#444", lw=1)
xs, ys = zip(*[(b, a) for a, b in BORDER_PT]); ax.plot(xs, ys, color="#888", lw=0.8, ls="--")
col = {"España": "#d62728", "Portugal": "#2ca02c", "Andorra": "#1f77b4"}
for pa, c in col.items():
    pts = [(x[5], x[4]) for x in out if x[6] == pa]
    ax.scatter(*zip(*pts), s=6 if pa == "España" else 14, c=c, alpha=0.6, label=f"{pa} ({len(pts)})")
ax.scatter([e[3] for e in ES] + [p[2] for p in PT], [e[2] for e in ES] + [p[1] for p in PT],
           marker="*", s=40, c="k", label="Capitales")
ax.scatter([2.4445], [41.5381], marker="s", s=60, c="orange", label="Mataró")
ax.set_xlim(-10, 4); ax.set_ylim(35.5, 44.2); ax.set_aspect(1.3); ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=8)
ax.set_title("BDIADelivery - destinos con coordenadas corregidas")
fig.tight_layout(); fig.savefig(out_png, dpi=110)
print("OK")
