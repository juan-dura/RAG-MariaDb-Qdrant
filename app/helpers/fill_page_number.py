def fill_page_number(page: int, total_pages: int) -> str:
    """
    Devuelve un string con el numero de página formateado con los ceros necesarios para mantener un orden lexicográfico correcto.
    Ejemplo: fill_page_number(3, 120) -> "003"
    """
    if total_pages is None:
        return str(page)
    total_digits = len(str(total_pages))
    return str(page).zfill(total_digits)