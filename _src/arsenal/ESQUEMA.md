# Ficha do arsenal — esquema do JSON

Cada peça (tanque, avião, blindado, navio, canhão) é um arquivo
`_src/arsenal/<slug>.json`. O `build.py` lê todos e gera
`arsenal/<slug>.html`, o índice `arsenal/index.html` (servido em `/arsenal/`),
a seção "Arsenal" da home e o bloco "As peças" nas páginas das batalhas
citadas. **Nenhum texto de ficha mora em template.**

Vale o método do site: **cada número leva selo e a fonte fica dita** (no
próprio valor, na `nota` ou na lista de `fontes`). Livro e fonte primária
(manual técnico, relatório de ensaio, museu) antes de Wikipédia; quando a
Wikipédia é o caminho até um livro, a fonte diz "citado por". Fontes que
divergem ficam `DIV`, com as versões. O que ninguém registrou fica `sem`.

O que a ficha diz sobre uma **batalha** só repete o que a página da batalha
já diz (que vem da apuração do episódio). Dado técnico novo entra na ficha
com fonte própria.

```json
{
  "slug": "sherman",                      // = nome do arquivo; vira arsenal/sherman.html
  "nome": "M4 Sherman",                   // o h1
  "nome_busca": "Tanque Sherman",         // opcional: só no <title>
  "classe": "tanque",                     // tanque | blindado | aviao | navio | canhao
  "papel": "tanque médio",                // uma linha: o que a peça é
  "pais": "Estados Unidos",
  "periodo": "1942–1945",                 // em serviço (no recorte da ficha)
  "pergunta": "a pergunta da ficha, uma frase",
  "resumo": "120 a 155 caracteres; vira meta description",
  "abertura": ["1 a 3 parágrafos curtos"],
  "numeros": [                            // 4 a 6: o placar
    {"valor": "49.234", "rotulo": "…", "conf": "2+"}
  ],
  "ficha": [                              // 8 a 16 linhas: a ficha técnica
    {"item": "Blindagem", "valor": "…", "conf": "2+|1|DIV|sem", "nota": "opcional: a fonte, a ressalva"}
  ],
  "secoes": [                             // 2 a 5: a peça no tabuleiro
    {"titulo": "Para que servia", "paragrafos": ["…"]},
    {"titulo": "Pontos fortes", "paragrafos": ["…"]},
    {"titulo": "Pontos fracos", "paragrafos": ["…"]}
  ],
  "batalhas": [                           // 1 ou mais: "Em quais batalhas jogou"
    {"slug": "montese", "texto": "o que a peça fez ali, só com o que a página da batalha diz"}
  ],
  "veredito": ["1 a 3 parágrafos: o que a peça valia no tabuleiro"],
  "mitos": [ {"circula": "…", "registro": "…"} ],        // 1 a 5
  "perguntas": [ {"p": "…?", "r": "…"} ],                // opcional, 3 a 5
  "fontes": [ {"texto": "…", "url": "https://… ou null"} ],  // 3 ou mais
  "imagens": [],                          // pode ficar vazia: a ficha sai sem foto
  "relacionados": ["bf-109"]              // opcional: 1 a 3 outras fichas ("Outras peças")
}
```

`conf`, `mitos`, `perguntas`, `fontes` e `imagens` seguem as mesmas regras de
`_src/batalhas/ESQUEMA.md` (a primeira imagem é a capa; `tipo` `epoca`,
`carta` ou `atual` com `ano`; licença domínio público, CC0, CC BY ou CC BY-SA).
Imagem já usada numa batalha pode ser reaproveitada, com a mesma ficha de
crédito e legenda própria. Fotos novas ficam em `assets/img/arsenal-<slug>.jpg`
(1600 px, JPEG 82) e `arsenal-<slug>-800.jpg`. Se a primeira imagem tiver
menos de 1200 px de largura, ela não vira capa de tela cheia: a ficha abre
sem capa e a foto entra como figura no corpo.

## O build para quando

- falta campo, a classe não existe, o nome do arquivo não bate com o slug;
- uma lista sai do tamanho (números 4–6, ficha 8–16, seções 2–5, fontes 3+);
- um número ou linha de ficha não tem `conf` válido;
- `batalhas` está vazia, repete ou aponta para batalha que não existe;
- `relacionados` aponta para ficha que não existe;
- imagem fora das regras (as mesmas das batalhas);
- o texto público carrega bastidor de produção;
- o título passa de 60 ou a description sai de 120–155 ou repete.

## Ligações

- **Ficha → batalha:** a seção "Em quais batalhas jogou", com o texto de
  `batalhas[].texto` e link para a página do episódio.
- **Batalha → ficha:** o bloco "As peças", logo depois da ficha da batalha,
  sai sozinho para toda batalha citada em alguma ficha. Não se mexe no JSON
  da batalha.

## Traduções

Mesmo desenho das batalhas: `_src/arsenal/en/<slug>.json` e
`_src/arsenal/es/<slug>.json`, mesmo nome de arquivo, mesmas listas, com a
conferência de números campo a campo. `slug`, `classe`, `conf`,
`relacionados` e os campos fixos de imagem e fonte vêm do original. A ficha
só existe no idioma em que foi traduzida: o índice, o menu, a seção da home
e o bloco "As peças" só aparecem ali quando há pelo menos uma. Os textos da
interface do arsenal (títulos de seção, nomes de classe) entram em
`_src/i18n/<id>.json` — o build lista os que faltarem.
