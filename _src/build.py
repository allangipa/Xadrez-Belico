#!/usr/bin/env python3
"""Gera o site do Xadrez Bélico.

    python _src/build.py        (a partir da raiz do site)

Lê cada batalha de `_src/batalhas/NN-slug.json` (esquema em
`_src/batalhas/ESQUEMA.md`) e escreve, na raiz:

    index.html  batalhas/<slug>.html  404.html
    sitemap.xml  robots.txt  assets/xadrez.css  assets/img/og-*.jpg

Nunca edite os .html gerados: o próximo build apaga a mudança.

Mesmo desenho do site do Arquitetura do Impossível, e o build é porteiro do
mesmo jeito. Ele PARA quando:
  - falta campo obrigatório, ou `proximo` aponta para batalha inexistente;
  - uma imagem citada não existe em assets/img;
  - a licença não é das aceitas (NC e "no known copyright" não entram);
  - uma imagem é gerada por IA (o site só mostra material real), ou é foto
    de hoje sem o ano — a tarja "FOTO DE AAAA" é regra da casa;
  - o texto público carrega bastidor de produção.
"""
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "_src"
IMG = RAIZ / "assets" / "img"

DOMINIO = "https://xadrezbelico.com.br"
# Endereço do canal no YouTube. None = os botões dizem "em breve no YouTube",
# sem link — melhor que apontar para um @ que pode não ser o do canal.
CANAL = None
NOME = "Xadrez Bélico"

# Episódios anunciados que ainda não têm página.
EM_PRODUCAO = [
    {
        "num": "05",
        "batalha": "A queda da França",
        "data": "maio e junho de 1940",
        "lugar": "França",
        "pergunta": "O episódio seguinte à Polônia, em produção.",
        "estreia": "2026-10-22",
    },
]

OBRIGATORIOS = ["num", "slug", "batalha", "titulo_video", "lugar", "data", "campanha",
                "estreia", "pergunta", "resumo", "abertura", "numeros", "ficha",
                "lances", "veredito", "mitos", "fontes", "imagens", "proximo"]

LICENCAS_OK = re.compile(r"^(dom[ií]nio p[uú]blico|public domain|cc0|cc by(-sa)? \d\.\d( [a-z]{2,3})?|pd[- ].*)$", re.I)
BASTIDOR = re.compile(
    r"VERIFICACAO|VERIFICAÇÃO\.md|APURACAO|\ba apurar\b|\bconferir\b|\brodada \d|\[2\+\]|\[DIV\]|\[1\]"
    r"|\.md\b|\.tsv\b|MANIFESTO|\broteiro\b|\bbloco \d|n[ãa]o usar\b|n[ãa]o afirmar", re.I)
TIPOS = {"epoca", "carta", "atual"}

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_LONGO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
               "setembro", "outubro", "novembro", "dezembro"]

CONF = {
    "2+": ("conf-2", "2+ fontes", "Confirmado em duas ou mais fontes independentes."),
    "1": ("conf-1", "1 fonte", "Uma fonte só; o texto diz qual."),
    "DIV": ("conf-div", "diverge", "As fontes discordam; mostramos as versões e não escolhemos."),
    "sem": ("conf-sem", "sem registro", "Ninguém registrou. Dizemos isso em vez de inventar."),
}

e = lambda s: html.escape(str(s), quote=True)


def para(s):
    t = e(s)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    return t


def data_br(iso, longa=False):
    d = dt.date.fromisoformat(iso)
    if longa:
        return f"{d.day} de {MESES_LONGO[d.month-1]} de {d.year}"
    return f"{d.day:02d} {MESES[d.month-1]} {d.year}"


def falha(msg):
    raise SystemExit("PARADO: " + msg)


def link_canal(classe, texto, sem_link="Em breve no YouTube"):
    if CANAL:
        return f'<a class="{classe}" href="{CANAL}" rel="noopener">{e(texto)}</a>'
    return f'<span class="{classe}" aria-disabled="true">{e(sem_link)}</span>'


