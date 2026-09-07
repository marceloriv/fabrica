from fabrica_prompts.tools import parece_instruccion, verificar_grounding


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


def test_verificar_grounding_detecta_tecnologias_con_simbolos():
    contexto = "El proyecto usará C# y Python en el backend."
    prompt = "Actúa como desarrollador senior. Escribe código en C# y C++ con .NET."

    resultado = verificar_grounding(prompt, contexto)
    assert "C++" in resultado
    assert ".NET" in resultado
    assert "C#" not in resultado  # C# está respaldado en contexto


def test_verificar_grounding_respeta_limites_de_palabra():
    # 'api' no debe coincidir dentro de 'rapidez'
    contexto = "La rapidez del algoritmo es crítica para la empresa."
    prompt = "Diseña una API REST para el servicio."

    resultado = verificar_grounding(prompt, contexto)
    assert "API" in resultado
    assert "REST" in resultado


def test_verificar_grounding_todos_respaldados():
    contexto = "Recomendamos Docker, FastAPI y PostgreSQL para este despliegue."
    prompt = "Despliega el servicio usando Docker y FastAPI conectado a PostgreSQL."

    resultado = verificar_grounding(prompt, contexto)
    assert "aparecen respaldados" in resultado
