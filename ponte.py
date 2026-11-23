"""Ponte entre o Codex CLI e o DOSVOX. Sem interface: roda e testa em qualquer console."""
from __future__ import annotations
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

# --- configuração ---
TEMPO_MAXIMO = 300
TEMPO_INSTRUCOES = 30
TEMPO_NAVEGADOR = 5
TEMPO_INSTALACAO = 900
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
URL_LOGIN = re.compile(r"https://(?:[\w-]+\.)*openai\.com/\S*")
CODIGO_LOGIN = re.compile(r"^\s*([A-Z0-9]{3,6}-[A-Z0-9]{3,6})\s*$")
MAX_CARACTERES = 24000
ID_VALIDO = re.compile(r"^[0-9a-fA-F-]{30,40}$")
ORIENTACAO = (
    "Você responde a uma pessoa cega que ouve a resposta num sintetizador de voz. "
    "Responda em português do Brasil, em texto corrido e simples, sem markdown, "
    "sem tabelas e sem links, a menos que ela peça. Seja objetivo."
)
INSTALACAO = "Instale o Codex com: npm install -g @openai/codex. Depois faça login com: codex login."

# --- erros ---
class ErroCodex(Exception):
    """Erro com mensagem já pronta para ser lida em voz."""
def explica_conhecido(erro: str, retomando: bool) -> str:
    # devolve "" quando o erro não é um dos conhecidos
    if re.search(r"\bnode\b.{0,40}(reconhecido|not recognized|cannot find)", erro, re.I | re.S):
        return ("O Codex precisa do Node.js, mas este programa não o encontrou. "
                "Feche o CodexVox e abra de novo. Se continuar, reinstale o Node.js e reinicie o computador.")
    if re.search(r"not logged in|not authenticated|unauthorized|\b401\b|codex login|sign in|log in", erro, re.I):
        return "O Codex não está conectado a uma conta. Digite barra configurar para conectar, ou, no prompt de comando: codex login."
    if retomando and re.search(r"no rollout found|thread/resume", erro, re.I):
        return "O Codex não encontrou a conversa anterior. Digite barra nova para começar outra."
    return ""
def explica_erro(erro: str, retomando: bool) -> str:
    linhas = [l.strip() for l in erro.splitlines() if l.strip()]
    detalhe = linhas[-1][:200] if linhas else "sem detalhes"
    return explica_conhecido(erro, retomando) or "O Codex terminou com erro. Detalhe: " + detalhe

# --- localizar e executar ---
def pasta_estado() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "CodexVox"
def achar_codex() -> list[str]:
    manual = os.environ.get("CODEXVOX_CODEX")
    if manual:
        return [manual]
    achado = shutil.which("codex")
    if achado:
        return [achado]
    appdata = os.environ.get("APPDATA")
    if appdata and (Path(appdata) / "npm" / "codex.cmd").is_file():
        return [str(Path(appdata) / "npm" / "codex.cmd")]
    raise ErroCodex("Não encontrei o Codex neste computador. " + INSTALACAO)
def procura(nome: str) -> str:
    # procura no PATH deste processo mais as pastas usuais do Node (o PATH do DOSVOX pode ser antigo)
    return shutil.which(nome, path=ambiente(pastas_node())["PATH"]) or ""
def tem_node() -> bool:
    return bool(procura("node") and procura("npm"))
def precisa_instalar_codex() -> bool:
    try:
        achar_codex()
        return False
    except ErroCodex:
        return True

