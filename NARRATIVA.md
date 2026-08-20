<!-- tag: hack2l -->

# Veredito — revisão de código que prova o que afirma

> **Para quem não vai abrir o código.** Escrito em 20/08/2026.
>
> Toda cifra deste documento vem de um arquivo de saída gravado por uma rodada
> real, ou de uma medição que dá para repetir. A **ficha de procedência** no fim
> lista cada número e o arquivo onde ele mora. Nada aqui é estimativa,
> arredondamento ou lembrança.
>
> Isso não é zelo decorativo. Este projeto já comemorou uma métrica que media a
> coisa errada — a história está na seção 8 — e documento de apresentação é
> exatamente onde essa classe de erro nasce.

---

## 1. Em uma página

Um revisor de código automático lê a sua alteração e diz o que achou de errado.
Todos fazem isso hoje. O problema é que eles **afirmam**: escrevem um parágrafo
convincente sobre um defeito que pode não existir, e quem recebe precisa parar o
que está fazendo para conferir cada um.

O Veredito trata cada suspeita como **acusação**, não como conclusão. Antes de
qualquer coisa chegar ao autor do código, ele tenta **provar** a acusação
executando o código de verdade. Só vira achado o que ele conseguiu demonstrar.
O que ele tentou e não conseguiu sai numa lista separada, dizendo por quê. O
que ele examinou e concluiu ser falso alarme sai numa terceira lista, com o
motivo.

A frase que resume: **o veredito é um exit code, não opinião de modelo.** Quem
decide se a prova valeu não é a inteligência artificial — é um teste que roda e
devolve sucesso ou falha, e um humano pode reproduzir em trinta segundos.

O produto ficou em **segundo lugar no Hack2L**, em agosto de 2026.

---

## 2. O problema: encontrar ficou barato, provar não

Em janeiro de 2026 o projeto **curl** encerrou seu programa de recompensa por
falhas de segurança. Durante anos, mais de 15% dos relatórios recebidos se
confirmavam como vulnerabilidade real. Em 2025 essa taxa caiu para menos de 5%,
soterrada por relatórios gerados por inteligência artificial. Eles pagaram
US$ 100 mil por 87 vulnerabilidades reais antes de desligar o programa.

Esse é o mercado inteiro em uma anedota. Gerar suspeita plausível virou
commodity — qualquer modelo faz, aos milhares, por centavos. O que ficou caro é
a **atenção humana** necessária para separar as suspeitas verdadeiras das
falsas.

Uma ferramenta que afirma sem evidência não economiza trabalho de revisão. Ela
**transfere** o trabalho para quem vai conferir, e multiplica. Se o revisor
automático manda dez achados e três são reais, alguém precisa investigar os dez
para descobrir quais três.

O Veredito inverte a pergunta. Em vez de *"o que pode estar errado aqui?"*,
ele pergunta *"consigo demonstrar que isto está errado?"* — e aceita
**"não consegui"** como resposta publicável.

---

## 3. Como funciona — três papéis

A arquitetura copia um tribunal, e não por estética: a divisão de papéis é o que
faz o sistema funcionar.

### Os promotores acusam

Seis leitores automáticos passam pela alteração em paralelo, cada um com uma
lente diferente — segurança, vazamento de dados entre usuários, divergência em
relação ao que a documentação promete, correção, padrões do projeto,
desempenho.

O trabalho deles é **cobertura, não pontaria**. Acusar é barato, e essa lista
bruta ninguém vê. Pedir que se contenham é contraproducente: quando o prompt
mandava reportar "apenas problemas relevantes", o modelo se autocensurava e
engolia defeito real. A filtragem não é trabalho de quem acusa.

### O advogado testa

Esta é a peça central, e a única que é um agente de verdade: ela pensa, chama
uma ferramenta, lê o resultado e decide o próximo passo, em ciclo.

Ele vê **uma acusação por vez, isolada** — sem saber o que as outras lentes
disseram, para não ser contaminado por consenso. E ele **não argumenta: testa.**
Tem acesso ao repositório montado numa cópia descartável, ao banco de dados de
teste e à aplicação rodando.

### O juiz sentencia

Regras determinísticas, cada uma com teste automatizado. Sem modelo de
linguagem, sem rede, em milissegundos.

