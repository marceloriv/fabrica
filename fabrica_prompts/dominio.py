import re

DOMINIOS = {
    "python": "Desarrollo de Software",
    "marketing": "Marketing Digital",
    "ventas": "Ventas",
    "educacion": "Educación",
    "legal": "Derecho",
    "finanzas": "Finanzas",
    "salud": "Salud",
    "datos": "Ciencia de Datos",
    "devops": "DevOps",
    "seguridad": "Ciberseguridad",
    "ia": "Inteligencia Artificial",
    "diseno": "Diseño UX/UI",
    "proyecto": "Gestión de Proyectos",
    "rrhh": "Recursos Humanos",
    "logistica": "Logística",
    "ecommerce": "E-commerce",
    "contenido": "Creación de Contenido",
    "soporte": "Soporte Técnico",
    "consultoria": "Consultoría",
    "investigacion": "Investigación",
}


PALABRAS_CLAVE = {
    "python": [
            "python",
            "código",
            "programar",
            "desarrollo",
            "software",
            "api",
            "ponytail",
            "audit",
            "opencode",
            "react",
            "typescript",
            "javascript",
            "node",
            "sql",
            "frontend",
            "backend",
        ],
        "marketing": [
            "marketing",
            "publicidad",
            "campaña",
            "branding",
            "seo",
            "social media",
        ],
        "ventas": [
            "ventas",
            "vender",
            "clientes",
            "negociación",
            "prospectos",
            "cierre",
        ],
        "educacion": [
            "educación",
            "enseñar",
            "aprender",
            "curso",
            "formación",
            "capacitación",
        ],
        "legal": ["legal", "ley", "contrato", "jurídico", "normativa", "regulación"],
        "finanzas": [
            "finanzas",
            "dinero",
            "inversión",
            "presupuesto",
            "contabilidad",
            "financiero",
        ],
        "salud": [
            "salud",
            "médico",
            "paciente",
            "tratamiento",
            "bienestar",
            "enfermedad",
        ],
        "datos": [
            "datos",
            "análisis",
            "estadística",
            "machine learning",
            "modelo",
            "predictivo",
        ],
        "devops": [
            "devops",
            "despliegue",
            "ci/cd",
            "infraestructura",
            "docker",
            "kubernetes",
        ],
        "seguridad": [
            "seguridad",
            "vulnerabilidad",
            "ataque",
            "protección",
            "cifrado",
            "hack",
        ],
        "ia": [
            "ia",
            "inteligencia artificial",
            "llm",
            "gpt",
            "automatización",
            "chatbot",
        ],
        "diseno": ["diseño", "ux", "ui", "interfaz", "experiencia", "wireframe"],
        "proyecto": ["proyecto", "scrum", "ágil", "planificación", "gestión", "sprint"],
        "rrhh": [
            "rrhh",
            "reclutamiento",
            "contratación",
            "empleados",
            "talento",
            "equipo",
        ],
        "logistica": [
            "logística",
            "envío",
            "almacén",
            "cadena",
            "suministro",
            "distribución",
        ],
        "ecommerce": [
            "ecommerce",
            "tienda",
            "carrito",
            "pagos",
            "producto",
            "catálogo",
        ],
        "contenido": [
            "contenido",
            "blog",
            "artículo",
            "redacción",
            "copywriting",
            "publicación",
        ],
        "soporte": ["soporte", "ayuda", "ticket", "incidente", "problema", "solución"],
        "consultoria": [
            "consultoría",
            "asesoría",
            "estrategia",
            "recomendación",
            "experto",
        ],
        "investigacion": [
            "investigación",
            "estudio",
            "análisis",
            "reporte",
            "hallazgos",
            "conclusión",
        ],
}
_PATRONES_DOMINIO = {
    dominio: re.compile(
        r"\b(" + "|".join(re.escape(p) for p in sorted(palabras, key=len, reverse=True)) + r")\b"
    )
    for dominio, palabras in PALABRAS_CLAVE.items()
}


def detectar_dominio(solicitud: str) -> str:
    """Detecta el dominio más probable basado en palabras clave en la solicitud."""
    texto = solicitud.lower()
    max_coincidencias = 0
    dominio_detectado = "general"

    for dominio, patron in _PATRONES_DOMINIO.items():
        coincidencias = len(set(patron.findall(texto)))
        if coincidencias > max_coincidencias:
            max_coincidencias = coincidencias
            dominio_detectado = dominio

    return dominio_detectado


def obtener_nombre_dominio(codigo: str) -> str:
    """
    Obtiene el nombre completo del dominio a partir de su código.
    """
    return DOMINIOS.get(codigo, "General")