def instala_codex(progresso=None, intervalo: float = 1.0) -> None:
    """Instala o Codex CLI usando o npm.
    progresso: função chamada a cada `intervalo` segundos durante a instalação; se devolver True, cancela.
    Levanta ErroCodex em qualquer falha.
    """
    if not precisa_instalar_codex():
        return
    npm = procura("npm")
    if not npm:
        raise ErroCodex("O Node.js não está instalado neste computador. Instale o Node.js primeiro.")

    # --- executar o comando ---
    pasta = pasta_estado()
    pasta.mkdir(parents=True, exist_ok=True)
    processo = inicia_processo([npm, "install", "-g", "@openai/codex"], pasta,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    saida = []
    leitor = threading.Thread(target=lambda: saida.extend(decodifica(l).strip() for l in processo.stdout), daemon=True)
    leitor.start()
    limite = time.monotonic() + TEMPO_INSTALACAO
    try:
        while True:
            try:
                processo.wait(timeout=intervalo)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() > limite:
                    encerra(processo)
                    raise ErroCodex("A instalação do Codex demorou demais e foi interrompida.") from None
                if progresso and progresso():
                    encerra(processo)
                    raise ErroCodex("A instalação do Codex foi cancelada.") from None
        leitor.join(5)
    finally:
        processo.wait()
        leitor.join(5)
        if not leitor.is_alive():  # fechar com o leitor ainda preso no pipe travaria
            processo.stdout.close()

    # --- verificar o resultado ---
    if processo.returncode != 0:
        fim = "; ".join(l for l in saida[-4:] if l)
        raise ErroCodex("Não consegui instalar o Codex. " + (fim or "sem detalhes")[:500])
    if precisa_instalar_codex():
        raise ErroCodex("A instalação terminou, mas o executável do Codex não foi localizado.")

# --- interface com o usuário ---
def argumentos(retoma: str, saida: Path) -> list[str]:
    inicio = ["exec", "resume"] if retoma else ["exec"]
    opcoes = ["--json", "--skip-git-repo-check", "-c", 'sandbox_mode="read-only"', "-o", str(saida)]
    return inicio + opcoes + ([retoma] if retoma else []) + ["-"]
def pastas_node() -> list[str]:
    # o codex.cmd chama `node`; se o PATH deste processo for antigo (Node instalado depois), ele não acha
    modelos = [("ProgramFiles", "nodejs"), ("ProgramW6432", "nodejs"), ("ProgramFiles(x86)", "nodejs"),
               ("LOCALAPPDATA", os.path.join("Programs", "nodejs")), ("APPDATA", "npm")]
    return [os.path.join(os.environ[var], sub) for var, sub in modelos if os.environ.get(var)]
def ambiente(extras: list[str]) -> dict:
    env = dict(os.environ)
    atuais = env.get("PATH", "").split(os.pathsep)
    novas = [p for p in extras if os.path.isdir(p) and p not in atuais]
    env["PATH"] = os.pathsep.join(atuais + novas)
    return env
def oem() -> str:
    try:
        import ctypes
        return "cp%d" % ctypes.windll.kernel32.GetOEMCP()
    except Exception:
        return "cp850"
def decodifica(dados: bytes) -> str:
    # o Codex escreve em UTF-8; mensagens do cmd.exe vêm na página de código do console (OEM)
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode(oem(), "replace")

# --- abrir navegador ---
def encerra(processo: subprocess.Popen) -> None:
    # no Windows o codex.cmd cria processos filhos: taskkill /T leva a árvore toda
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(processo.pid)], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        processo.kill()
def mata(processo: subprocess.Popen) -> None:
    encerra(processo)
    processo.communicate()
def inicia_processo(comando: list[str], pasta: Path, **canais) -> subprocess.Popen:
    try:
        return subprocess.Popen(comando, cwd=pasta, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                env=ambiente(pastas_node() + [str(Path(comando[0]).parent)]), **canais)
    except OSError as erro:
        raise ErroCodex("Não consegui iniciar o Codex: " + str(erro)) from erro
