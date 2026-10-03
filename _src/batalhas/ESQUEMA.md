# Ficha de batalha — esquema do JSON

Cada batalha do site é um arquivo `_src/batalhas/NN-slug.json`. O `build.py`
lê todos e gera `batalhas/<slug>.html` e o quadro da home. **Nenhum texto de
batalha mora em template.**

Fonte única do conteúdo: a apuração do episódio
(`Canais do YouTube\Xadrez Bélico\Roteiros\...` — `VERIFICACAO.md` na pasta do
episódio, ou `APURACAO NN - Tema.md` na pasta `Roteiros`, e as NOTAS DE
VERIFICAÇÃO / FONTES PRINCIPAIS no fim do roteiro). O roteiro dá o tom e a
ordem, nunca um número que a apuração não sustente.

```json
{
  "num": "02",
  "slug": "montese",
  "batalha": "Montese",
  "titulo_video": "texto exato do título do YouTube, ou null se o vídeo ainda não tem título",
  "lugar": "Montese, Módena, Itália",
  "data": "14 a 17 de abril de 1945",
  "campanha": "A FEB na Itália",          // fio do episódio
  "estreia": "2026-10-01",                 // ou null se não houver data
  "pergunta": "a pergunta do episódio, uma frase",
  "resumo": "120 a 155 caracteres (o build para fora disso); vira meta description",
  "abertura": ["2 parágrafos curtos"],
  "numeros": [                             // 4 a 6
    {"valor": "2h15", "rotulo": "para tomar a cidade", "conf": "2+"}
  ],
  "ficha": [                               // 8 a 16 linhas
    {"item": "Forças", "valor": "…", "conf": "2+|1|DIV|sem", "nota": "opcional"}
  ],
  "lances": [                              // 4 a 7: a batalha como partida
    {"titulo": "…", "paragrafos": ["…"]}
  ],
  "veredito": ["1 a 3 parágrafos: por que deu certo, ou não, do ponto de vista do tabuleiro"],
  "mitos": [ {"circula": "…", "registro": "…"} ],
  "fontes": [ {"texto": "…", "url": "https://… ou null"} ],
  "imagens": [                             // a primeira é a capa
    {"arquivo": "02-montese-capa.jpg", "alt": "…", "legenda": "…",
     "autor": "…", "licenca": "Domínio público", "licenca_url": "https://…",
     "origem_url": "https://… ou null",
     "tipo": "epoca",                      // "epoca" | "atual" | "carta"
     "ano": "1945",                        // obrigatório para "atual": vira tarja FOTO DE AAAA
     "foco": "50% 40%"}                    // opcional: object-position no recorte
  ],
  "proximo": "fornovo-di-taro"             // slug da próxima, ou null
}
```

`conf`: `2+` duas ou mais fontes independentes · `1` uma fonte (o texto diz
qual) · `DIV` as fontes divergem, o valor mostra as versões · `sem` ninguém
registrou.

## Campos opcionais de busca e navegação (03/10/2026)

- `"nome_busca": "Batalha de Stalingrado"` — o nome como as pessoas buscam a
  batalha (autocomplete do Google em pt-BR). Entra só no `<title>`, no lugar
  de `batalha`; o h1 e o resto da página não mudam. O padrão
  `nome (anos), lance a lance · Xadrez Bélico` continua, com as mesmas travas.
- `"relacionados": ["slug", "slug", "slug"]` — o bloco "Leia também" no fim da
  página: três batalhas de assunto próximo (Frente Oriental, Guerra do
  Paraguai, FEB, Pacífico…). O build para se um slug não existir, repetir,
  for a própria batalha ou for o `proximo`.

Imagens: o build gera sozinho a cópia `.webp` de cada JPEG (e da versão
`-800`) e serve as duas num `<picture>`.

## Perguntas frequentes e páginas de tema (03/10/2026)

