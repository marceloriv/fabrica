from typing import List, Tuple


def validar_prompt(prompt: str, criterios: List[str]) -> Tuple[bool, List[str]]:
    """
    Valida un prompt contra una lista de criterios de éxito.
    
    Args:
        prompt: El prompt a validar
        criterios: Lista de criterios de éxito
        
    Returns:
        Tuple con (aprobado, lista de correcciones)
    """
    correcciones = []
    
    # Validaciones básicas
    if not prompt or len(prompt.strip()) < 10:
        correcciones.append("El prompt es demasiado corto o está vacío")
    
    if "rol" not in prompt.lower() and "role" not in prompt.lower():
        correcciones.append("Falta definir el rol del asistente")
    
    if "tarea" not in prompt.lower() and "task" not in prompt.lower():
        correcciones.append("Falta definir la tarea específica")
    
    # Validar criterios personalizados
    for criterio in criterios:
        palabras_clave = criterio.lower().split()
        if not any(palabra in prompt.lower() for palabra in palabras_clave):
            correcciones.append(f"No se cumple el criterio: {criterio}")
    
    # Detectar posibles ambigüedades
    palabras_ambiguas = ["quizás", "tal vez", "posiblemente", "podría", "debería"]
    for palabra in palabras_ambiguas:
        if palabra in prompt.lower():
            correcciones.append(f"Ambigüedad detectada: '{palabra}' - usa instrucciones más directas")
    
    return len(correcciones) == 0, correcciones


def generar_reporte_auditoria(
    prompt: str,
    criterios: List[str],
    aprobado: bool,
    correcciones: List[str]
) -> str:
    """
    Genera un reporte formateado de la auditoría.
    """
    reporte = "=" * 60 + "\n"
    reporte += "REPORTE DE AUDITORÍA DE PROMPT\n"
    reporte += "=" * 60 + "\n\n"
    
    reporte += f"ESTADO: {'✅ APROBADO' if aprobado else '❌ RECHAZADO'}\n\n"
    
    reporte += "CRITERIOS DE ÉXITO:\n"
    for i, criterio in enumerate(criterios, 1):
        reporte += f"  {i}. {criterio}\n"
    
    reporte += "\n"
    
    if correcciones:
        reporte += "CORRECCIONES REQUERIDAS:\n"
        for i, correccion in enumerate(correcciones, 1):
            reporte += f"  {i}. {correccion}\n"
    else:
        reporte += "✅ No se requieren correcciones\n"
    
    reporte += "\n" + "=" * 60 + "\n"
    
    if aprobado:
        reporte += "PROMPT FINAL:\n"
        reporte += "-" * 60 + "\n"
        reporte += prompt
        reporte += "\n" + "-" * 60 + "\n"
    
    return reporte