A regra mais importante: **o artefato ganha do modelo.** Se o advogado escreveu
"PROVADO" e o teste que ele mesmo produziu devolveu sucesso — ou seja, o código
não quebrou —, vale o teste. A opinião do modelo perde para o fato.

A segunda: **a severidade acompanha a força da prova, não a gravidade
teórica.** Um problema catastrófico em tese, sem demonstração, sai como suspeita
de severidade baixa e rotulada. Um problema modesto com teste que quebra sai
acima dele.

> O juiz ser determinístico é uma decisão de produto, não uma limitação. É a
> única peça do sistema que um auditor consegue ler inteira e verificar sozinho.

---

## 4. A prova diferencial, sem jargão

É o mecanismo que sustenta tudo, e cabe em duas frases.

O advogado escreve um teste e roda esse mesmo teste **duas vezes**: uma no seu
código antes da alteração, outra depois. A acusação só é considerada provada se
o teste **passa antes e falha depois**.

Por que isso muda tudo:

- **O falso alarme se elimina sozinho.** Se o teste já falhava no código de
  ontem, o problema não é da sua alteração — e ninguém precisou julgar isso. A
  aritmética decidiu.
- **A evidência deixa de ser uma opinião sobre o seu código.** Vira uma frase
  conferível: *"este teste passa no seu código de hoje e quebra com a sua
  mudança"*. Você roda, você vê.

⚠️ **Onde ela não serve, e nós dizemos isso.** Quando a alteração cria algo que
não existia antes — uma rota nova, por exemplo —, o teste falha no código antigo
por **ausência**, não por defeito. Aí a prova diferencial não vale, e o sistema
precisa de outro caminho: um teste que falha só no código novo, ou uma
demonstração contra a aplicação rodando.

---

## 5. Os três desfechos, e por que o terceiro é o produto

Todo achado sai com um de três carimbos.

| | o que significa |
|---|---|
| **Provado** | há um artefato reproduzível anexado. É o que sustenta severidade alta, e é conferível sem confiar em nós |
| **Descartado** | a perícia olhou e refutou. Sai no parecer **com o motivo** |
| **Inconclusivo** | a ferramenta falhou, o modelo recusou, ou o defeito é de uma classe que as ferramentas disponíveis não alcançam. Sai **rotulado, com a causa** |

O terceiro carimbo é a decisão de produto mais importante que tomamos, e a mais
fácil de entender pelo avesso.

**Imagine que só existissem dois desfechos: provado e descartado.** Toda vez que
a ferramenta quebrasse, o modelo recusasse ou o teste não rodasse, o achado
cairia em "descartado". O relatório sairia dizendo *"examinei dez acusações e
refutei todas"* — e pareceria excelente. A categoria mais importante se esvazia
sozinha, e **o esvaziamento se parece com rigor.**

É uma absolvição falsa, e é exatamente o erro que o produto existe para impedir.
Por isso a regra está escrita em código, com teste, e não em prosa: **"não
consegui provar" nunca vira "não existe".**

Um exemplo real de inconclusivo honesto, da rodada de 14/08: a acusação era de
duplicação de dados quando duas requisições chegam ao mesmo tempo. A resposta do
advogado foi que a janela só ocorre com duas transações simultâneas, que as
ferramentas disponíveis são sequenciais, e que portanto **não há artefato
determinístico possível** — nem confirmado, nem derrubado. Ele não chutou, e não
escondeu.

> As listas de descartados e inconclusivos são a peça que nenhum concorrente
> entrega. Elas parecem confissão de fraqueza e são o contrário: dizer o que foi
> olhado e absolvido, e com que limite, é o que permite confiar no que foi
> condenado.

---

## 6. Um achado por extenso

Este é um achado real, publicado como comentário num pull request de verdade,
em 18/08/2026. O repositório é a nossa bancada de medição, e o defeito foi
plantado de propósito — mas o sistema não sabia disso, e o texto abaixo é o que
saiu, sem edição.

**O contexto, em português:** o código tinha uma verificação que dizia *"antes
de mostrar uma tarefa, confira se esta pessoa participa do projeto a que a
tarefa pertence"*. A alteração removeu essa verificação, com a justificativa —
escrita na própria documentação da função — de que *"ter o link já é sinal de
que a pessoa recebeu de alguém do projeto"*.

O parecer, verbatim:

```
[ALTA] [alta] correctness - app/main.py:104

O QUE: Remoção da verificação `t.project_id not in _projetos_visiveis(db, user)`
permite que qualquer usuário autenticado leia tarefas de projetos aos quais não
tem acesso, violando isolamento de projeto

ARBITRO: Ler uma tarefa exige poder ver o projeto a que ela pertence
         (docs/REGRAS.md - Acesso e isolamento)

EVIDENCIA: test_isolamento_tarefa.py passa em f3bdd65 e falha em 61cc0a7
           (exit 0 -> 1). Artefato: artefatos/prova_correcao_01.json

E TAMBEM: contra o app rodando --
  GET /projects como davi -> HTTP 200
  GET /tasks/1     como davi -> HTTP 200
  Artefato: artefatos/http_correcao_01.json

CONSERTO SUGERIDO: Restaurar em le_tarefa a condicao `if t is None or
t.project_id not in _projetos_visiveis(db, user): raise HTTPException(404)`,
e implementar compartilhamento por link com token opaco se o fluxo de chat for
realmente necessario.
```

Linha por linha, para quem não lê código:

- **`ARBITRO`** — a regra violada não foi inventada pelo modelo nem trazida de
  fora. Está escrita **no repositório do cliente**, no arquivo `docs/REGRAS.md`,
  e o sistema aponta onde. Se ele não conseguisse apontar onde a regra está
  escrita, este campo sairia vazio — e sair vazio é a resposta honesta para a
  maioria dos repositórios do mundo. A seção 8 conta o que custou aprender isso.
- **`EVIDENCIA`** — a prova diferencial da seção 4. O mesmo teste passa no
  commit anterior e falha no commit da alteração. `exit 0 -> 1` é literalmente o
  código de saída mudando de "sucesso" para "falha".
- **`E TAMBEM`** — a demonstração contra a aplicação de verdade, no ar. `davi`
  é uma conta que não participa daquele projeto. Ele pediu a tarefa número 1 e
  **recebeu**, com resposta HTTP 200, que quer dizer "aqui está".
- **`CONSERTO SUGERIDO`** — e o conserto não é genérico. Ele nomeia a função, a
  condição exata a restaurar, e reconhece a intenção legítima por trás da
  alteração, propondo o jeito seguro de fazer aquilo que o autor queria fazer.

**O que o autor do código recebeu:** 12 suspeitas foram levantadas pelos
promotores; 3 couberam no orçamento daquela rodada e foram testadas; 3 saíram
condenadas com evidência; 1 era duplicata e foi fundida antes da fila; 8 saíram
listadas como levantadas e **não testadas**, cada uma com sua posição na fila e
o motivo de não ter entrado.

Essa última lista importa: o parecer declara em voz alta o que ele **não**
olhou. Sem ela, um achado omitido por falta de orçamento seria indistinguível de
um achado que não existe.

A rodada inteira levou **136,5 segundos**.

### Outros três, mais curtos

**Carol leu um documento que não era dela.** Rodada de 14/08, na aplicação do
desafio. `carol` é uma conta que existe como controle negativo: ela não possui
nenhum documento. O advogado fez `alice` compartilhar um documento com `bob`, e
então pediu esse documento **como carol** — e recebeu HTTP 200. Três chamadas
encadeadas, com a regra do repositório citada com procedência. É o achado que
está na página inicial do produto.

**A refutação que corrigiu a acusação.** Na mesma rodada, o advogado não apenas
derrubou uma acusação: mostrou que ela estava com o **rótulo errado** —
*"o defeito real é o filtro invertido, uma divergência de PRD, não vazamento nem
injection como acusado"*. A refutação foi mais útil que a acusação original.

**O produto corrigiu o nosso gabarito.** Na medição de 15/08, um dos defeitos
plantados era uma condição de corrida, e nós tínhamos escrito no gabarito que o
resultado esperado era *inconclusivo* — partindo da premissa de que era
impossível provar. O sistema não tentou provar a corrida: sabia que não
conseguiria. Provou a **precondição** — que a garantia de unicidade do banco
tinha sido removida — com um teste que passa antes e falha depois. E saiu com
severidade **média**, não alta, porque a regra que rebaixa prova que não é ponta
a ponta funcionou sozinha. A limitação foi declarada no próprio motivo, não
escondida.