# --- carga e conferência ----------------------------------------------------
def carregar():
    bs = []
    for f in sorted((SRC / "batalhas").glob("[0-9][0-9]-*.json")):
        try:
            b = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as ex:
            falha(f"{f.name} não é JSON válido: {ex}")
        falta = [c for c in OBRIGATORIOS if c not in b]
        if falta:
            falha(f"{f.name} sem os campos {falta}")
        if f.name != f"{b['num']}-{b['slug']}.json":
            falha(f"{f.name}: nome do arquivo não bate com num/slug")
        if b["estreia"]:
            dt.date.fromisoformat(b["estreia"])
        if not b["imagens"]:
            falha(f"{f.name}: precisa de pelo menos uma imagem (a capa)")
        for im in b["imagens"]:
            for k in ("arquivo", "alt", "legenda", "autor", "licenca", "tipo"):
                if not im.get(k):
                    falha(f"{f.name}: imagem sem '{k}': {im.get('arquivo')}")
            if im["tipo"] not in TIPOS:
                falha(f"{f.name}: tipo de imagem inválido {im['tipo']!r} (gerada por IA não entra no site)")
            if im["tipo"] == "atual" and not re.fullmatch(r"\d{4}", str(im.get("ano", ""))):
                falha(f"{f.name}: foto atual sem 'ano' em {im['arquivo']} — a tarja precisa dele")
            if not (IMG / im["arquivo"]).exists():
                falha(f"{f.name}: imagem inexistente assets/img/{im['arquivo']}")
            if re.search(r"\bNC\b|no known copyright", im["licenca"], re.I) or not LICENCAS_OK.match(im["licenca"].strip()):
                falha(f"{f.name}: licença não aceita em {im['arquivo']}: {im['licenca']!r}")
        for n in b["numeros"] + b["ficha"]:
            if n.get("conf") not in CONF:
                falha(f"{f.name}: conf inválido {n.get('conf')!r} em {n}")
        texto = json.dumps({k: v for k, v in b.items() if k not in ("imagens", "fontes", "titulo_video")}, ensure_ascii=False)
        texto += " ".join(i["legenda"] + " " + i["alt"] for i in b["imagens"])
        m = BASTIDOR.search(texto)
        if m:
            ctx = texto[max(0, m.start() - 60):m.end() + 60]
            falha(f"{f.name}: bastidor de produção no texto público ({m.group(0)!r}): …{ctx}…")
        bs.append(b)
    slugs = {b["slug"] for b in bs}
    for b in bs:
        if b["proximo"] and b["proximo"] not in slugs:
            falha(f"{b['slug']}: proximo '{b['proximo']}' não existe")
    if not bs:
        falha("nenhuma batalha em _src/batalhas")
    return bs


# --- peças comuns -------------------------------------------------------------
def cabeca(titulo, descricao, url, imagem, base, jsonld, tipo="website"):
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{e(url)}">
<meta name="theme-color" content="#171310">
<link rel="icon" href="{base}assets/marca/cavalo-64.png" type="image/png">
<link rel="apple-touch-icon" href="{base}assets/marca/cavalo-180.png">
<link rel="preload" href="{base}assets/fontes/libre-baskerville-latin-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{base}assets/xadrez.css">
<meta property="og:type" content="{tipo}">
<meta property="og:site_name" content="{e(NOME)}">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(imagem)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
<body>
<a class="pular" href="#conteudo">Pular para o conteúdo</a>
"""


def topo(base, atual=""):
    cur = lambda k: ' aria-current="page"' if k == atual else ""
    return f"""<header class="topo">
  <div class="casca">
    <a class="marca" href="{base}index.html"><img src="{base}assets/marca/cavalo-128.png" width="40" height="40" alt=""><span>Xadrez Bélico</span></a>
    <nav class="nav" aria-label="Principal">
      <a href="{base}index.html#batalhas"{cur('batalhas')}>Batalhas</a>
      <a href="{base}index.html#metodo"{cur('metodo')}>Método</a>
      {link_canal('yt', 'YouTube', 'YouTube em breve')}
    </nav>
  </div>
