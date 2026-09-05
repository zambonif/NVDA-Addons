# Diário para NVDA

[English](README.md) · [Português do Brasil](README.pt-BR.md) · [Español](README.es.md) · [Italiano](README.it.md) · [Français](README.fr.md)

Versão 1.3.0

O Diário para NVDA é um diário pessoal acessível e offline, integrado ao leitor de telas NVDA. Seu diferencial é reunir entradas com data escolhida, registro automático da criação, cofre criptografado protegido por senha, recuperação opcional e corretor ortográfico acessível em tempo real.

## Principais recursos

- Criar, listar, ler, editar e excluir entradas.
- Escolher a data de cada entrada sem perder a data e a hora originais de criação.
- Proteger título, datas e texto em um cofre com criptografia autenticada AES-256-GCM.
- Alterar a senha e cadastrar opcionalmente uma frase de recuperação.
- Ouvir um bip ao terminar uma palavra possivelmente errada, sem perder o espaço, a pontuação ou a quebra de linha digitada.
- Abrir sugestões com clique direito, Aplicações, Shift+F10 ou Alt+F10.
- Substituir a palavra, ignorá-la durante a sessão atual do NVDA ou adicioná-la ao dicionário local do Diário.
- Exportar os dois arquivos criptografados do cofre para um ZIP e importar somente entradas que ainda não existem no Diário aberto.
- Usar interface e documentação em português do Brasil, inglês, espanhol, italiano ou francês.
- Manter todos os dados no computador; o complemento não envia entradas para a internet.

## Requisitos

- NVDA 2025.1 ou posterior.
- Windows 8 ou posterior para a API nativa de correção ortográfica. As versões atuais do NVDA exigem uma versão mais nova e ainda suportada do Windows.
- Um dicionário ortográfico do Windows para o idioma selecionado no Diário. Se ele não estiver instalado, o Diário continua funcionando normalmente; somente o corretor fica desativado naquele idioma.

## Instalação e abertura

Instale `diario-1.3.0.nvda-addon` pela Loja de Complementos do NVDA ou abra o pacote diretamente e confirme a instalação. Reinicie o NVDA quando solicitado.

Abra pelo menu do NVDA > Ferramentas > Diário ou pressione NVDA+Alt+D. O gesto pode ser alterado em Gestos de Entrada, na categoria Diário.

## Corretor ortográfico

Os campos de título e texto da entrada são verificados enquanto você digita. Depois de uma palavra seguida por espaço, pontuação, Tab ou Enter, toca um bip se o Windows a considerar incorreta. O separador sempre é inserido; portanto, basta continuar digitando para ignorar o aviso.

Coloque o cursor sobre a palavra ou depois dela e pressione Aplicações, Shift+F10 ou Alt+F10. Também é possível clicar nela com o botão direito. O menu acessível mostra até oito sugestões do Windows e, depois delas:

- **Ignorar nesta sessão:** interrompe os avisos para a palavra até o NVDA ser reiniciado.
- **Adicionar ao dicionário local:** grava a palavra em `dicionario.txt`, dentro da pasta de dados do Diário, e evita novos avisos.

O dicionário local é um arquivo de texto UTF-8 que contém somente as palavras adicionadas pelo usuário. Ele não é criptografado porque não contém entradas do diário. O mesmo arquivo é usado nos cinco idiomas da interface.

## Exportação e importação do backup criptografado

Os botões **Exportar backup** e **Importar backup** ficam disponíveis somente depois que o Diário é desbloqueado.

**Exportar backup** abre uma caixa para escolher onde salvar e cria um ZIP contendo exatamente `diario.enc` e `diario.backup.enc`. Os dois arquivos permanecem criptografados; nenhum título, data ou texto de entrada é gravado sem criptografia.

**Importar backup** abre uma caixa para escolher o arquivo, valida as duas cópias criptografadas em uma pasta temporária e acrescenta apenas entradas cujos identificadores ainda não existem no Diário atual. Entradas existentes nunca são substituídas, mesmo que uma entrada importada com o mesmo identificador tenha conteúdo diferente. Datas, títulos, textos e horários de criação das entradas novas são preservados.

Um backup exportado do mesmo cofre é aberto com a chave já mantida pelo Diário desbloqueado e não pede outra senha. Um backup vindo de um cofre criado separadamente possui outra chave aleatória, mesmo que o texto da senha seja igual; somente nesse caso o complemento pede a senha daquele backup. Isso não altera a senha do Diário atual. Depois da mesclagem, as entradas novas ficam protegidas pelo cofre atual.

Se o ZIP for inválido, a senha estiver incorreta, a operação for cancelada ou não houver entradas novas, o Diário atual permanece inalterado.

## Dados, privacidade e recuperação

Os dados ficam abaixo da pasta de configurações do NVDA, na subpasta `diario`. O cofre principal é `diario.enc`, e sua cópia de segurança criptografada é `diario.backup.enc`.

Todo o conteúdo das entradas, inclusive títulos e datas, usa criptografia autenticada AES-256-GCM pela CNG do Windows. A chave do cofre é protegida a partir da senha com PBKDF2-HMAC-SHA256 e 600 mil iterações. Quando cadastrada, a frase de recuperação protege separadamente a mesma chave aleatória.

A frase de recuperação não revela a senha antiga; ela apenas permite criar uma senha nova. Se a senha e a frase forem esquecidas, o complemento não poderá recuperar as entradas. Use segredos longos e difíceis de adivinhar e mantenha cópias independentes dos arquivos criptografados.

A versão 1.3.0 mantém o formato do cofre criptografado compatível com a versão 1.1.0.

## Idioma da interface

Abra menu do NVDA > Preferências > Configurações > Diário para escolher Português (Brasil), Español, Italiano, Français ou English sem alterar o idioma geral do NVDA. Novas janelas usam a escolha imediatamente. Reinicie o NVDA para atualizar também o item em Ferramentas, a categoria e a descrição do gesto.

## Compilação e testes do fonte

O repositório usa somente a biblioteca padrão do Python para o build e os testes unitários:

```text
python build.py
python -m unittest discover -s tests -v
```

O build lê a versão em `manifest.ini` e cria `dist/diario-<versão>.nvda-addon`, sem incluir testes, caches ou arquivos de desenvolvimento no instalável.

Use `python build.py --source` para criar também o ZIP do fonte e os checksums.

A ponte do corretor usa `ctypes`, sem dependências Python de terceiros. O pacote pode ser montado em qualquer sistema, mas a integração nativa precisa de uma verificação final no Windows com o NVDA antes da publicação na loja.

## Licença e autor

Copyright © Fernando de Paula Zamboni.

Licença GNU General Public License, versão 2 ou posterior. Consulte [LICENSE.txt](LICENSE.txt).
