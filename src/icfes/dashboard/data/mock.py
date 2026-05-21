import numpy as np
import pandas as pd


def mock_anos() -> list[str]:
    return [str(y) for y in range(2015, 2026)]


def mock_trend_data() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    anos = mock_anos()
    return pd.DataFrame(
        {
            "ano": anos,
            "Global": 250 + rng.normal(0, 5, len(anos)).cumsum(),
            "Matemáticas": 47 + rng.normal(0, 2, len(anos)).cumsum(),
            "Lectura": 50 + rng.normal(0, 2, len(anos)).cumsum(),
            "Ciencias": 48 + rng.normal(0, 2, len(anos)).cumsum(),
        }
    )


def mock_depto_data() -> pd.DataFrame:
    deptos = [
        "Cundinamarca",
        "Antioquia",
        "Valle",
        "Santander",
        "Boyacá",
        "Risaralda",
        "Quindío",
        "Atlántico",
        "Caldas",
        "Nariño",
    ]
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        {"Departamento": deptos, "Promedio": 255 + rng.uniform(-20, 30, 10)}
    )


def mock_gender_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Área": [
                "Global",
                "Matemáticas",
                "Lectura",
                "Ciencias",
                "Sociales",
                "Inglés",
            ],
            "Masculino": [258, 50, 51, 49, 47, 46],
            "Femenino": [255, 47, 53, 48, 50, 45],
        }
    )
