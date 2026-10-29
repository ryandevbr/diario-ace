def calcular_volume_retangular(comprimento_cm: float, largura_cm: float, altura_cm: float) -> float:
    # Converter cm para dm (dividir por 10), pois 1 dm³ = 1 litro
    c = comprimento_cm / 10
    l = largura_cm / 10
    h = altura_cm / 10
    return c * l * h

def calcular_volume_cilindrico(diametro_cm: float, altura_cm: float) -> float:
    d = diametro_cm / 10
    h = altura_cm / 10
    # Fórmula do manual: V = 0,8 * (D * D) * H
    return 0.8 * (d * d) * h

def calcular_volume_triangular(base_cm: float, largura_cm: float, altura_cm: float) -> float:
    b = base_cm / 10
    l = largura_cm / 10
    h = altura_cm / 10
    # Fórmula do manual: V = (Base * Largura * Altura) / 2
    return (b * l * h) / 2

def obter_dosagem(volume_litros: float) -> str:
    """Retorna a dosagem recomendada em colheres baseada na tabela do Ministério da Saúde."""
    if volume_litros <= 0:
        return "0 colheres"
    elif volume_litros <= 50:
        return "Aproximadamente ½ colher"
    elif volume_litros <= 100:
        return "Aproximadamente 1 colher"
    elif volume_litros <= 200:
        return "Aproximadamente 1,5 colheres"
    elif volume_litros <= 250:
        return "Aproximadamente 2 colheres"
    elif volume_litros <= 300:
        return "Aproximadamente 2,5 colheres"
    elif volume_litros <= 500:
        return "Aproximadamente 4 colheres"
    elif volume_litros <= 1000:
        return "Aproximadamente 8 colheres"
    else:
        # Para volumes maiores que 1000L, a regra geral é 8 colheres a cada 1000L
        colheres = (volume_litros / 1000) * 8
        return f"Aproximadamente {colheres:.1f} colheres (volume > 1000L)"