</header>
"""


def rodape(base):
    ano = dt.date.today().year
    canal = f'<p><a href="{CANAL}" rel="noopener">Assista no YouTube</a></p>' if CANAL else ""
    return f"""<footer class="rodape">
  <div class="casca">
    <div>
      <h4>Xadrez Bélico</h4>
      <p>Batalha explicada como partida: terreno, peças, lances e o erro de planejamento. Não é canal de heroísmo, é canal de causa.</p>
      {canal}
    </div>
    <div>
      <h4>Do mesmo criador</h4>
      <ul>
        <li><a href="https://vestigiooculto.com.br" rel="noopener">Vestígio Oculto</a> — arqueologia e mistério</li>
        <li><a href="https://arquiteturadoimpossivel.com.br" rel="noopener">Arquitetura do Impossível</a> — como as grandes obras foram erguidas</li>
      </ul>
    </div>
    <div>
      <h4>Este site</h4>
      <ul>
        <li>Não usa cookies nem rastreamento.</li>
        <li>Só material de época ou foto real, com crédito. Nenhuma imagem gerada por IA.</li>
      </ul>
    </div>
    <div class="linha"><span>© {ano} {NOME} · textos autorais</span><span>o que estava à vista, lido de novo</span></div>
  </div>
</footer>
"""


SCRIPT = (RAIZ / "_src" / "pagina.js").read_text(encoding="utf-8") if (RAIZ / "_src" / "pagina.js").exists() else ""


def fim():
    return f"<script>\n{SCRIPT}\n</script>\n</body>\n</html>\n"


def conf_selo(c):
    cls, txt, tit = CONF[c]
    return f'<span class="conf {cls}" title="{e(tit)}">{e(txt)}</span>'


def img_tag(arquivo, alt, base, tamanhos="100vw", carregar="lazy", foco=None):
    nome = Path(arquivo).stem
    w, h = Image.open(IMG / arquivo).size
    srcset = ""
    if (IMG / f"{nome}-800.jpg").exists():
        srcset = f' srcset="{base}assets/img/{nome}-800.jpg 800w, {base}assets/img/{arquivo} {w}w" sizes="{tamanhos}"'
    st = f' style="object-position:{e(foco)}"' if foco else ""
    return (f'<img src="{base}assets/img/{e(arquivo)}"{srcset} width="{w}" height="{h}" '
            f'alt="{e(alt)}" loading="{carregar}" decoding="async"{st}>')


def tarja(im):
    """A tela diz o que a imagem não é: foto de hoje leva o ano."""
    if im["tipo"] == "atual":
        return f'<span class="tarja">Foto de {e(im["ano"])}</span>'
    return ""


def credito(im):
    lic = e(im["licenca"])
    if im.get("licenca_url"):
        lic = f'<a href="{e(im["licenca_url"])}" rel="license noopener">{lic}</a>'
    autor = e(im["autor"])
    if im.get("origem_url"):
        autor = f'<a href="{e(im["origem_url"])}" rel="noopener">{autor}</a>'
    return f"{autor} · {lic}"


def selo_estreia(iso, classe="selo"):
    if not iso:
        return ""
    return f'<span class="{classe}" data-estreia="{iso}" data-no-ar="No ar">Estreia {e(data_br(iso))}</span>'


# --- imagem de compartilhamento -----------------------------------------------
def fonte(nome, tam):
    return ImageFont.truetype(str(SRC / "marca" / nome), tam)


def og_batalha(b):
    destino = IMG / f"og-{b['slug']}.jpg"
    capa = Image.open(IMG / b["imagens"][0]["arquivo"]).convert("RGB")
    im = ImageOps.fit(capa, (1200, 630), Image.LANCZOS, centering=(0.5, 0.45))
    im = Image.blend(im, ImageOps.colorize(ImageOps.grayscale(im), (23, 19, 16), (227, 210, 170)), 0.55)
    sombra = Image.new("L", (1, 630))
    for y in range(630):
        sombra.putpixel((0, y), int(245 * min(1, max(0, (y - 150) / 330)) ** 1.1))
    im = Image.composite(Image.new("RGB", im.size, (23, 19, 16)), im, sombra.resize((1200, 630)))
    d = ImageDraw.Draw(im)
    d.text((58, 372), f"EPISÓDIO {b['num']}  ·  {b['data'].upper()}", font=fonte("rotulo.ttf", 26), fill=(217, 151, 63))
    tam = 76
    while tam > 40 and d.textlength(b["batalha"].upper(), font=fonte("titulo.ttf", tam)) > 1084:
        tam -= 4
    d.text((54, 412), b["batalha"].upper(), font=fonte("titulo.ttf", tam), fill=(227, 210, 170))
    d.text((58, 530), "X A D R E Z   B É L I C O", font=fonte("rotulo.ttf", 30), fill=(217, 151, 63))
    esc = Image.open(SRC / "marca" / "escudo-original.jpg").convert("RGB")
    esc.thumbnail((150, 185), Image.LANCZOS)
    im.paste(esc, (1200 - esc.width - 50, 630 - esc.height - 40))
    im.save(destino, "JPEG", quality=84, optimize=True, progressive=True)
    return destino.name


def og_home():
    destino = IMG / "og-home.jpg"
    ImageOps.fit(Image.open(SRC / "marca" / "banner.jpg").convert("RGB"), (1200, 630), Image.LANCZOS).save(
        destino, "JPEG", quality=86, optimize=True, progressive=True)
    return destino.name


# --- home ------------------------------------------------------------------------
def card(b, base):
    capa = b["imagens"][0]
    return f"""<li class="card revela">
  <div class="foto">{img_tag(capa['arquivo'], capa['alt'], base, '(max-width:720px) 100vw, 400px', foco=capa.get('foco'))}
    <span class="num">{e(b['num'])}</span>
    {selo_estreia(b['estreia'], 'selo')}
  </div>
  <div class="corpo">
    <span class="rotulo">{e(b['campanha'])}</span>
    <h3><a href="{base}batalhas/{b['slug']}.html">{e(b['batalha'])}</a></h3>
    <div class="quando">{e(b['data'])} · {e(b['lugar'])}</div>
    <p class="perg">{para(b['pergunta'])}</p>
    <div class="pe"><span>Episódio {e(b['num'])}</span><span>Ler a partida →</span></div>
  </div>