def executa(comando: list[str], entrada: str, pasta: Path, limite: float = 0) -> tuple[int, str, str]:
    processo = inicia_processo(comando, pasta, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        saida, erro = processo.communicate(entrada.encode("utf-8"), timeout=limite or TEMPO_MAXIMO)
    except subprocess.TimeoutExpired:
        mata(processo)
        raise ErroCodex("O Codex demorou demais e foi interrompido.") from None
    return processo.returncode, decodifica(saida), decodifica(erro)

# --- ler o resultado ---
def le_eventos(texto: str) -> list[dict]:
    eventos = []
    for linha in texto.splitlines():
        try:
            evento = json.loads(linha)
        except ValueError:
            continue
        if isinstance(evento, dict):
            eventos.append(evento)
    return eventos
def id_da_conversa(eventos: list[dict]) -> str:
    for evento in eventos:
        achado = evento.get("thread_id", "")
        if evento.get("type") == "thread.started" and ID_VALIDO.fullmatch(achado):
            return achado
    return ""

def ultima_mensagem(eventos: list[dict]) -> str:
    # plano B se o arquivo -o faltar; o formato item.completed/agent_message não foi visto no Codex real
    itens = [e.get("item") for e in eventos if e.get("type") == "item.completed"]
    textos = [i.get("text", "") for i in itens if isinstance(i, dict) and i.get("type") == "agent_message"]
    return textos[-1] if textos else ""
def le_saida(arquivo: Path) -> str:
    if not arquivo.exists():
        return ""
    return arquivo.read_text(encoding="utf-8-sig", errors="replace")

# --- texto para voz ---
def limpa_fala(texto: str) -> list[str]:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"```[A-Za-z0-9]*", "", texto)
    texto = re.sub(r"!?\[([^\]]*)\]\(\s*https?://[^)]*\)", r"\1", texto)
    texto = re.sub(r"https?://\S+", "(endereço omitido)", texto)
    texto = re.sub(r"\*\*|__|`", "", texto)
    texto = re.sub(r"(?<![\w*])\*(\S(?:[^*\n]*\S)?)\*(?![\w*])", r"\1", texto)
    texto = re.sub(r"^\s{0,3}#{1,6}\s*", "", texto, flags=re.M)
    texto = re.sub(r"^\s*[-*•]\s+", "", texto, flags=re.M)
    texto = re.sub(r"\s+[—–]\s+", ", ", texto)
    if len(texto) > MAX_CARACTERES:
        texto = texto[:MAX_CARACTERES].rsplit(" ", 1)[0] + "\nA resposta foi encurtada."
    return [l.strip() for l in texto.split("\n") if l.strip()]
def salva_resposta(texto: str, pasta: Path) -> Path:
    # cópia completa (com links) em ANSI, para abrir no Edivox
    arquivo = Path(pasta) / "resposta.txt"
    arquivo.write_text(texto.strip().replace("\n", "\r\n") + "\r\n", encoding="cp1252", errors="replace")
    return arquivo

# --- login (codex login --device-auth) ---
def limpa_ansi(texto: str) -> str:
    return ANSI.sub("", texto)
def acha_instrucoes(linhas: list[str]) -> tuple[str, str]:
    # devolve (endereço, código); "" para o que ainda não apareceu. O endereço precisa ser da openai.com
    # (no login pelo navegador o endereço é longo e não há código)
    url = codigo = ""
    for linha in linhas:
        achado, marcado = URL_LOGIN.search(linha), CODIGO_LOGIN.match(linha)
        url = url or (achado.group(0) if achado else "")
        codigo = codigo or (marcado.group(1) if marcado else "")
    return url, codigo

