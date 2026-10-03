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