</li>"""


def card_producao(a):
    return f"""<li class="card producao revela">
  <div class="foto"><span class="num">{e(a['num'])}</span><span class="selo">Em produção</span></div>
  <div class="corpo">
    <h3>{e(a['batalha'])}</h3>
    <div class="quando">{e(a['data'])} · {e(a['lugar'])}</div>
    <p class="perg">{para(a['pergunta'])}</p>
    <div class="pe"><span>Episódio {e(a['num'])}</span><span>{('Estreia ' + e(data_br(a['estreia']))) if a.get('estreia') else ''}</span></div>
  </div>
</li>"""


def home(bs, og):
    base = ""
    nomes = {"2+": "Confirmado", "1": "Fonte única", "DIV": "Divergência", "sem": "Sem registro"}
    graus = "".join(f"<li>{conf_selo(k)}<p><strong>{nomes[k]}</strong>{e(v[2])}</p></li>" for k, v in CONF.items())
    jsonld = {"@context": "https://schema.org", "@type": "WebSite", "name": NOME, "url": DOMINIO + "/",
              "inLanguage": "pt-BR", "description": "História militar explicada como partida de xadrez."}
    cards = "\n".join(card(b, base) for b in bs) + "\n" + "\n".join(card_producao(a) for a in EM_PRODUCAO)
    return (cabeca(f"{NOME} — a batalha explicada como partida",
                   "História militar lida como tabuleiro: terreno, peças, lances e o erro de planejamento. Por que o ataque deu certo, ou não deu. Com fonte.",
                   DOMINIO + "/", f"{DOMINIO}/assets/img/{og}", base, jsonld)
            + topo(base) + f"""<main id="conteudo">
<section class="abre">
  <img src="_src-banner" alt="" aria-hidden="true">
  <div class="casca">
    <div>
      <div class="filete">Terreno · peças · lances</div>
      <h1>A batalha, <em>como partida</em></h1>
      <p class="lead">Por que este ataque deu certo, ou não deu, do ponto de vista do tabuleiro. O terreno, as peças de cada lado, a ordem dos lances e o erro de planejamento. Não é canal de heroísmo: é canal de causa.</p>
      <div class="botoes">
        <a class="botao cheio" href="#batalhas">Ver as batalhas</a>
        {link_canal('botao', 'Canal no YouTube')}
      </div>
    </div>
    <div class="escudo"><img src="assets/marca/escudo.jpg" width="720" height="886" alt="Escudo do Xadrez Bélico: um cavalo de xadrez com elmo de crista"></div>
  </div>