class Login:
    # por_codigo=False: `codex login` (o Codex abre o navegador sozinho e imprime o endereço de reserva)
    # por_codigo=True: `codex login --device-auth` (só funciona se estiver ativado nas configurações de segurança do ChatGPT)
    def __init__(self, comando: list[str], pasta: Path, por_codigo: bool = False):
        self.linhas, self.fila, self.por_codigo = [], queue.Queue(), por_codigo
        self.processo = inicia_processo(comando + ["login"] + (["--device-auth"] if por_codigo else []), pasta,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        threading.Thread(target=self.le_saida, daemon=True).start()
    def le_saida(self) -> None:
        for bruto in self.processo.stdout:
            self.fila.put(limpa_ansi(decodifica(bruto)).strip())
        self.processo.stdout.close()
        self.fila.put(None)

    # devolve as instruções de login (endereço, código) ou levanta ErroCodex se não aparecerem a tempo
    def recolhe(self) -> None:
        while not self.fila.empty():
            linha = self.fila.get()
            if linha:
                self.linhas.append(linha)
    def instrucoes(self, tempo: float = 0) -> tuple[str, str]:
        limite = time.monotonic() + (tempo or (TEMPO_INSTRUCOES if self.por_codigo else TEMPO_NAVEGADOR))
        while True:
            url, codigo = acha_instrucoes(self.linhas)
            if url and (codigo or not self.por_codigo):
                return url, codigo
            try:
                linha = self.fila.get(timeout=max(0.05, limite - time.monotonic()))
            except queue.Empty:
                if not self.por_codigo:  # o navegador pode ter aberto sem o Codex imprimir o endereço
                    return url, codigo
                self.cancela()
                raise ErroCodex("Não consegui ler as instruções de login do Codex a tempo.") from None
            if linha is None:
                self.processo.wait()
                if not self.por_codigo and self.processo.returncode == 0:
                    return url, codigo
                ultima = self.linhas[-1][:200] if self.linhas else "sem detalhes"
                raise ErroCodex("O login do Codex terminou antes da hora. Detalhe: " + ultima)
            if linha:
                self.linhas.append(linha)

    # devolve True se o login terminou (com sucesso ou não)
    def terminou(self) -> bool:
        return self.processo.poll() is not None
    def sucesso(self) -> bool:
        return self.processo.poll() == 0
    def cancela(self) -> None:
        if not self.terminou():
            encerra(self.processo)
        self.processo.wait()
    def bruto(self) -> str:
        self.recolhe()
        return "\n".join(self.linhas)

# --- Codex ---
class Codex:
    def __init__(self, pasta=None, comando=None):
        self.pasta = Path(pasta) if pasta else pasta_estado()
        self.trabalho = self.pasta / "trabalho"
        self.trabalho.mkdir(parents=True, exist_ok=True)
        self.arquivo_id = self.pasta / "conversa.id"
        self.comando = comando or achar_codex()
    def conversa(self) -> str:
        if not self.arquivo_id.exists():
            return ""
        valor = self.arquivo_id.read_text(encoding="ascii", errors="ignore").strip()
        return valor if ID_VALIDO.fullmatch(valor) else ""
    def nova(self) -> None:
        self.arquivo_id.unlink(missing_ok=True)

    # --- login ---
    def confere_login(self) -> None:
        # sem login o Codex fica tentando reconectar por minutos; `login status` responde na hora
        codigo, bruto, erro = executa(self.comando + ["login", "status"], "", self.trabalho, 30)
        if codigo == 0:
            return
        detalhe = (bruto + " " + erro).strip()[:300] or "sem texto"
        conhecido = explica_conhecido(detalhe, False)
        if conhecido:
            raise ErroCodex(conhecido)
        raise ErroCodex("Não consegui conferir o login do Codex. Código %d. Resposta: %s. Programa: %s"
                        % (codigo, detalhe, " ".join(self.comando)))
    def logado(self) -> bool:
        return executa(self.comando + ["login", "status"], "", self.trabalho, 30)[0] == 0
    def inicia_login(self, por_codigo: bool = False) -> Login:
        return Login(self.comando, self.trabalho, por_codigo)

    # --- pergunta ---
    def pergunta(self, texto: str) -> str:
        texto = texto.strip()
        if not texto:
            raise ErroCodex("A pergunta está vazia.")
        self.confere_login()
        retoma = self.conversa()
        if not retoma:
            texto = ORIENTACAO + "\n\nPergunta: " + texto
        saida = self.pasta / "ultima.utf8.tmp"
        saida.unlink(missing_ok=True)
        codigo, bruto, erro = executa(self.comando + argumentos(retoma, saida), texto, self.trabalho)
        if codigo != 0:
            raise ErroCodex(explica_erro(erro or bruto, bool(retoma)))
        eventos = le_eventos(bruto)
        resposta = le_saida(saida) or ultima_mensagem(eventos)
        saida.unlink(missing_ok=True)
        if not resposta.strip():
            raise ErroCodex("O Codex não devolveu resposta.")
        novo = id_da_conversa(eventos)
        if novo:
            self.arquivo_id.write_text(novo, encoding="ascii")
        return resposta

# --- demonstração (sem Codex, para testar a interface) ---
class Demonstracao:
    def __init__(self):
        self.pasta = pasta_estado()
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.numero = 0
    def nova(self) -> None:
        self.numero = 0
    def logado(self) -> bool:
        return True
    def pergunta(self, texto: str) -> str:
        self.numero += 1
        return ("**Modo demonstração**, pergunta número %d. Você escreveu: `%s`.\n\n"
                "- primeiro item da lista\n- segundo item da lista\n\n"
                "Veja [o manual](https://exemplo.org/manual?a=1&b=2) para mais detalhes." % (self.numero, texto))
