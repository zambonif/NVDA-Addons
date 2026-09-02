# Diário para NVDA

Add-on acessível para criar, listar, ler, editar e excluir entradas de diário no NVDA.

## Recursos da versão 1.1

- título e texto sem limite definido pelo add-on;
- data da entrada escolhida por dia, mês e ano;
- data e hora de criação registradas automaticamente;
- data e hora da última edição, quando houver;
- lista ordenada da data mais recente para a mais antiga;
- leitura em caixa de texto somente para leitura;
- confirmação antes da exclusão;
- senha obrigatória antes de exibir a lista e os comandos do diário;
- criptografia autenticada AES-256-GCM do conteúdo completo, inclusive títulos e datas;
- proteção da chave com PBKDF2-HMAC-SHA256 e 600 mil iterações;
- frase de recuperação opcional para definir uma senha nova;
- alteração de senha e cadastro, substituição ou remoção da frase de recuperação;
- migração automática das entradas sem criptografia da versão 0.1;
- arquivo local criptografado, gravação atômica e cópia de segurança também criptografada;
- menu Ferramentas e atalho `NVDA+Alt+D`;
- painel próprio em Preferências → Configurações do NVDA;
- idiomas português do Brasil, espanhol, italiano, francês e inglês, escolhidos
  sem alterar o idioma geral do NVDA.

## Senha, recuperação e migração

Na primeira abertura da versão 0.2, o add-on pede uma senha. Se houver entradas da versão 0.1, elas são importadas para o cofre. Os arquivos antigos sem criptografia só são removidos depois que o novo cofre é gravado e relido com sucesso.

A frase de recuperação é opcional, mas recomendada. Ela não revela nem armazena a senha antiga: permite abrir a chave do cofre e cadastrar uma senha nova. A frase deve ser longa e difícil de adivinhar. Para facilitar a lembrança, diferenças entre letras maiúsculas e minúsculas e espaços repetidos são ignoradas na frase; a senha continua sendo exata.

Se o usuário perder tanto a senha quanto a frase cadastrada, não há mecanismo de recuperação. Isso é uma consequência necessária de não manter uma porta dos fundos no cofre.

As entradas ficam na subpasta `diario` da pasta de configurações do NVDA. Os arquivos da versão 0.2 são `diario.enc` e `diario.backup.enc`. Nada é enviado para a internet.

A remoção dos arquivos antigos impede sua leitura normal, mas não promete apagamento forense dos setores já usados pelo disco, especialmente em SSDs ou em pastas sincronizadas. Quem precisar eliminar vestígios antigos deve considerar também cópias externas, histórico de sincronização e backups do computador.

## Estrutura

O arquivo instalável é um ZIP com a extensão `.nvda-addon`. Para empacotar manualmente, compacte o conteúdo da raiz deste projeto — não a pasta externa — mantendo `manifest.ini` na raiz do pacote.

## Compatibilidade declarada

- NVDA mínimo: 2025.1.0
- Última API testada no manifesto: 2026.1.1

Os testes automatizados cobrem o armazenamento independente da interface. A validação completa da interface exige NVDA no Windows.

A versão 0.2.1 corrige a falha que impedia o complemento de carregar no NVDA 2026.1.1. O executável do NVDA não inclui o submódulo `cryptography.hazmat.primitives.ciphers.aead`, embora outras partes do pacote `cryptography` estejam presentes. No Windows, o Diário agora chama diretamente a implementação AES-GCM da API CNG do sistema e não depende desse submódulo.

A versão 0.2.2 mantém viva a reserva do identificador do botão de recuperação durante toda a execução do NVDA. Também torna idempotentes os comandos de fechamento das janelas de leitura, edição e da lista principal, evitando que eventos repetidos chamem o wxPython depois que a janela já foi destruída.

A versão 0.2.3 troca o identificador do botão “Bloquear e fechar” da janela principal pelo cancelamento nativo dos diálogos wxPython e adiciona tratamento direto para Enter, Espaço e Enter do teclado numérico.

A versão 1.0 acrescenta uma categoria “Diário” às configurações do NVDA. A
escolha de idioma vale para as novas janelas do add-on; reiniciar o NVDA também
atualiza o nome do item no menu Ferramentas, a categoria de configurações e a
descrição do gesto. A preferência fica em `diario/preferencias.json` e não
altera nem recriptografa o cofre existente.

A versão 1.1 prepara o complemento para a loja oficial do NVDA. O manifesto-base
passa a usar inglês, como exigido pelos metadados da loja, enquanto português,
espanhol, italiano e francês recebem manifestos localizados. Também foram
acrescentados o endereço do repositório, o contato protegido do autor e a versão
do NVDA realmente usada nos testes. O formato do cofre não foi alterado.

## Gerar o instalador

Execute `python build-addon.py`. O arquivo será criado em `dist/diario-1.1.0.nvda-addon`.

## Idiomas

O português do Brasil é o idioma-base. Espanhol, italiano, francês e inglês
estão incluídos desde a versão 1.0. O idioma é escolhido na categoria “Diário” das
configurações do NVDA.

## Licença

GNU General Public License, versão 2 ou posterior.
