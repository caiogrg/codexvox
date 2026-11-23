"""CodexVox: conversa por voz com o Codex dentro do DOSVOX (dvcs + sv)."""
from __future__ import annotations
import os
import subprocess
import sys
import time
import traceback
import webbrowser
import ponte
try:
    import sv
    erro_sv = ""
except ImportError as erro:
    sv, erro_sv = None, str(erro)  # sem o sv, cai para o console comum (útil para testar)

# --- textos ---
CREDITOS = (
    "CodexVox. Primeira versão, em ScriptVox: Jonas Macedo. "
    "Demanda: Antonio Muniz. "
    "Versão em Python com dvcs e sv: Caio Gustavo Rodrigues Grizosto."
)
AJUDA = (
    "Digite sua pergunta e Enter. "
    "Comandos: "
    "barra nova começa outra conversa, "
    "barra configurar conecta o Codex a uma conta pelo navegador, "
    "barra editor abre a última resposta no Edivox, "
    "barra sobre mostra os créditos. "
    "Enter sem texto ou Esc encerra."
)

# --- diagnóstico (a janela do dvcs pode esconder erros; tudo vai para codexvox.log) ---
def registra(texto: str) -> None:
    pasta = ponte.pasta_estado()
    pasta.mkdir(parents=True, exist_ok=True)
    with open(pasta / "codexvox.log", "a", encoding="utf-8") as arquivo:
        arquivo.write(texto + "\n")

# --- voz (únicos pontos que tocam o sv; ajuste aqui se a assinatura for outra) ---
def escreve(texto: str) -> None:
    sv.escreve(texto) if sv else print(texto)
def inicia() -> None:
    if sv:
        sv.inicia()
def le(aviso: str) -> str:
    escreve(aviso)  # o primeiro parâmetro de sv.le é `mudo`: passar o aviso ali deixaria a leitura sem voz
    texto = (sv.le() if sv else input()) or ""
    return "" if "\x1b" in texto else texto  # Esc é o padrão do DOSVOX para sair
def escreve_linhas(linhas: list[str]) -> None:
    for linha in linhas:
        escreve(linha)
def soletra(texto: str) -> None:
    sv.soletra(texto) if sv else print(" ".join(texto))
def tecla() -> str:
    # tecla pendente em minúsculas ("esc" para o Esc); "" se nenhuma
    if not (sv and sv.teclado()):
        return ""
    lida = sv.le(tecla=True)
    lida = lida.decode("latin-1") if isinstance(lida, bytes) else str(lida)
    return "esc" if lida == "\x1b" else lida.lower()
