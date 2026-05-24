import re
import sys
import pandas as pd
from datetime import datetime
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright

# Evita UnicodeEncodeError al imprimir nombres con caracteres especiales en consola Windows
sys.stdout.reconfigure(encoding="utf-8")

# Solo el nombre del producto (sin cantidad ni gramaje): el bot trae todas las
# presentaciones que ese producto tenga en la web, cada una con su unidad real.
productos = [
    "Aceite De Sesamo Samyang",
    "Aji Merken Molido",
    "Aji Panka",
    "Alga Kombu",
    "Arrolladitos Primavera Carne Food House",
    "Arrolladitos Primavera Verdura Food House",
    "Arroz Koshihikari",
    "Arroz Presidente",
    "Azucar Mascabo",
    "Fideos De Arroz 5mm",
    "Fideos De Arroz Trad. Soyarroz",
    "Harina De Soja Tostada Yin Yang",
    "Kanikama Familiar",
    "Maiz Cancha Roja",
    "Maiz Pisado Blanco",
    "Masa Gyoza",
    "Masa Wantan",
    "Masa Para Arrolladito",
    "Mostaza Estragon",
    "Negui",
    "Papel De Arroz",
    "Pasta Sesamo Tahina",
    "Pimienta Sichuan",
    "Salsa De Soja Clara",
    "Salsa Inglesa Darama",
    "Salsa Tabasco Sriracha",
    "Shiso",
    "Tofu Defu",
    "Tofu Soyarroz Tradicional",
    "Aceite De Sesamo Kadoya",
    "Aceite Trufa Negra",
    "Aceite De Sesamo Nutrasem",
    "Alga Nori",
    "Arroz Fortuna Kometo",
    "Fideos De Arroz Vermicelli",
    "Fideos De Arroz Finos",
    "Hondashi",
    "Mirin",
    "Panko",
    "Gochujang",
    "Salsa Hoisin",
    "Salsa De Ostras",
    "Salsa De Pescado",
    "Salsa De Soja Bitarwan",
    "Sriracha",
    "Sesamo Integral",
    "Vinagre De Arroz",
    "Wasabi",
]


def normalizar(texto):
    """Normaliza texto para comparacion: minusculas, sin puntos ni tildes."""
    import unicodedata
    texto = texto.lower().strip()
    texto = texto.replace(".", "").replace(",", "").replace("-", " ")
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def nombre_coincide(nombre_web, nombre_producto):
    """El nombre web debe contener TODAS las palabras clave del producto buscado.
    Asi se traen solo las presentaciones de ese producto y no otros parecidos."""
    web = normalizar(nombre_web)
    # Palabras clave del nombre buscado (ignorar palabras cortas como "de", "con")
    palabras = [p for p in normalizar(nombre_producto).split() if len(p) > 2]
    if not palabras:
        return False
    return all(p in web for p in palabras)


def limpiar_nombre(nombre_web):
    """Deja el nombre solo en espanol + unidad de medida.
    Descarta: caracteres chinos, parentesis y su contenido, y la barra '/'."""
    txt = nombre_web
    # Quitar todo lo que este entre parentesis (marca, etc.)
    txt = re.sub(r"\([^)]*\)", " ", txt)
    # Quitar caracteres chinos / japoneses / coreanos y puntuacion CJK
    txt = re.sub(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]", " ", txt)
    # Quitar la barra separadora
    txt = txt.replace("/", " ")
    # Normalizar espacios sobrantes
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def extraer_precio(item):
    """Toma el precio vigente (rojo), ignorando el precio tachado en oferta.
    En WooCommerce el precio viejo va dentro de <del>; el precio vigente
    es el unico que NO esta dentro de un <del>."""
    loc = item.locator(
        "xpath=.//span[contains(@class,'price')]"
        "//span[contains(@class,'woocommerce-Price-amount')][not(ancestor::del)]"
    )
    try:
        if loc.count() > 0:
            return loc.first.inner_text(timeout=3000).strip()
    except Exception:
        pass
    return "No encontrado"


def scrape_casachina():
    resultados = []
    vistos = set()  # evita repetir la misma presentacion en filas distintas
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()

        for nombre_producto in productos:
            print(f"\n--- Buscando: {nombre_producto}")

            try:
                # Buscar por URL directa con parametros WooCommerce
                url_busqueda = f"https://www.casachinaoficial.com/?s={quote_plus(nombre_producto)}&post_type=product"
                page.goto(url_busqueda, timeout=60000)
                page.wait_for_timeout(3000)

                # Cerrar popup si existe
                try:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                except:
                    pass

                # Obtener productos de los resultados
                items = page.locator("div.product")
                count = items.count()
                print(f"   {count} resultados en la busqueda")

                if count == 0:
                    raise Exception("Sin resultados de busqueda")

                # Traer TODAS las presentaciones que coincidan con el nombre:
                # cada tamano/variante es una fila propia con su unidad real.
                encontrado = False
                for i in range(count):
                    item = items.nth(i)
                    try:
                        nw = item.locator("h3 a").text_content(timeout=3000).strip()
                    except:
                        try:
                            nw = item.locator("h3").text_content(timeout=3000).strip()
                        except:
                            continue

                    if not nombre_coincide(nw, nombre_producto):
                        continue

                    encontrado = True
                    nombre_limpio = limpiar_nombre(nw)
                    clave = nombre_limpio.lower()
                    if clave in vistos:
                        continue
                    vistos.add(clave)

                    pr = extraer_precio(item)
                    print(f"   MATCH: {nombre_limpio} | {pr}")
                    resultados.append({
                        "Productos": nombre_limpio,
                        "Precio": pr,
                    })

                if not encontrado:
                    print(f"   SIN MATCH - ningun resultado coincide con '{nombre_producto}'")
                    resultados.append({
                        "Productos": nombre_producto,
                        "Precio": "No encontrado",
                    })

            except Exception as e:
                print(f"   Error: {e}")
                resultados.append({
                    "Productos": nombre_producto,
                    "Precio": "No encontrado",
                })

        browser.close()
    return pd.DataFrame(resultados)


if __name__ == "__main__":
    df_resultados = scrape_casachina()
    fecha = datetime.now().strftime("%Y-%m-%d")

    # A1: proveedor | A2: fecha | A3: vacia | A4: encabezados | A5+: datos
    with pd.ExcelWriter("precios_casachina.xlsx", engine="openpyxl") as writer:
        df_resultados.to_excel(writer, index=False, startrow=3)
        ws = writer.sheets["Sheet1"]
        ws["A1"] = "Proveedor: Casa China"
        ws["A2"] = f"Fecha: {fecha}"

    print(f"\nArchivo generado: precios_casachina.xlsx ({len(df_resultados)} filas)")