> A nossa premissa era falsa, e o produto encontrou um caminho que nós não
> tínhamos visto.

---

## 7. A medição com gabarito

A pergunta que um investidor faz, e com razão: *"como vocês sabem que isso
funciona, e não só que funciona no exemplo que vocês escolheram?"*

Em 15/08 construímos uma segunda aplicação — domínio deliberadamente diferente,
projetos e tarefas em vez de documentos compartilhados — e plantamos nela quatro
alterações, cada uma com um resultado esperado escrito **antes** de rodar. Os
defeitos foram escolhidos por taxonomia externa (CWE), não por intuição nossa.

| alteração | defeito plantado | esperado | resultado |
|---|---|---|---|
| tarefa por link | acesso indevido a objeto (CWE-639) | provado | **3 provados** ✅ |
| filtro de projetos | injeção de SQL (CWE-89) | provado | **2 provados**, 1 inconclusivo ✅ |
| reconvite de membro | condição de corrida (CWE-367) | inconclusivo | 2 provados, 1 refutado ❌ |
| contagem de tarefas | **nenhum** | refutado | **3 refutados** ✅ |

**Os quatro desfechos são diferentes entre si.** É o critério de um instrumento
calibrado: uma ferramenta que responde a mesma coisa para todas as entradas não
está medindo nada.

A linha mais importante da tabela é a última. **O pull request limpo teve três
acusações e zero condenações.** As refutações não foram genéricas: uma delas
derrubou uma premissa alucinada do promotor, apontando que a regra invocada era
de um banco de dados diferente e não se aplicava ali.

Isso importa mais do que parece. **Falso positivo é pior que defeito não
achado:** o autor que recebe uma acusação falsa desinstala a ferramenta e não
volta. O defeito não achado apenas mantém o estado atual do mundo.

A linha que não bateu está explicada em detalhe no arquivo da medição, e os três
erros eram do gabarito, não do produto — inclusive o caso da seção anterior, em
que a nossa premissa estava errada. Não escondemos a linha vermelha porque a
explicação dela é o dado mais informativo dos quatro.

⚠️ **E o limite, dito em voz alta:** quatro alterações provam que o instrumento
mede. Não provam que o produto acha defeito em código do mundo real. Confundir
as duas coisas seria repetir exatamente o erro da próxima seção.

---

## 8. A história do árbitro chumbado

Esta é a seção que um CTO deve ler com atenção, porque ela diz mais sobre como
trabalhamos do que qualquer número de acerto.

Em 08/08, logo depois do hackathon, comemoramos uma métrica. Rodamos o produto
em dez pull requests reais de projetos grandes — Flask, Django, httpx, Gin,
Next.js, Requests — e medimos quantas acusações vinham com um **árbitro**
preenchido, isto é, com a regra violada nomeada em vez de uma opinião solta.

O resultado pareceu ótimo: **94 acusações com árbitro preenchido**, de 209
levantadas.

Aí olhamos o conteúdo dos 94.

**93 deles citavam os critérios de aceite do desafio da Vindler** — o exercício
do hackathon — aplicados a repositórios que não têm absolutamente nada a ver com
ele. O nonagésimo quarto era a lista inteira de critérios copiada do prompt e
colada como se fosse um árbitro só.

Ou seja: **fora do exercício original, a taxa real de árbitro era zero.**

E tem uma camada pior. Os rótulos que o modelo citava — `AC1` a `AC5`, `R1` a
`R4` — **nunca existiram nem no desafio original.** Nós inventamos aquela
numeração ao escrever os prompts, mandamos o modelo citá-la "verbatim", e ele
obedeceu: passou a citar critérios inventados por nós como se fossem regras do
repositório de outra pessoa.

O caso mais constrangedor apareceu num pull request do `psf/requests` que
consertava **um link de markdown**. Uma linha. O sistema acusou o conserto de
ser o defeito, e um dos sobreviventes alegava, textualmente, que *"nenhum
requisito R1–R4 ou critério AC1–AC5 pode ser validado ou invalidado por esta
mudança"*. O advogado então **provou** aquilo — confirmou que um pull request de
documentação do `requests` de fato não satisfaz os critérios de aceite de outro
projeto. Verdade trivial, valor zero, e foi parar na lista de condenados.

### As três lições, que viraram regra permanente

