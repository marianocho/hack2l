<!-- tag: hack2l -->

# Pitch — 3 minutos

Critérios com **pesos iguais**: protótipo · viabilidade como startup · pitch ·
criatividade. Três dos quatro são negócio e apresentação.

3 minutos falados ≈ **420 palavras**. O roteiro abaixo tem marcas de tempo. O
bloco de demo é o maior de propósito: o que vende é a tela, não a fala.

---

## Roteiro

### 0:00–0:25 — O problema, com número verificado

> "Em janeiro deste ano o **curl fechou o programa de bug bounty**. Não foi falta
> de dinheiro: pagaram cem mil dólares por oitenta e sete vulnerabilidades. Foi
> que a taxa de confirmação, que ficou acima de 15% por anos, **caiu abaixo de 5%
> em 2025** — enterrada numa enxurrada de relatórios gerados por IA. Confiantes,
> bem escritos, e falsos.
>
> Imprecisão de IA já fechou instituição. Esse é o problema."

### 0:25–0:50 — Why now + a tese

> "E a categoria está sendo comprada: em dezembro a **Cursor comprou a Graphite**,
> acima da avaliação de duzentos e noventa milhões.
>
> Só que todo revisor de IA hoje faz a mesma coisa: **afirma**. 'Isso parece uma
> vulnerabilidade.' Ninguém prova.
>
> O Veredito trata cada suspeita como acusação: **nada vira parecer sem prova
> reproduzível.**"

### 0:50–1:05 — O que é, em uma frase

> "Promotores acusam. Um advogado **testa** — ele não argumenta, ele executa. E um
> juiz sentencia com regras determinísticas.
>
> A peça central é a **prova diferencial**: o mesmo teste roda no commit base e no
> head do PR. Só é provado se **passa antes e falha depois**. O veredito final é
> um **exit code**, não opinião de modelo."

### 1:05–2:15 — DEMO (o bloco maior; mostrar, não contar)

Três telas, nesta ordem. Cada uma tem uma frase.

**1. Um achado provado.**
> "Este é o artefato. Exit code zero no código de hoje, exit code um com a
> mudança. Isso não é o modelo dizendo que achou — é o teste falhando."

**2. O mesmo tipo de achado, um nível abaixo.**
> "Este cheirou mal e não fechou. Vira **suspeita rotulada**, mostrando o que foi
> tentado. Não vira alarme."

**3. As duas listas que ninguém mais tem.**
> "Toda ferramenta te enche de alarme falso até você parar de ler. Esta te mostra
> **o que descartou e por quê**. E esta — a de inconclusivos — é a mais
> importante.
>
> Hoje de manhã o app alvo estava sem chave de modelo. Os payloads de injection
> não podiam funcionar, porque não havia modelo para desobedecer. Um revisor
> comum teria escrito **'injection: refutado'** — seis vezes, com aparência de
> rigor. O Veredito detectou que **não conseguia observar** e se recusou a
> absolver. Marcou inconclusivo, com a causa.
>
> **Ausência de observação não é prova de ausência.** Essa regra é código, não
> intenção."

### 2:15–2:40 — Diferenciação (a frase corrigida)

> "Existe quem escaneie prompt injection em PR — a **Promptfoo** faz, com análise
> estática de fluxo de dados. **Ninguém executa o ataque para provar que é
> alcançável.** É a diferença entre 'este padrão é arriscado' e 'eu disparei este
> payload pela API e olha o trace'.
>
> E o ICSE deste ano teve um trabalho com enquadramento multiagente parecido. Lá
> os agentes **debatem por escrito**. Aqui o verificador **executa**, e o veredito
> é um exit code."

### 2:40–3:00 — Negócio e fecho

> "Custo por PR revisado: **[X dólares]**, medido, no log.
>
> Reduzir alarme falso não basta — toda ferramenta promete isso. O que faz o dev
> voltar a ler é ver **o que foi descartado e por quê**. É isso que transforma
> revisão em **laudo**.
>
> E laudo tem comprador que 'revisão melhor' não tem: **segurança e auditoria**.
> Um parecer com prova reproduzível e trilha do que foi descartado é artefato de
> compliance.
>
> E revisar **código de agente** é classe nova de defeito: nenhum incumbente tem
> oráculo para 'este PR quebrou o isolamento de tenant no RAG'.
>
> Todo mundo afirma. Nós provamos."

### ⚠️ Por que o fecho é assim, e não "zero ruído"

A versão anterior usava a frase do `CLAUDE.md` — *"'menos ruído no PR' não tem
comprador"* — noventa segundos depois de vender a lista de descartados na Tela 3.
Logicamente compatível (uma fala é sobre auditabilidade, a outra sobre quem
assina o cheque), mas num pitch **falado** a mesma palavra com duas valências
tropeça. Corrigido.

**Não trocar por "provamos com zero ruído".** É a alegação mais falsificável do
pitch: morre apontando para a lista de SUSPEITAS que está projetada na tela
atrás de você. Pior que "achou 4 dos 5 defeitos", porque não precisa nem de
gabarito para ser derrubada.

A cadeia correta é: lista de descartados → o dev volta a confiar → confiança
vira laudo → laudo tem comprador em compliance. Ruído entra como **mecanismo**,
nunca como promessa.

---

## 🚫 Não falar (não verificado — um número errado se autodestrói)

- "18,6% no PrimeVul Paired"
- "HackerOne pausou o IBB em março de 2026"
- "nenhuma ferramenta do mercado faz isso" — **falso**, a Promptfoo faz estático
- "exatamente a mesma arquitetura do VulTrial"
- **"encontrou 4 dos 5 defeitos"** — não existe gabarito. Dizer alegação sobre
  gabarito que não temos destrói a tese na mesma frase.

## ✅ Falar assim

> "Provou N achados com artefato reproduzível, descartou M com motivo, e marcou K
> como inconclusivos com a causa."

Verdade, está na tela, e é mais forte que qualquer porcentagem.

---

## Se perguntarem

**"Isso não está calibrado pro PR de vocês?"**
> "Os seis promotores foram escritos sem ninguém ler o diff. Tem um teste que
> roda os seis contra um diff fictício — `testar_promotores.py`. Troca o PR, o
> agente continua funcionando."

**"E se o agente errar?"**
> "Erra. Por isso a severidade acompanha a **força da prova**, não a gravidade
> teórica. Crítica sem árbitro citado é rebaixada automaticamente. Prova que não
> é ponta a ponta não sustenta severidade alta. São três regras em código."

**"Quanto custa?"**
> "[X] por PR. Haiku gera hipóteses, Opus verifica, Sonnet sintetiza — modelo
> caro só onde a decisão acontece."

**"Roda em CI?"**
> Honesto: "Hoje roda contra um app subido localmente. Disparar payload real
> contra ambiente de cliente pede sandbox efêmero — é o próximo problema, e é de
> engenharia, não de pesquisa."
