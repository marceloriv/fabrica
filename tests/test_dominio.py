from fabrica_prompts.dominio import detectar_dominio, obtener_nombre_dominio


def test_detectar_dominio():
    """Prueba que el dominio se detecte correctamente basándose en palabras clave."""
    assert detectar_dominio("Necesito escribir código en python") == "python"
    assert detectar_dominio("Generar una campaña de marketing digital") == "marketing"
    assert (
        detectar_dominio("Cómo optimizar despliegues con Docker y Kubernetes")
        == "devops"
    )
    assert detectar_dominio("hacer un audit de rendimiento") == "python"
    assert detectar_dominio("usar la herramienta opencode") == "python"
    assert detectar_dominio("hola mundo") == "general"


def test_obtener_nombre_dominio():
    """Prueba la traducción de código de dominio a su nombre legible."""
    assert obtener_nombre_dominio("python") == "Desarrollo de Software"
    assert obtener_nombre_dominio("marketing") == "Marketing Digital"
    assert obtener_nombre_dominio("inexistente") == "General"
