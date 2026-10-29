import flet as ft
from app.components.ui import card, snack
from app.services import calculadora_service

def build(page: ft.Page) -> ft.Control:
    # Estado para controlar os campos visíveis
    tipo_atual = {"valor": "retangular"}
    
    # Campos de entrada (serão usados dinamicamente)
    campo_comp = ft.TextField(label="Comprimento (cm)", keyboard_type=ft.KeyboardType.NUMBER)
    campo_larg = ft.TextField(label="Largura (cm)", keyboard_type=ft.KeyboardType.NUMBER)
    campo_alt = ft.TextField(label="Altura (cm)", keyboard_type=ft.KeyboardType.NUMBER)
    campo_diam = ft.TextField(label="Diâmetro (cm)", keyboard_type=ft.KeyboardType.NUMBER)
    campo_base = ft.TextField(label="Base (cm)", keyboard_type=ft.KeyboardType.NUMBER)
    
    # Container para agrupar os campos visíveis
    container_campos = ft.Column(spacing=10)
    
    # Painel de resultado
    texto_volume = ft.Text("0 L", size=32, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700)
    texto_dose = ft.Text("-", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_700)
    resultado_container = ft.Container(
        content=card(
            page,
            ft.Column([
                ft.Text("Volume do Depósito", size=13, color=ft.Colors.GREY_600),
                texto_volume,
                ft.Divider(),
                ft.Text("Dose Recomendada", size=13, color=ft.Colors.GREY_600),
                texto_dose,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        ),
        visible=False
    )

    def atualizar_campos(e=None):
        container_campos.controls.clear()
        tipo = dropdown_tipo.value
        
        if tipo == "retangular":
            container_campos.controls.extend([campo_comp, campo_larg, campo_alt])
        elif tipo == "cilindrico":
            container_campos.controls.extend([campo_diam, campo_alt])
        elif tipo == "triangular":
            container_campos.controls.extend([campo_base, campo_larg, campo_alt])
            
        resultado_container.visible = False
        page.update()

    dropdown_tipo = ft.Dropdown(
        label="Tipo de Depósito",
        options=[
            ft.dropdown.Option(key="retangular", text="Caixa Retangular (Tanque)"),
            ft.dropdown.Option(key="cilindrico", text="Caixa Cilíndrica (Tambor)"),
            ft.dropdown.Option(key="triangular", text="Depósito Triangular"),
        ],
        value="retangular",
        on_select=atualizar_campos,  # <-- MUDOU DE on_change PARA on_select
    )

    def calcular(e):
        try:
            # Pega os valores com segurança
            def get_val(campo): return float(campo.value) if campo.value else 0.0
            
            tipo = dropdown_tipo.value
            volume = 0.0
            
            if tipo == "retangular":
                volume = calculadora_service.calcular_volume_retangular(
                    get_val(campo_comp), get_val(campo_larg), get_val(campo_alt))
            elif tipo == "cilindrico":
                volume = calculadora_service.calcular_volume_cilindrico(
                    get_val(campo_diam), get_val(campo_alt))
            elif tipo == "triangular":
                volume = calculadora_service.calcular_volume_triangular(
                    get_val(campo_base), get_val(campo_larg), get_val(campo_alt))
                
            if volume <= 0:
                snack(page, "Preencha as medidas corretamente.", ft.Colors.RED_500)
                return
                
            # Atualiza a tela
            texto_volume.value = f"{volume:.1f} Litros"
            texto_dose.value = calculadora_service.obter_dosagem(volume)
            resultado_container.visible = True
            page.update()
            
        except ValueError:
            snack(page, "Digite apenas números.", ft.Colors.RED_500)

    # Inicializa os campos
    atualizar_campos()

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Text("Calculadora de Larvicida", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text("Calcule o volume para descobrir a dose correta.", size=13, color=ft.Colors.GREY_600),
                    ft.Container(height=10),
                    
                    card(page, ft.Column([
                        dropdown_tipo,
                        container_campos,
                        ft.Button(
                            "Calcular Volume",
                            icon=ft.Icons.CALCULATE,
                            on_click=calcular,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.TEAL_700,
                                color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=15
                            )
                        )
                    ], spacing=15)),
                    
                    ft.Container(height=15),
                    resultado_container
                ])
            )
        ]
    )