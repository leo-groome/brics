"""Vocabulario controlado de Families para el normalizer LLM.

Lista cerrada que el modelo debe respetar (Pydantic enum). Si el modelo intenta
devolver una familia fuera de esta lista, el parser falla y se hace retry.

Iterable: editar este archivo + re-correr ingest no rompe el catálogo existente
(los conceptos viejos siguen mapeados a sus familias previas).

Granularidad pensada para el lenguaje real de los 51 XLSX históricos del cliente
(agencias automotrices, residencial, comercial).
"""

FAMILIES: list[str] = [
    # Obra gruesa / estructura
    "Preliminares",
    "Demolicion",
    "Movimientos Tierra",
    "Cimentacion",
    "Estructura Concreto",
    "Estructura Acero",
    "Albanileria",
    "Impermeabilizacion",
    # Acabados / arquitectura
    "Tablarroca",
    "Plafones",
    "Pintura",
    "Pisos",
    "Recubrimientos Muros",
    "Carpinteria",
    "Canceleria Aluminio",
    "Cristaleria",
    "Herreria",
    "Fachada",
    # Mobiliario fijo
    "Muebles Bano",
    "Muebles Cocina",
    "Equipamiento",
    # Instalaciones
    "Instalacion Electrica",
    "Iluminacion",
    "Instalacion Hidraulica",
    "Instalacion Sanitaria",
    "Instalacion Gas",
    "Aire Acondicionado",
    "Voz Datos",
    "Seguridad CCTV",
    # Misc
    "Otros",
]