- `"perguntas": [{"p": "Pergunta como se busca?", "r": "Resposta de 1 a 3 frases."}]`
  (opcional, 3 a 5 itens, logo antes de `fontes`) — vira a seção "Perguntas
  frequentes" (âncora `#perguntas`), depois dos mitos e antes das fontes, e
  entra no índice "Nesta página". As perguntas saem das buscas reais (autocomplete
  do Google em pt-BR: "como foi construído…", "quantas pessoas morreram…",
  "quem venceu…", "por que … perdeu…"). **A resposta só repete o que a página já
  diz**: nenhum fato novo; divergência continua divergência ("as fontes
  divergem: X ou Y"); onde a página diz que não há registro, a resposta diz
  isso. O build para se faltar "?", se houver menos de 3 ou mais de 5 itens, ou
  se aparecer termo de bastidor (a mesma trava do resto da página). Sem
  JSON-LD de FAQ, de propósito.
- `_src/temas.json` — as páginas-índice `temas/<slug>.html`: `slug`, `nome`
  (o h1), `titulo` (o `<title>`; a marca entra no fim se couber em 60),
  `resumo` (a description, 120–155), `intro` (2 ou 3 parágrafos, só com o
  que as páginas do grupo dizem) e `batalhas` (a lista de slugs, 2 ou mais). O
  build gera a página com cartões, CollectionPage + BreadcrumbList, imagem de
  compartilhamento própria (`og-tema-<slug>.jpg`), põe no sitemap, lista na
  home (seção `#temas`) e linka o tema no bloco "Leia também" de cada batalha do
  grupo. Para se um slug não existir, repetir, ou se o texto tiver bastidor.

## Traduções (03/10/2026)

Arquivos paralelos, **mesmo nome** do original:

```
_src/batalhas/NN-slug.json        português (a fonte; manda sempre)
_src/batalhas/en/NN-slug.json     inglês
_src/batalhas/es/NN-slug.json     espanhol
_src/temas.en.json                    temas em inglês (opcional)
_src/i18n/en.json                     textos da interface em inglês
_src/paginas/en/sobre.html            Sobre, Contato e Privacidade em inglês (só o <main>)
```

**A tradução tem os mesmos campos e as mesmas listas, na mesma ordem e com o
mesmo número de itens** (mesmas seções, mesmos parágrafos, mesmas linhas de
ficha, mesmas imagens). O build confere campo a campo (`fundir_traducao`).

- **Campos fixos** — num, slug, estreia, proximo, relacionados, conf, arquivo, licenca, licenca_url, origem_url, tipo, ano, foco, url: não se traduzem. Podem ser omitidos
  (vêm do original); se estiverem, têm de ser idênticos.
- **Opcionais só da tradução**: `nome_busca` (o nome como se busca naquele
  idioma), `_nota` (comentário, não publicado) e `_excecoes_numeros`.
- `autor` das imagens e `texto` das fontes podem ficar iguais ao original
  (nome próprio, título de obra citada); o resto, com 25 caracteres ou mais,
  igual ao português é tratado como "não traduzido" e para o build.

### Conferência de números

Todo número do original tem de aparecer no mesmo campo da tradução, e a
tradução não pode ter número que o original não tem. A comparação normaliza:

| português | inglês | conta como |
|---|---|---|
| `1.145` / `3,75` | `1,145` / `3.75` | 1145 / 3.75 |
| `20 mil`, `1,5 milhão` | `20,000`, `1.5 million` | 20000, 1500000 |
| `250–300 mil` | `250,000–300,000` | 250000 e 300000 |
| `3/11/1924` | `3 November 1924` | 3, mês 11, 1924 |
| `12 de outubro` | `12 October` / `October 12` | 12, mês 10 |

O mês por extenso conta como número (só na caixa da ortografia: minúsculo em
pt/es, maiúsculo em en — "Rio de Janeiro" não é janeiro). Número escrito por
extenso ("cinco anos") não é conferido: mantenha por extenso. Exceção legítima
(raro): liste o número em `"_excecoes_numeros": ["1.000"]` na tradução — ele
deixa de ser conferido nos dois lados.

### Textos da interface: `_src/i18n/<id>.json`

```json
{
  "_idioma": {"nome": "English", "curto": "EN", "hreflang": "en", "og_locale": "en_US",
              "marca_sub": "War as a Chess Game",
              "meses": ["January", "…"], "meses_curtos": ["Jan", "…"],
              "data_longa": "{mes} {dia}, {ano}", "data_curta": "{mes} {dia:02d}, {ano}"},
  "textos": {"Leia também": "Read next", "Detalhes na {politica}.": "Details in our {politica} (in Portuguese)."}
}
```

A **chave é o próprio texto em português** que está no build. Mudou o texto
em português, a tradução deixa de casar e o build para listando o que falta
(e avisa das chaves que ficaram sobrando). Os marcadores `{…}` têm de ser os
mesmos dos dois lados. Datas por extenso saem de `data_longa`/`data_curta`.

