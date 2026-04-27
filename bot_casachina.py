import os
import smtplib
import pandas as pd
from email.message import EmailMessage
from datetime import datetime
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright

productos = [
    ("Aceite De Sesamo Samyang", "750ml"),
    ("Aji Merken Molido", "100gr"),
    ("Aji Panka", "100gr"),
    ("Alga Kombu", "x paq"),
    ("Arrolladitos Primavera Carne Food House", "10uni"),
    ("Arrolladitos Primavera Verdura Food House", "10uni"),
    ("Arroz Koshihikari", "5kg"),
    ("Arroz Koshihikari", "30kg"),
    ("Arroz Presidente", "10kg"),
    ("Arroz Presidente", "30kg"),
    ("Azucar Mascabo", "1kg"),
    ("Fideos De Arroz 5mm", "400gr"),
    ("Fideos De Arroz Trad. Soyarroz", "300grs"),
    ("Harina De Soja Tostada Yin Yang", "500gr"),
    ("Kanikama Familiar", "1kg"),
    ("Maiz Cancha Roja", "500gr"),
    ("Maiz Pisado Blanco", "1kg"),
    ("Masa Gyoza", "50uni"),
    ("Masa Wantan", "50uni"),
    ("Masa Para Arrolladito", "200Gr"),
    ("Mostaza Estragon", "200gr"),
    ("Negui", "x paq"),
    ("Papel De Arroz 22cm", "500grs"),
    ("Pasta Sesamo Tahina Gourmet", "908gr"),
    ("Pimienta Sichuan", "20gr"),
    ("Salsa De Soja Clara", "1.9lt"),
    ("Salsa Inglesa Darama", "5lt"),
    ("Salsa Tabasco Sriracha", "256ml"),
    ("Shiso", "x paq"),
    ("Tofu Defu", "400gr"),
    ("Tofu Defu", "800gr"),
    ("Tofu Soyarroz Tradicional", "450gr"),
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
    web = normalizar(nombre_web)
    palabras = [p for p in normalizar(nombre_producto).split() if len(p) > 2]
    coincidencias = sum(1 for p in palabras if p in web)
    return coincidencias >= max(1, len(palabras) * 0.6)


def unidad_coincide(nombre_web, unidad):
    nombre = normalizar(nombre_web)
    unidad_norm = normalizar(unidad)

    if unidad_norm == "x paq":
        return True

    unidad_limpia = unidad_norm.replace(" ", "")
    nombre_limpio = nombre.replace(" ", "")

    if unidad_limpia in nombre_limpio:
        return True

    variantes = [unidad_limpia]
    if unidad_limpia.endswith("uni"):
        variantes.append(unidad_limpia.replace("uni", "u"))
    if unidad_limpia.endswith("grs"):
        variantes.append(unidad_limpia.replace("grs", "gr"))
    if unidad_limpia.endswith("gr") and not unidad_limpia.endswith("grs"):
        variantes.append(unidad_limpia + "s")

    return any(v in nombre_limpio for v in variantes)


def scrape_casachina():
    resultados = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for nombre_producto, unidad in productos:
            termino = f"{nombre_producto} {unidad}" if unidad != "x paq" else nombre_producto
            print(f"\n--- Buscando: {nombre_producto} ({unidad})")

            try:
                url_busqueda = f"https://www.casachinaoficial.com/?s={quote_plus(termino)}&post_type=product"
                page.goto(url_busqueda, timeout=60000)
                page.wait_for_timeout(3000)

                try:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                except:
                    pass

                items = page.locator("div.product")
                count = items.count()
                print(f"   {count} resultados en la busqueda")

                if count == 0:
                    raise Exception("Sin resultados de busqueda")

                candidatos = []
                for i in range(count):
                    item = items.nth(i)
                    try:
                        nw = item.locator("h3 a").text_content(timeout=3000).strip()
                    except:
                        try:
                            nw = item.locator("h3").text_content(timeout=3000).strip()
                        except:
                            continue

                    try:
                        pr = item.locator("span.woocommerce-Price-amount.amount bdi").first.text_content(timeout=3000).strip()
                    except:
                        try:
                            pr = item.locator("span.woocommerce-Price-amount.amount").first.text_content(timeout=3000).strip()
                        except:
                            try:
                                pr = item.locator(".price").first.text_content(timeout=3000).strip()
                            except:
                                pr = "No encontrado"

                    candidatos.append((nw, pr))

                encontrado = False
                for nw, pr in candidatos:
                    if nombre_coincide(nw, nombre_producto) and unidad_coincide(nw, unidad):
                        print(f"   MATCH: {nw} | {pr}")
                        resultados.append({
                            "Producto": nombre_producto,
                            "Unidad": unidad,
                            "Nombre Web": nw,
                            "Precio": pr,
                            "Proveedor": "Casa China Oficial",
                            "Fecha": datetime.now().strftime("%Y-%m-%d")
                        })
                        encontrado = True
                        break

                if not encontrado:
                    for nw, pr in candidatos:
                        if nombre_coincide(nw, nombre_producto):
                            print(f"   MATCH parcial (nombre sin unidad exacta): {nw} | {pr}")
                            resultados.append({
                                "Producto": nombre_producto,
                                "Unidad": unidad,
                                "Nombre Web": f"(aprox) {nw}",
                                "Precio": pr,
                                "Proveedor": "Casa China Oficial",
                                "Fecha": datetime.now().strftime("%Y-%m-%d")
                            })
                            encontrado = True
                            break

                if not encontrado:
                    print(f"   SIN MATCH - ningun resultado coincide con '{nombre_producto}'")
                    resultados.append({
                        "Producto": nombre_producto,
                        "Unidad": unidad,
                        "Nombre Web": "",
                        "Precio": "No encontrado",
                        "Proveedor": "Casa China Oficial",
                        "Fecha": datetime.now().strftime("%Y-%m-%d")
                    })

            except Exception as e:
                print(f"   Error: {e}")
                resultados.append({
                    "Producto": nombre_producto,
                    "Unidad": unidad,
                    "Nombre Web": "",
                    "Precio": "No encontrado",
                    "Proveedor": "Casa China Oficial",
                    "Fecha": datetime.now().strftime("%Y-%m-%d")
                })

        browser.close()
    return pd.DataFrame(resultados)


def enviar_mail(nombre_archivo, cantidad_productos, encontrados):
    remitente = os.environ["MAIL_REMITENTE"]
    password = os.environ["MAIL_PASSWORD"]
    destinatario = os.environ["MAIL_DESTINATARIO"]

    msg = EmailMessage()
    msg["Subject"] = f"Precios Casa China - {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = remitente
    msg["To"] = destinatario
    msg.set_content(
        f"Adjunto el listado de precios de Casa China Oficial.\n\n"
        f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Productos buscados: {cantidad_productos}\n"
        f"Encontrados: {encontrados}\n"
        f"No encontrados: {cantidad_productos - encontrados}\n"
    )

    with open(nombre_archivo, "rb") as f:
        contenido = f.read()
    msg.add_attachment(
        contenido,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=nombre_archivo,
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(remitente, password)
        smtp.send_message(msg)

    print(f"Mail enviado a {destinatario}")


if __name__ == "__main__":
    df_resultados = scrape_casachina()

    nombre_archivo = f"Casa China V {datetime.now().strftime('%Y-%m-%d')}.xlsx"
    df_resultados.to_excel(nombre_archivo, index=False)

    encontrados = (df_resultados["Precio"] != "No encontrado").sum()
    print(f"\nArchivo generado: {nombre_archivo} ({len(df_resultados)} productos, {encontrados} encontrados)")

    enviar_mail(nombre_archivo, len(df_resultados), encontrados)