**1. Preenchido não é válido.** A métrica contava campos não vazios. Todos os 94
estavam preenchidos, e todos com lixo reciclado. Desde então, toda métrica nova
neste projeto passa pela pergunta *"isto pode estar medindo outra coisa?"* — e
esse hábito já pegou erro várias vezes depois.

**2. Regra sem procedência é opinião.** O árbitro deixou de ser uma sigla e
virou uma citação com endereço: o arquivo e a linha, no repositório sob revisão,
onde a regra está escrita. Se o sistema não consegue apontar onde, o campo sai
**vazio** — e vazio é a resposta honesta para a maioria dos repositórios do
mundo, que não documentam suas regras.

**3. O que é do cliente entra em tempo de execução, nunca no prompt.** O que o
repositório documenta é lido do repositório, na hora. Aponte a configuração para
outro projeto e você revisa outro projeto, sem tocar em uma linha de código
nossa.

E a trava: existe um teste automatizado que verifica mecanicamente que nenhum
critério de projeto específico voltou para dentro dos prompts. **Prompt regride
em silêncio; asserção não.**

> É a mesma regra que rege este documento. Nenhum número entra sem endereço — e
> a ficha de procedência no fim existe para que você possa conferir cada um.

---

## 9. Doze bugs num dia

Em 18/08 o produto ganhou a última milha: o parecer virou comentário de pull
request, e o sistema inteiro passou a rodar sozinho na integração contínua. Para
chegar lá, doze defeitos nossos precisaram ser consertados no mesmo dia.

Vale contá-los porque **quase todos são a mesma família de erro**, e reconhecer
essa família é a habilidade que este projeto comprou caro.

**O padrão:** *a proteção existe, mas está condicionada ao mesmo sinal que ela
deveria vigiar. Então ela fica muda exatamente onde é necessária.*

Um exemplo concreto, sem jargão: uma verificação que checava se o teste bateu
com o resultado declarado, mas que só rodava **quando havia um teste**. Nos
casos em que a prova veio por outro caminho, a verificação simplesmente não
acontecia — e era justamente nesses casos que ela importava.

| o defeito | o que ensinou |
|---|---|
| caminho de pastas fixo no código | ferramenta que o projeto não declara deve **recusar dizendo**, em vez de falhar em silêncio |
| a regra confundindo "não declarada" com "quebrou" | precisa de três desfechos: funcionou / quebrou / não existe |
| o alarme do banco disparando sempre | **proteção pode morrer de excesso** — alarme que toca sempre ensina a ignorar |
| sete valores do projeto antigo como padrão | valor de exemplo deixado como reserva é cicatriz de migração, não robustez |
| caminho reescrito na hora de exibir | caminho normalizado é fato da rodada; carimbe no momento em que acontece |
| descrição lida de uma cópia sem arquivos | nem toda cópia de repositório tem os arquivos dentro |
| um argumento faltando em uma de oito chamadas | "sete de oito" ninguém percebe lendo |
| uma raiz só para configuração e código | são **duas**: a configuração vem de um lado, o código sob revisão do outro |
| tipo errado de credencial no download | protocolos vizinhos querem credenciais diferentes |
| pastas de trabalho criadas tarde demais | "preparar o ambiente" inclui preparar o ambiente inteiro |
| a regra tratando recusa como discordância | artefato que **nunca rodou** não derruba veredito |
| dependência externa desatualizada | era ferramenta de terceiro, não nossa |

### As três que mais valem

**1. A regra dava atestado de limpeza a uma vulnerabilidade real.** Na primeira
execução completa, o advogado achou o defeito e disse "provado" nas três
acusações. O parecer saiu dizendo *"nenhum achado sustentado por evidência"*. O
juiz leu o artefato, viu que ele não continha um teste bem-sucedido e derrubou —
só que aquele artefato era uma **recusa do classificador de segurança**, não um
teste discordando.

E o círculo fechava de um jeito quase cômico: o texto da recusa dizia
*"prove por leitura"*. **O advogado obedeceu, provou por leitura, e o juiz o
derrubou por ter obedecido.**

**2. A régua teria comemorado.** Nessa mesma execução, os vereditos internos do
advogado batiam com o gabarito. Quem medisse o sucesso olhando o arquivo interno
leria "acertou, 1 de 1" — enquanto o parecer, a única coisa que o cliente vê,
dava o defeito por inexistente.

