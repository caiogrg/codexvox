"""
Módulo scriptvox.
Traduz a semântica do scriptvox para o Python com dvcs.
É a única porta do sistema para o dvcs: os demais módulos importam sv, nunca dvcs. O que não tem nome do Scriptvox passa direto para o dvcs.
"""

import dvcs
from dvcs import *

def inicia(): sintInic(0, "")  # ativa a síntese de voz; quem inicia o programa chama uma vez
def __getattr__(nome):
    """O que o sv não define vem do dvcs (sv.sintWriteln, sv.ENTER...). O Menu vem do módulo menu só quando alguém pede, para o sv não depender dele ao ser importado."""
    if nome == "Menu":
        import menu
        return menu.Menu
    return getattr(dvcs, nome)

COMANDOS = ["ajuda", "teclado", "escreve", "fala", "soletra", "bipa", "cor",
    "fundo", "tela", "Menu", "le", "janela", "toca", "termina"]
TECLAS = ["ENTER", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "CONTROL_F1", "CONTROL_F2", "CONTROL_F3", "CONTROL_F4", "CONTROL_F5", "CONTROL_F6",
    "CONTROL_F7", "CONTROL_F8", "CONTROL_F9", "CONTROL_F10", "CONTROL_F11", "CONTROL_F12",
    "ALT_F1", "INSERT", "DELETE", "HOME", "END", "PAGEUP", "PAGEDOWN",
    "CIMA", "BAIXO",     "ESQUERDA", "DIREITA", "BACKSPACE", "ESC", "TAB"]
CORES = ["BLACK", "BLUE", "GREEN", "CYAN", "RED", "MAGENTA", "BROWN", "LIGHTGRAY",
    "DARKGRAY", "LIGHTBLUE", "LIGHTGREEN", "LIGHTCYAN", "LIGHTRED", "LIGHTMAGENTA",
    "YELLOW", "WHITE"]
__all__ = COMANDOS + TECLAS + CORES + ["inicia"]  # inicia não é comando do Scriptvox: fica fora do menu de ajuda


def teclado() -> bool:
    """Equivalente ao observa teclado do Scriptvox.
    Retorna keyPressed()"""
    return keyPressed()

def escreve(texto: str| list| None= None, mudo: bool= False, quebra: bool= True,
    lista: bool= False):
    """
    Escreve um texto na tela.
    mudo: False sintetiza o texto escrito; True apenas escreve na tela.
    quebra: True quebra a linha ao final da escrita; False equivale ao & em SV.
    lista: True espera receber uma lista para escrever um item por linha.
    """
    def sc_escreve(texto, quebra, mudo):
        if quebra:
            writeln(texto)
        else:
            write(texto)
        if not mudo and texto: sintetiza(str(texto))

    if not lista: sc_escreve(texto, quebra, mudo)
    else:
        if not isinstance(texto, list):
            raise TypeError("Texto deve ser uma lista válida.")
        for item in texto:
            sc_escreve(item, quebra, mudo)

def fala(texto: str, espera: bool=True):
    """
    Sintetiza um texto sem escrever na tela.
    espera: True espera terminar para continuar; False continua a execução.
    """
    if not texto:
        sintPara()
    else:
        sintetiza(texto)
    if espera:
        while sintFalando(): waitMessage()

def soletra(texto: str, espera: bool=True):
    """
    Soletra um texto.
    espera: True espera terminar para continuar; False continua a execução.
    """
    if not texto:
        sintPara()
    else:
        sintSoletra(texto)
    if espera:
        while sintFalando(): waitMessage()

def bipa(clek: int=0):
    sintClek() if clek else sintBip()

def cor(cor: int):
    """Altera a cor do texto na tela.
    Cor pode ser um valor numérico ou uma constante do dvcs.
    """
    textColor(cor)
def fundo(fundo: int):
    """Altera a  cor de fundo na tela.
    Cor pode ser um valor numérico ou uma constante do dvcs.
    """
    textBackground(fundo)