</section>

<section class="secao" id="batalhas">
  <div class="casca">
    <header>
      <div>
        <span class="rotulo">Tabuleiro · <b>{len(bs) + len(EM_PRODUCAO):02d}</b> episódios</span>
        <h2>As batalhas</h2>
        <p>Cada página tem a ficha da batalha, a partida lance a lance, o veredito, os mitos contra o registro e as fontes.</p>
      </div>
    </header>
    <ul class="batalhas">
{cards}
    </ul>
  </div>
</section>

<section class="secao metodo" id="metodo">
  <div class="casca">
    <div>
      <span class="rotulo">Método</span>
      <h2>O que estava à vista, <span class="destaque">lido de novo</span></h2>
      <p>Público de história militar corrige data, unidade e calibre — e com razão. Cada número aqui leva um selo dizendo quanto se pode confiar nele.</p>
      <p>Quando as fontes divergem, mostramos as versões e não escolhemos. Nome de unidade e horário só entram depois de conferidos. E nenhuma imagem deste site foi gerada por IA: é material de época, carta militar ou foto do lugar, com o ano na tela.</p>
    </div>
    <ul class="graus">{graus}</ul>
  </div>
</section>
</main>
""" + rodape(base) + fim())


# --- página de batalha ---------------------------------------------------------------
def figura(im, n, base):
    leg = f"{im['legenda']} — {im['autor']}, {im['licenca']}"
    return f"""<figure class="fig revela">
  <button type="button" data-grande="{base}assets/img/{e(im['arquivo'])}" data-legenda="{e(leg)}" aria-label="Ampliar imagem: {e(im['alt'])}">{img_tag(im['arquivo'], im['alt'], base, '(max-width:980px) 100vw, 720px')}{tarja(im)}</button>
  <figcaption><span class="fn">FIG. {n:02d}</span><span>{para(im['legenda'])}</span><small>{credito(im)}</small></figcaption>
