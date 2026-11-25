"""Comprueba si las coordenadas ORIGINALES de cada destino encajan con su provincia y país.

Uso: python tools/comprobar_coordenadas.py database/original/script_sqlserver.sql \n         analysis/comprobacion_coordenadas.csv analysis/mapa_destinos.png
"""
import re, struct, math, csv, sys, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path

src, out_csv, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
t = open(src, encoding="utf-16").read()

# Capitales de provincia (orden = IdProvincia 1..47 del script)
CAP = [("Álava",42.85,-2.67),("Albacete",38.99,-1.86),("Alicante",38.35,-0.48),("Almería",36.84,-2.46),
("Asturias",43.36,-5.85),("Ávila",40.66,-4.70),("Badajoz",38.88,-6.97),("Barcelona",41.39,2.17),
("Burgos",42.34,-3.70),("Cáceres",39.47,-6.37),("Cádiz",36.53,-6.29),("Cantabria",43.46,-3.81),
("Castellón",39.99,-0.05),("Ciudad Real",38.99,-3.93),("Córdoba",37.89,-4.78),("A Coruña",43.36,-8.41),
("Cuenca",40.07,-2.13),("Girona",41.98,2.82),("Granada",37.18,-3.60),("Guadalajara",40.63,-3.17),
("Guipúzcoa",43.32,-1.98),("Huelva",37.26,-6.95),("Huesca",42.14,-0.41),("Jaén",37.78,-3.79),
("León",42.60,-5.57),("Lleida",41.62,0.62),("Lugo",43.01,-7.56),("Madrid",40.42,-3.70),
("Málaga",36.72,-4.42),("Murcia",37.99,-1.13),("Navarra",42.81,-1.64),("Ourense",42.34,-7.86),
("Palencia",42.01,-4.53),("Pontevedra",42.43,-8.64),("La Rioja",42.47,-2.45),("Salamanca",40.97,-5.66),
("Segovia",40.95,-4.12),("Sevilla",37.39,-5.98),("Soria",41.76,-2.46),("Tarragona",41.12,1.25),
("Teruel",40.34,-1.11),("Toledo",39.86,-4.02),("Valencia",39.47,-0.38),("Valladolid",41.65,-4.72),
("Vizcaya",43.26,-2.93),("Zamora",41.50,-5.75),("Zaragoza",41.65,-0.89)]
names_db = [n for _, n in re.findall(r"\[Provincias\].*VALUES \((\d+), N'([^']*)'", t)]
assert len(names_db) == 47 and all(a[0] == b for a, b in zip(CAP, names_db)), "orden de provincias distinto"

# Contorno aproximado de la península (lat, lon) y frontera ES-PT
IBERIA = [(42.32,3.32),(42.43,3.17),(42.6,1.7),(42.8,0.7),(42.7,-0.3),(43.05,-1.4),(43.37,-1.79),(43.45,-3.0),
(43.47,-3.8),(43.56,-5.7),(43.6,-7.0),(43.79,-7.7),(43.55,-8.3),(43.2,-9.3),(42.4,-8.9),(41.87,-8.87),
(41.1,-8.67),(40.2,-8.9),(39.35,-9.4),(38.7,-9.5),(38.4,-8.8),(37.95,-8.87),(37.0,-8.95),(37.1,-7.9),
(37.2,-7.4),(36.9,-6.4),(36.0,-5.6),(36.15,-5.35),(36.7,-4.4),(36.72,-3.0),(36.75,-2.1),(37.6,-0.7),
(38.0,-0.65),(38.35,-0.45),(38.75,0.2),(39.5,-0.3),(40.0,0.05),(40.7,0.85),(41.1,1.3),(41.35,2.15),
(41.7,2.85),(42.0,3.2)]
BORDER_PT = [(41.87,-8.87),(42.05,-8.2),(41.95,-7.2),(41.97,-6.6),(41.6,-6.2),(41.0,-6.9),(40.35,-6.85),
(39.65,-7.53),(39.0,-7.0),(38.2,-7.3),(37.2,-7.4)]
PORTUGAL = BORDER_PT + [(37.1,-7.9),(37.0,-8.95),(37.95,-8.87),(38.4,-8.8),(38.7,-9.5),(39.35,-9.4),
(40.2,-8.9),(41.1,-8.67)]
iberia_path = Path([(lo, la) for la, lo in IBERIA])
pt_path = Path([(lo, la) for la, lo in PORTUGAL])

def pais_de(lat, lon):
    if not iberia_path.contains_point((lon, lat)):
        return "Mar/fuera"
    if 42.43 <= lat <= 42.66 and 1.41 <= lon <= 1.79:
        return "Andorra"
    return "Portugal" if pt_path.contains_point((lon, lat)) else "España"

def hav(a, b, c, d):
    r = math.radians
    x = math.sin(r(c-a)/2)**2 + math.cos(r(a))*math.cos(r(c))*math.sin(r(d-b)/2)**2
    return 6371.0088*2*math.atan2(math.sqrt(x), math.sqrt(1-x))