def tela (x: None| int= None, y: None| int= None, limpa: bool= False,
    tamanho: bool= False, do_cursor: bool= False,
    linhas: None| tuple[int, int] | None=  None) -> tuple[int, int]:
    """Gerencia a tela.
    x, y: Posicionam o cursor nas coordenadas informadas.
    limpa=True: Limpa a tela.
    do_cursor: Limpa a linha a partir do cursor.

    linhas(y1, y2): Limpa as linhas de y1 a y2.
    Se omitir y1, y2, limpa a linha atual.
    Colocando apenas y1, limpa linha informada.

    tamanho=True: Retorna o tamanho da tela.
    Por padrão, retorna a posição atual do cursor (x, y)
    """

    def limpa_linhas(y1=None, y2=None):
        pos_x = whereX()
        pos_y = whereY()
        _, altura = screenSize()
        if y1 is None: y1 = whereY()
        if y2 is None: y2 = y1
        y1 = max(1, min(y1, altura))
        y2 = max(1, min(y2, altura))
        if y1 > y2:
            y1, y2 = y2, y1
        for i in range(y1, y2 + 1):
            goToXY(1, i)
            clrEol()
        goToXY(pos_x, pos_y)

    if tamanho: return screenSize()
    if x is None: x = whereX()
    if y is None: y = whereY()
    if limpa:
        if do_cursor: clrEol()
        elif  linhas: limpa_linhas(*linhas)
        else: clrScr()
    goToXY(x, y)
    return whereX(), whereY()

def le(
    mudo: bool= False,
    senha: bool= False,
    maiusc:bool= False,
    minusc: bool=  False,
    inteiro: bool= False,
    tecla: bool= False,
    lista: bool= False,
    edita: bool= False,
    term: str = "",
    x: int | None = None,
    y: int | None = None,
    tamanho: int = 255,
    altera: bool = True
):
    """
    Lê dados do usuário
    O tipo retornado depende dos parâmetros informados.
    Combinações de parâmetros são permitidas quando compatíveis entre si.
    edita=True: edita o texto de term (retorna o texto e a tecla que terminou a edição).
    x, y: onde começa a edição (por padrão, a posição do cursor). tamanho: máximo de caracteres.
    altera=False: só percorre o texto, sem poder alterá-lo.
    """
    def scLe(maiusc=False, minusc=False, mudo=False, senha=False,
        inteiro=False, tecla=False):
        if not senha:
            if tecla:
                t = sintReadKey() if not mudo else readKey()
                if t == b"\0": t += readKey()
                return t
            else:
                        s =  sintReadln() if not mudo else readln()
        else:
            s =  sintSenha()
        s = s if not maiusc else s.upper()
        s = s if not minusc else s.lower()
        s = int(s) if inteiro else s
        return s

    if lista:
        l = []
        if not mudo:
            sintWriteln("Leitura de lista.")
        if not term:
            if not mudo: sintWriteln("Termine com uma linha vazia.")
        else:
            if not mudo: sintWriteln(f"Termine com uma linha contendo {term}")
        while True:
            s = scLe(maiusc, minusc, mudo, senha, inteiro, tecla)
            if s == term: break
            l.append(s)
        if not mudo: sintWriteln("Fim da leitura da lista.")
        return l

    elif edita:
        return sintEdita(term, whereX() if x is None else x, whereY() if y is None else y, tamanho, altera)
    return scLe(maiusc, minusc, mudo, senha, inteiro, tecla)

def janela(titulo: str=""):
    """Altera o título da janela."""
    setWindowTitle(titulo)

def toca(arquivo: str, espera: bool= True) -> bool:
    """Toca um arquivo de som (wav ou mp3, sem a extensão) e, se espera=True, só volta quando termina ou quando uma tecla é pressionada.
    espera=False: começa a tocar e continua a execução. Sem arquivo (""), para todos os sons, como o fala() vazio para a fala. Retorna False se o arquivo não existir ou não tocar."""
    import som, time
    if not arquivo:
        som.para()
        return True
    if not som.toca(arquivo): return False
    while espera and som.tocando(arquivo):
        if keyPressed():
            readKey()
            som.para(arquivo)
        time.sleep(0.02)
    return True

def termina(texto: str= ""):
    import sys
    if texto: sintWriteln(texto)
    sintFim()
    sys.exit()

def ajuda(comando):
    import inspect
    obj = globals().get(comando)
    if obj and hasattr(obj, "__doc__"):
        escreve(obj.__name__)
        escreve(inspect.signature(obj))
        escreve(obj.__doc__)
    elif comando in TECLAS:
        escreve(f"Constante de tecla: {comando}")
    elif comando in CORES:
        escreve(f"Constante de cor: {comando}")
    else:
        escreve("Item não encontrado.")