</figure>"""


def pagina(b, bs, og):
    base = "../"
    url = f"{DOMINIO}/batalhas/{b['slug']}.html"
    capa, resto = b["imagens"][0], b["imagens"][1:]
    secoes = []
    for i, s in enumerate(b["lances"]):
        sid = f"l{i+1}"
        corpo = "".join(f"<p>{para(p)}</p>" for p in s["paragrafos"])
        fig = figura(resto[i], i + 2, base) if i < len(resto) else ""
        secoes.append((sid, s["titulo"], f'<h2 id="{sid}"><span class="n">Lance {i+1}</span>{e(s["titulo"])}</h2>{corpo}{fig}'))
    sobra = "".join(figura(im, len(b["lances"]) + 2 + k, base) for k, im in enumerate(resto[len(b["lances"]):]))

    numeros = "".join(f'<li><span class="valor">{e(n["valor"])}</span><span class="rot">{e(n["rotulo"])}</span>{conf_selo(n["conf"])}</li>' for n in b["numeros"])
    ficha = "".join(
        f'<tr><th scope="row">{e(f["item"])}</th><td class="v">{para(f["valor"])}'
        + (f'<span class="nota">{para(f["nota"])}</span>' if f.get("nota") else "")
        + f'</td><td class="c">{conf_selo(f["conf"])}</td></tr>' for f in b["ficha"])
    legenda_conf = "".join(f"<span>{conf_selo(k)} {e(v[2])}</span>" for k, v in CONF.items())
    mitos = "".join(f'<li><div><span class="rotulo">O que se conta</span><p>{para(m["circula"])}</p></div><div><span class="rotulo"><b>O que o registro mostra</b></span><p>{para(m["registro"])}</p></div></li>' for m in b["mitos"])
    fontes = "".join(
        f'<li>{para(f["texto"])}' + (f' — <a href="{e(f["url"])}" rel="noopener">{e(re.sub(r"^https?://(www[.])?", "", f["url"]).split("/")[0])}</a>' if f.get("url") else "") + "</li>"
        for f in b["fontes"])
    creditos = "".join(f'<li>Fig. {i+1:02d} — {e(im["legenda"])}: {credito(im)}</li>' for i, im in enumerate(b["imagens"]))
    indice = [("ficha", "Ficha da batalha")] + [(sid, t) for sid, t, _ in secoes] + [("veredito", "Veredito"), ("mitos", "Mitos e registro"), ("fontes", "Fontes")]
    indice_html = "".join(f'<li><a href="#{a}">{e(t)}</a></li>' for a, t in indice)

    i_atual = [x["slug"] for x in bs].index(b["slug"])
    ant = bs[i_atual - 1] if i_atual > 0 else None
    prox = next((x for x in bs if x["slug"] == b["proximo"]), None) if b["proximo"] else None
    nav = '<nav class="seguinte" aria-label="Outras batalhas">'
    nav += (f'<a href="{ant["slug"]}.html"><span class="rotulo">← Episódio {ant["num"]}</span><strong>{e(ant["batalha"])}</strong></a>' if ant else "<span></span>")
    nav += (f'<a href="{prox["slug"]}.html"><span class="rotulo">Episódio {prox["num"]} →</span><strong>{e(prox["batalha"])}</strong></a>' if prox
            else '<a href="../index.html#batalhas"><span class="rotulo">Todas as batalhas →</span><strong>O tabuleiro</strong></a>')
    nav += "</nav>"

    estreia = ""
    if b["estreia"]:
        estreia = f' · <span data-estreia="{b["estreia"]}" data-no-ar="no ar">estreia {e(data_br(b["estreia"], True))}</span>'
    jsonld = {
        "@context": "https://schema.org", "@type": "Article", "headline": f"{b['batalha']}: a partida explicada",
        "description": b["resumo"], "inLanguage": "pt-BR", "url": url, "image": f"{DOMINIO}/assets/img/{og}",
        "author": {"@type": "Organization", "name": NOME}, "publisher": {"@type": "Organization", "name": NOME},
        "about": {"@type": "Event", "name": b["batalha"], "location": b["lugar"]},
    }
    return (cabeca(f"{b['batalha']} ({b['data']}) — {NOME}", b["resumo"], url, f"{DOMINIO}/assets/img/{og}", base, jsonld, "article")
            + '<div class="progresso" aria-hidden="true"></div>' + topo(base, "batalhas") + f"""<main id="conteudo">
<header class="capa">
  {img_tag(capa['arquivo'], capa['alt'], base, '100vw', 'eager', foco=capa.get('foco'))}
  {tarja(capa)}
  <span class="credito-capa">{e(capa['legenda'])} — {credito(capa)}</span>
  <div class="casca">
    <span class="rotulo">Episódio <b>{e(b['num'])}</b> · {e(b['campanha'])}</span>
    <h1>{e(b['batalha'])}</h1>
    <div class="sub">{e(b['data'])} · {e(b['lugar'])}</div>
    <p class="perg">{para(b['pergunta'])}</p>
  </div>
</header>
<section class="placar" aria-label="A batalha em números"><ul>{numeros}</ul></section>
<div class="casca layout">
  <article class="texto">
    <div class="abertura">{''.join(f'<p>{para(p)}</p>' for p in b['abertura'])}</div>

    <h2 id="ficha"><span class="n">Ficha</span>Ficha da batalha</h2>
    <div class="dossie"><table class="ficha"><tbody>{ficha}</tbody></table></div>
    <div class="legenda-conf">{legenda_conf}</div>

    {''.join(h for _, _, h in secoes)}
    {sobra}

    <h2 id="veredito"><span class="n">Veredito</span>Por que deu no que deu</h2>
    <div class="veredito">{''.join(f'<p>{para(p)}</p>' for p in b['veredito'])}</div>

    <h2 id="mitos"><span class="n">Mitos</span>O que se conta e o que o registro mostra</h2>
    <ul class="mitos">{mitos}</ul>

    <section class="video">
      <div>
        <span class="rotulo">Episódio {e(b['num'])}{estreia}</span>
        <h3>{e(b['titulo_video'])}</h3>
      </div>
      {link_canal('botao cheio', 'Ver no YouTube')}
    </section>

    <h2 id="fontes"><span class="n">Fontes</span>Fontes</h2>
    <ol class="fontes">{fontes}</ol>
    <h3 style="margin-top:2rem">Imagens</h3>
    <ul class="creditos">{creditos}</ul>
  </article>
  <aside class="indice" aria-label="Nesta página">
    <div class="lado-card">
      <span class="rotulo">Ficha rápida</span>
      <dl>
        <div><dt>Onde</dt><dd>{e(b['lugar'])}</dd></div>
        <div><dt>Quando</dt><dd>{e(b['data'])}</dd></div>
        <div><dt>Episódio</dt><dd>{e(b['num'])}{(' · ' + e(data_br(b['estreia']))) if b['estreia'] else ''}</dd></div>
      </dl>
    </div>
    <span class="rotulo">Nesta página</span>
    <ol>{indice_html}</ol>
  </aside>