def abre_endereco(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception as erro:
        registra("não consegui abrir o navegador: " + str(erro))

# --- conversa ---
def abre_editor(codex) -> None:
    arquivo = codex.pasta / "resposta.txt"
    edivox = r"C:\Winvox\edivox.exe"
    if not arquivo.exists():
        escreve("Ainda não há resposta para abrir.")
    elif os.path.exists(edivox):
        subprocess.Popen([edivox, str(arquivo)])
    elif hasattr(os, "startfile"):
        os.startfile(str(arquivo))
    else:
        escreve("A resposta está em " + str(arquivo))

def avisa_login(url: str, codigo: str, por_codigo: bool) -> None:
    if not por_codigo:
        escreve("O Codex vai abrir o navegador. Entre na sua conta e aceite o acesso. "
                "Tecle A se o navegador não abrir, ou Esc para cancelar.")
        return
    escreve("Vou abrir o navegador. Entre na sua conta e digite o código que vou soletrar. "
            "Este modo só funciona se o login por código estiver ativado nas configurações de segurança do ChatGPT.")
    abre_endereco(url)
    soletra(codigo)
    escreve("Tecle C para ouvir o código de novo, A para abrir o navegador de novo, ou Esc para cancelar.")

# --- login ---
def configurar(codex, por_codigo: bool = False) -> None:
    if codex.logado():
        escreve("O Codex já está conectado a uma conta.")
        return
    try:
        login = codex.inicia_login(por_codigo)
        url, codigo = login.instrucoes()
    except ponte.ErroCodex as erro:
        registra("login: " + str(erro))
        escreve(str(erro) + " Se continuar, no prompt de comando digite: codex login.")
        return
    avisa_login(url, codigo, por_codigo)
    while not login.terminou():
        apertada = tecla()
        if apertada == "esc":
            login.cancela()
            escreve("Login cancelado.")
            return
        if apertada == "c" and codigo:
            soletra(codigo)
        if apertada == "a":
            login.recolhe()
            url = ponte.acha_instrucoes(login.linhas)[0]
            if url:
                abre_endereco(url)
            else:
                escreve("Ainda não tenho o endereço.")
        time.sleep(0.3)
    registra("login: " + "\n".join(l for l in login.bruto().splitlines()
                                   if not (ponte.CODIGO_LOGIN.match(l) or ponte.URL_LOGIN.search(l))))
    escreve("Pronto. O Codex está conectado." if codex.logado()
            else "O login não foi concluído. Digite barra configurar para tentar de novo.")

# --- comandos ---
def comando(texto: str, codex) -> None:
    if texto == "/nova":
        codex.nova()
        escreve("Conversa nova.")
    elif texto.split()[0] == "/configurar":
        try:
            configurar(codex, "codigo" in texto or "código" in texto)
        except Exception as erro:  # a janela do dvcs não pode fechar sem explicar
            registra(traceback.format_exc())
            escreve("Erro inesperado: " + str(erro))
    elif texto == "/editor":
        abre_editor(codex)
    elif texto == "/sobre":
        escreve(CREDITOS)
    else:
        escreve(AJUDA)

# --- pergunta ---
def responde(texto: str, codex) -> None:
    escreve("Consultando o Codex. Aguarde.")
    try:
        bruta = codex.pergunta(texto)
    except ponte.ErroCodex as erro:
        escreve(str(erro))
        return
    except Exception as erro:  # a janela do dvcs não pode fechar sem explicar
        escreve("Erro inesperado: " + str(erro))
        return
    ponte.salva_resposta(bruta, codex.pasta)
    escreve_linhas(ponte.limpa_fala(bruta))

# --- instalação do Codex ---
def espera_instalacao():
    # chamada a cada segundo pela ponte: Esc cancela e, de 20 em 20 segundos, avisa que continua
    contagem = [0]
    def progresso() -> bool:
        contagem[0] += 1
        if tecla() == "esc":
            return True
        if contagem[0] % 20 == 0:
            escreve("Ainda instalando. Esc cancela.")
        return False
    return progresso

def instala_codex_se_necessario() -> int:
    """Devolve 0 se o Codex está pronto para uso; 1 se o usuário recusou ou a instalação falhou."""
    if not ponte.precisa_instalar_codex():
        return 0
    if not ponte.tem_node():
        escreve("O Codex precisa do Node.js, que não está instalado. Instale o Node.js, em nodejs ponto org, "
                "e abra o programa de novo. Se você acabou de instalar, feche e abra o DOSVOX.")
        return 1
    escreve("O Codex não está instalado.")
    if le("Deseja instalá-lo agora? Digite S para sim ou N para não, e Enter.").strip().lower() not in ("s", "sim"):
        escreve("O Codex é necessário para utilizar este programa.")
        return 1
    escreve("Instalando o Codex. Isso pode levar alguns minutos. Esc cancela.")
    try:
        ponte.instala_codex(espera_instalacao())
    except ponte.ErroCodex as erro:
        registra("instalação: " + str(erro))
        escreve(str(erro))
        return 1
    escreve("Instalação concluída. Se ainda não conectou sua conta, digite barra configurar.")
    return 0

# --- programa ---
def principal(argv: list[str]) -> int:
    inicia()
    if "--demo" not in argv and instala_codex_se_necessario():
        return 1
    try:
        codex = ponte.Demonstracao() if "--demo" in argv else ponte.Codex()
    except ponte.ErroCodex as erro:
        escreve(str(erro))
        return 1
    escreve(AJUDA)
    while True:
        texto = le("Pergunte ao Codex.").strip()
        if not texto:
            break
        if texto.startswith("/"):
            comando(texto.lower(), codex)
        else:
            responde(texto, codex)
    escreve("Até logo.")
    return 0

if __name__ == "__main__":
    registra("início. sv carregado: %s. erro ao carregar o sv: %s" % (sv is not None, erro_sv or "nenhum"))
    try:
        codigo = principal(sys.argv[1:])
    except Exception:
        registra(traceback.format_exc())
        raise
    registra("fim, código %d" % codigo)
    sys.exit(codigo)
