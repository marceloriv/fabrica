from fabrica_prompts.tools import parece_instruccion


def test_parece_instruccion_detecta_instrucciones_reales():
    assert parece_instruccion("Actúa como una pastelera experta y mentora culinaria...")
    assert parece_instruccion("Actua como un maestro pastelero, paciente y didáctico.")
    assert parece_instruccion("Eres un ingeniero de software senior experto en Python.")
    assert parece_instruccion("Tu tarea es redactar una guía paso a paso.")


def test_parece_instruccion_detecta_respuestas_directas():
    assert not parece_instruccion("¡Hola! Bienvenida al mundo de la pastelería.")
    assert not parece_instruccion("Hola y bienvenida al fascinante mundo de la ciencia dulce.")
    assert not parece_instruccion("### Guía de Inicio a la Pastelería: Tus Primeras Tortas")
    assert not parece_instruccion("Claro, acá tenés la guía que pediste.")
    assert not parece_instruccion("Aquí tenés todo lo que necesitás saber.")


def test_parece_instruccion_ignora_espacios_iniciales():
    assert not parece_instruccion("   ¡Hola! Bienvenida.")
    assert parece_instruccion("   Actúa como un experto.")