rx = re.compile(r"\[Destinos\].*VALUES \((\d+), N'([^']*)', N'([^']*)', (\d+|NULL), N'([^']*)', N'[^']*', "
                r"CAST\(([-\d.]+) AS Decimal\(10, 7\)\), CAST\(([-\d.]+) AS Decimal\(10, 7\)\), 0x([0-9A-F]+)\)")
rows = []
for m in rx.finditer(t):
    i, dire, ciu, prov, pais, lat, lon, hx = m.groups()
    lat, lon = float(lat), float(lon)
    glat, glon = struct.unpack("<dd", bytes.fromhex(hx)[6:22])
    prov = None if prov == "NULL" else int(prov)
    cap = CAP[prov-1] if prov else None
    rows.append(dict(
        IdDestino=int(i), Ciudad=ciu, Pais=pais, IdProvincia=prov, Provincia=cap[0] if cap else "",
        Latitud=lat, Longitud=lon, PaisSegunLatLon=pais_de(lat, lon),
        KmACapitalProvincia_LatLon=round(hav(lat, lon, cap[1], cap[2]), 1) if cap else "",
        CoordLat=round(glat, 7), CoordLon=round(glon, 7), PaisSegunCoordenadas=pais_de(glat, glon),
        KmACapitalProvincia_Coord=round(hav(glat, glon, cap[1], cap[2]), 1) if cap else "",
        KmEntreAmbas=round(hav(lat, lon, glat, glon), 1)))

with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
    w.writeheader(); w.writerows(rows)

def resumen(campo_pais, campo_km):
    km = sorted(r[campo_km] for r in rows if r[campo_km] != "")
    ok_pais = sum(r[campo_pais] == r["Pais"] for r in rows)
    mar = sum(r[campo_pais] == "Mar/fuera" for r in rows)
    cerca = sum(1 for k in km if k <= 50)
    print(f"  país coincide: {ok_pais}/{len(rows)} | en el mar/fuera: {mar} | a <=50 km de su capital: {cerca}/{len(km)}"
          f" | distancia mediana a la capital: {km[len(km)//2]:.0f} km | máx: {km[-1]:.0f} km")
    byp = collections.Counter((r["Pais"], r[campo_pais]) for r in rows)
    print("  (país declarado -> país según coordenadas):", dict(byp))

print("Destinos:", len(rows))
print("Columnas Latitud/Longitud:"); resumen("PaisSegunLatLon", "KmACapitalProvincia_LatLon")
print("Columna Coordenadas (geography):"); resumen("PaisSegunCoordenadas", "KmACapitalProvincia_Coord")
print("Portugal/Andorra con provincia española:",
      sum(1 for r in rows if r["Pais"] != "España" and r["IdProvincia"]))
print("Distancia mediana entre Lat/Lon y Coordenadas:",
      sorted(r["KmEntreAmbas"] for r in rows)[len(rows)//2], "km")
ej = [r for r in rows if r["IdDestino"] in (1, 2, 3)]
for r in ej:
    print(f"  Ej. destino {r['IdDestino']}: provincia {r['Provincia']} ({r['Pais']}) -> Lat/Lon en {r['PaisSegunLatLon']}, "
          f"a {r['KmACapitalProvincia_LatLon']} km de su capital; Coordenadas a {r['KmACapitalProvincia_Coord']} km")

# Mapa
fig, axs = plt.subplots(1, 2, figsize=(15, 7), sharey=True)
col = {"España": "#d62728", "Portugal": "#2ca02c", "Andorra": "#1f77b4"}
for ax, (la, lo, tit) in zip(axs, [("Latitud", "Longitud", "Columnas Latitud / Longitud"),
                                   ("CoordLat", "CoordLon", "Columna Coordenadas (geography)")]):
    xs, ys = zip(*[(b, a) for a, b in IBERIA + [IBERIA[0]]]); ax.plot(xs, ys, color="#444", lw=1)
    xs, ys = zip(*[(b, a) for a, b in BORDER_PT]); ax.plot(xs, ys, color="#888", lw=0.8, ls="--")
    for p, c in col.items():
        pts = [(r[lo], r[la]) for r in rows if r["Pais"] == p]
        ax.scatter(*zip(*pts), s=6 if p == "España" else 18, c=c, alpha=0.6, label=f"{p} declarado ({len(pts)})")
    ax.scatter([c[2] for c in CAP], [c[1] for c in CAP], marker="*", s=60, c="k", label="Capitales de provincia")
    ax.scatter([2.4445], [41.5381], marker="s", s=60, c="orange", label="Mataró")
    ax.set_title(tit); ax.set_xlim(-10, 4); ax.set_ylim(35.5, 44.2); ax.set_aspect(1.3); ax.grid(alpha=0.3)
axs[0].legend(loc="lower right", fontsize=8)
fig.suptitle("BDIADelivery - ubicación de los 1.500 destinos frente a su país declarado")
fig.tight_layout(); fig.savefig(out_png, dpi=110)
print("OK", out_csv, out_png)