> Régua olhando o lugar errado reporta sucesso com o instrumento quebrado.

É o erro dos 94 árbitros de novo, agora dentro da própria medição. A regra que
ficou: **pontue sempre pelo parecer, nunca pelo arquivo interno.**

**3. O corte pela raiz.** Descobrimos que **14 de 14** valores fixos no código
de configuração usavam um número ou caminho que o projeto original declarava —
e em nove deles a segunda aplicação declarava coisa diferente. Consertar os
valores um a um trataria o sintoma. O mecanismo era o **valor de reserva
existir**.

Duas travas novas, e nenhuma é uma lista mantida à mão: uma compara os dois
projetos irmãos entre si, e a outra carrega a configuração **sem projeto
nenhum** — a ausência de exemplo denuncia o valor herdado em milissegundos, sem
precisar de repositório, container ou dinheiro.

### E a regra que governa todas

**Toda proteção precisa ser vista falhando.** Proteção que nunca foi testada com
a violação injetada não é proteção, é decoração.

Isso se pagou no mesmo dia: das travas escritas para o conserto, uma passou
**verde com o defeito presente**. Ela observava a exceção certa vindo do lugar
errado. Foi descoberta porque alguém apagou uma linha de propósito para ver o
teste ficar vermelho — e ele não ficou.

> **Teste que acusa a coisa errada não vale mais que teste que não acusa nada.**

---

## 10. Estado hoje

Medido em 20/08/2026, salvo onde indicado.

| | |
|---|---|
| suíte de testes | **787 passando**, 1 pulado, 6 fora do modo rápido |
| custo por acusação verificada | **US$ 0,071** |
| custo de um pull request completo | **US$ 1,23 a US$ 1,38** |
| duração de uma rodada completa | **2 a 13 minutos**, conforme o tamanho |
| entrega ao usuário | comentário no pull request, publicado pela integração contínua |
| reconhecimento | 2º lugar no Hack2L, agosto de 2026 |
| código | aberto — `github.com/marianocho/hack2l` |

**A contenção funciona.** Um revisor automático que executa código pode destruir
aquilo que ele testa — e isso aconteceu conosco duas vezes, em 11/08. Numa
delas, a suíte de testes do commit anterior apagou o banco da aplicação: quatro
usuários e cinco documentos. O agente nunca julgou aquele código; para ele o
commit anterior é apenas um ponto de controle. **O desenho tratava o commit
anterior como referência inerte, e executar código não é inerte.**

A resposta não foi tentar adivinhar o que o código faz — adivinhar perdeu as
duas vezes. Foi impor a fronteira de fora: banco de dados descartável, rede sem
saída para a internet, cópia da aplicação durante a rodada, e um retrato do
banco antes e depois de cada execução.

Na rodada de 14/08, durante 161 segundos o agente enviou cargas de injeção, leu
documentos como outro usuário e compartilhou documentos entre contas. O banco
real ficou **idêntico, tabela por tabela** — conferido por duas vias
independentes que concordaram entre si.

---

## 11. O que ainda não sabemos

Um documento que só lista vitórias mede a habilidade de escrever documentos.
Estes são os buracos conhecidos, em ordem de importância.

**1. A taxa de aceitação tem zero medições.** De cada achado publicado, qual
fração o autor de fato conserta? É a métrica que prova a tese do produto, e
hoje não temos nenhuma medição dela. Tudo o que temos é gabarito nosso, em
repositório nosso. É o primeiro item da fila.

**2. Não há ainda um número sobre código de terceiros com gabarito.** As
medições com resposta conhecida foram feitas nas nossas duas aplicações. Rodar
em pull requests já integrados de projetos públicos — metade deles corrigindo
bugs conhecidos, o que dá um gabarito invertido de graça — é o experimento que
falta, e custa cerca de US$ 15.

**3. Condições de corrida continuam invisíveis.** Defeitos que só aparecem com
duas coisas acontecendo ao mesmo tempo não têm prova determinística com as
ferramentas atuais. O sistema diz isso em vez de chutar, o que é o
comportamento certo — mas é uma classe inteira de defeito que ele não alcança.