</div>
{nav}
</main>
<div class="lupa" role="dialog" aria-modal="true" aria-label="Imagem ampliada"><button type="button">Fechar</button><img alt=""><p></p></div>
""" + rodape(base) + fim())


def pagina_404():
    base = "/"
    return (cabeca(f"Página não encontrada — {NOME}", "Esta página não existe.", DOMINIO + "/404.html",
                   f"{DOMINIO}/assets/img/og-home.jpg", base, {"@context": "https://schema.org", "@type": "WebPage", "name": "404"})
            + topo(base) + """<main id="conteudo" class="simples"><div class="casca">
  <div class="filete">Erro 404</div>
  <h1>Lance <span class="destaque">ilegal</span></h1>
  <p>Esta casa do tabuleiro não existe, ou a página mudou de endereço.</p>
  <div class="botoes"><a class="botao cheio" href="/index.html#batalhas">Ver as batalhas</a></div>
</div></main>
""" + rodape(base) + fim())


def main():
    bs = carregar()
    (RAIZ / "batalhas").mkdir(exist_ok=True)
    css = (SRC / "xadrez.css").read_text(encoding="utf-8").replace("url(/assets/fontes/", "url(fontes/")
    (RAIZ / "assets" / "xadrez.css").write_text(css, encoding="utf-8")

    # fundo da abertura: só a mesa com o mapa e as peças, do banner. A metade
    # de cima tem "XADREZ BÉLICO" gravado na arte e brigaria com o h1.
    ban = Image.open(SRC / "marca" / "banner.jpg").convert("RGB")
    W, H = ban.size
    ban = ban.crop((0, int(H * .63), W, H))
    ban.thumbnail((1920, 1080), Image.LANCZOS)
    ban.save(IMG / "banner.jpg", "JPEG", quality=80, optimize=True, progressive=True)

    og = {b["slug"]: og_batalha(b) for b in bs}
    (RAIZ / "index.html").write_text(home(bs, og_home()).replace('src="_src-banner"', 'src="assets/img/banner.jpg"'), encoding="utf-8")
    gerados = set()
    for b in bs:
        (RAIZ / "batalhas" / f"{b['slug']}.html").write_text(pagina(b, bs, og[b["slug"]]), encoding="utf-8")
        gerados.add(f"{b['slug']}.html")
    for velho in (RAIZ / "batalhas").glob("*.html"):
        if velho.name not in gerados:
            velho.unlink()
            print("removido (batalha sem JSON):", velho.name)
    (RAIZ / "404.html").write_text(pagina_404(), encoding="utf-8")

    hoje = dt.date.today().isoformat()
    urls = [DOMINIO + "/"] + [f"{DOMINIO}/batalhas/{b['slug']}.html" for b in bs]
    (RAIZ / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{hoje}</lastmod></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (RAIZ / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /_src/\n\nSitemap: {DOMINIO}/sitemap.xml\n", encoding="utf-8")

    print(f"ok: {len(bs)} batalhas, {len(EM_PRODUCAO)} em produção" + ("" if CANAL else " · CANAL do YouTube não definido"))
    for b in bs:
        print(f"  {b['num']} {b['batalha']}: {len(b['ficha'])} linhas de ficha, {len(b['lances'])} lances, {len(b['imagens'])} imagens")


if __name__ == "__main__":
    main()
