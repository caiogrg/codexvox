# CodexVox (Python, dvcs + sv)

Conversa por voz com o Codex dentro do DOSVOX. Você digita a pergunta, o DOSVOX fala a resposta.

Esta versão substitui a ponte em ScriptVox + `.CMD` + `.BAT`. Não há mais arquivos de troca, caminhos para editar nem `.BAT`: um único programa faz tudo.

## Instalação (para usuários)

1. Instale o [Node.js](https://nodejs.org), a única dependência. Depois feche e abra o DOSVOX.
2. Baixe o `CodexVox.exe` na página [Releases](../../releases) deste repositório e coloque-o numa pasta (a DLL do dvcs deve ficar junto).
3. Abra o `CodexVox.exe` pelo DOSVOX. Se o Codex não estiver instalado, o programa pergunta se deve instalá-lo (tecle S e Enter). Esc cancela.
4. Na primeira vez, digite `/configurar`: o navegador abre, você entra na conta do ChatGPT e aceita o acesso. Depois é só perguntar.

É preciso uma conta do ChatGPT. Cada pergunta é enviada ao serviço do Codex (OpenAI).

## Como funciona

1. `codexvox.py` pergunta pelo `sv` e chama a ponte.
2. `ponte.py` roda `codex exec` com a pergunta pela entrada padrão (nunca como argumento de comando). A primeira pergunta cria uma conversa; as seguintes a retomam.
3. A resposta é limpa para voz (sem markdown, sem endereços longos) e lida pelo DOSVOX.
4. A resposta completa, com links, fica em `resposta.txt` (ANSI). O comando `/editor` abre esse arquivo no Edivox, onde dá para navegar linha a linha.

Comandos: `/nova` (outra conversa), `/configurar` (conecta o Codex a uma conta pelo navegador; `/configurar codigo` usa o login por código), `/editor`, `/sobre`, Enter vazio ou Esc encerra.


## Usar a partir do código-fonte

1. Instale o Node.js (nodejs.org), a única dependência. O Codex o programa instala sozinho: se não o encontrar, pergunta se você quer instalá-lo (S ou N), roda `npm install -g @openai/codex` e Esc cancela. Se preferir, instale você mesmo com esse comando.
2. Faça login uma vez: digite `/configurar` no programa (o Codex abre o navegador, você entra na conta e aceita; tecle A se o navegador não abrir ou Esc para cancelar) ou, no prompt de comando, `codex login`
3. Rode: `python codexvox.py`

Se algo falhar, o programa fala o motivo (sem login, Codex ausente, tempo esgotado). A conversa fica em `%APPDATA%\CodexVox\conversa.id`.

## Problemas comuns

- **"node não é reconhecido" ou o Codex não é encontrado:** o ambiente do DOSVOX guarda o PATH de quando foi aberto. Se você instalou o Node.js ou o Codex com o DOSVOX aberto, feche e abra o DOSVOX de novo (não precisa reiniciar o computador).
- **`codex login` diz que logou, mas o programa diz que não:** confira no prompt com `codex login status`. Faça o login com o mesmo usuário do Windows que roda o DOSVOX e espere o terminal terminar sozinho. Se o retorno pelo navegador falhar, use `codex login --device-auth` (ou `/configurar codigo`), mas esse modo só funciona se o "login com código de dispositivo" estiver ativado nas configurações de segurança do ChatGPT; sem isso a página recusa com um aviso em vermelho.
- **Nada é falado ao abrir:** o `sv` precisa de `sv.inicia()` no começo do programa. O erro e o motivo ficam em `%APPDATA%\CodexVox\codexvox.log`.

## Empacotar

    pyinstaller --name CodexVox codexvox.py

Copie a DLL do dvcs para a pasta do executável, como nos outros programas. O executável foi testado do início ao fim (instalação do Codex, `/configurar`, pergunta e contexto).

## Segurança e privacidade

- O Codex roda em modo somente leitura nas duas chamadas (`sandbox_mode="read-only"`). Somente leitura ainda permite **ler** arquivos do computador.
- Cada pergunta é enviada ao serviço do Codex (OpenAI). Não use dados pessoais de alunos nem senhas.

## Limites conhecidos

- Testado no PyVox (DOSVOX) com o módulo `sv` do autor. `escreve()`, `inicia()` e `le()` em `codexvox.py` são os únicos pontos que tocam o `sv`. Atenção: o primeiro parâmetro de `sv.le` é `mudo`, então a leitura deve ser chamada sem argumentos (o aviso é falado antes, com `escreve`).
- O Codex é um agente de código: a resposta pode levar dezenas de segundos. O tempo máximo é de 5 minutos.

## Licença

Veja o arquivo [LICENSE](LICENSE). O dvcs tem a licença do seu autor e não faz parte desta.

## Créditos

- Primeira versão, em ScriptVox, e ideia original: Jonas Macedo
- Pedido: Antonio Muniz
- Versão em Python com dvcs e sv: Caio Gustavo Rodrigues Grizosto
- dvcs: Thiago Seus
    