**4. Repositório muito grande ainda degrada.** Em projetos de grande porte, a
leitura fica lenta o bastante para estourar o tempo limite. A prioridade não é
resolver: é **falhar rotulado** em vez de morrer em silêncio.

**5. O parecer ainda parece um terminal.** O conteúdo está certo e a
apresentação não: rótulos em caixa alta, referências de arquivo que não são
links clicáveis, e caminhos de artefato que apontam para arquivos que o autor
não tem. É trabalho de acabamento, já mapeado item a item.

---

## 12. Ficha de procedência

Cada número deste documento e o arquivo onde ele mora. Todos os caminhos são
relativos à raiz do repositório `hack2l`.

| número | onde |
|---|---|
| 2º lugar no Hack2L, 08/08/2026 | `CLAUDE.md` |
| curl: >15% por anos, <5% em 2025, US$ 100 mil por 87 vulnerabilidades | `CLAUDE.md`, seção "Fatos de mercado" |
| US$ 0,071 por acusação verificada | `saidas/final/controle_negativo_11ago/LEIA.md` |
| 209 acusações em 10 pull requests; 94 com árbitro; 93 do vocabulário do desafio | `ACHADO_ARBITRO_CHUMBADO.md` |
| `psf/requests#7576`: 11 acusações, 7 refutadas, 2 inconclusivas, 2 provadas, US$ 0,61, 328s | `ACHADO_ARBITRO_CHUMBADO.md` |
| controle negativo 11/08: 0 condenados, 8 descartados com motivo, 0 inconclusivos, US$ 1,23, 9m35s, 30 chamadas de ferramenta sem erro | `saidas/final/controle_negativo_11ago/LEIA.md` |
| rodada 11/08: 10 condenados, 0 inconclusivos, US$ 1,38, 13m28s; recusas do classificador de 2 para 0 | `saidas/final/rodada_11ago_prova_readonly/LEIA.md` |
| banco apagado pela suíte do commit anterior: 4 usuários, 5 documentos | `saidas/final/controle_negativo_11ago/LEIA.md` |
| rodada 14/08: 6 acusações, 161s, 4 provados, 1 descartado, 1 inconclusivo | `saidas/final/rodada_14ago_contencao/LEIA.md` |
| banco real idêntico antes e depois da rodada de 14/08 | `saidas/rodadas/20260814T2131-1dd2e5c/efeito_no_banco.json` |
| medição com gabarito, 15/08: placar dos 4 pull requests; 145.190 tokens de entrada | `saidas/final/bancada_15ago/LEIA.md` |
| o produto corrigindo o gabarito na condição de corrida, severidade média | `saidas/final/bancada_15ago/LEIA.md` |
| parecer do `bancada#1`: 12 levantadas, 3 testadas, 3 condenados, 1 fundida, 8 não testadas | `saidas/rodadas/20260818T1928-61cc0a7/parecer.md` e `escopo.json` |
| rodada do `bancada#1`: 136,5 segundos | `saidas/rodadas/20260818T1928-61cc0a7/custo.json` |
| comentário publicado sem empilhar: 1 comentário após 2 rodadas, 5.590 caracteres | `HANDOFF_18AGO.md` |
| os doze bugs de 18/08 e as três lições | `HANDOFF_18AGO.md` |
| 14 de 14 valores fixos usando o valor do projeto original; 9 divergentes | `HANDOFF_18AGO.md` |
| suíte: 787 passando, 1 pulado, 6 fora do modo rápido | medido em 20/08/2026 — `py -3.12 -m pytest -q -m "not lento"` |

### O que este documento deliberadamente **não** afirma

- **Não dizemos "encontrou N dos M defeitos" em código de terceiros.** Seria uma
  alegação sobre um gabarito que não temos.
- **Não dizemos que nenhuma ferramenta do mercado faz análise de segurança em
  pull requests.** Faz — o Promptfoo Code Scanning verifica injeção de prompt e
  dados pessoais, por análise estática. A diferença que reivindicamos é
  específica: **executar para provar**, e publicar o que não conseguiu provar.
- **Não somamos inconclusivos com refutados.** Dizer "refutou tudo" quando
  nenhuma ferramenta funcionou é a absolvição falsa da seção 5, e já cometemos
  esse erro duas vezes nos nossos próprios relatórios.

---

*Veredito — revisão de código por prova. `contato@veredito.dev`*
