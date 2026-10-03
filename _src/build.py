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
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "_src"
IMG = RAIZ / "assets" / "img"

DOMINIO = "https://xadrezbelico.com.br"
# Endereço do canal no YouTube, confirmado pelo Allan em 02/10/2026. None faz
# os botões dizerem "em breve no YouTube", sem link.
CANAL = "https://www.youtube.com/@XadrezB%C3%A9lico"
NOME = "Xadrez Bélico"

# AdSense — mesmo publisher do Vestígio Oculto. ADSENSE_LIGADO = False tira
# tudo de todas as páginas e apaga o ads.txt: é o interruptor geral.
ADSENSE_LIGADO = True
ADSENSE_PUB = "pub-4401770243539507"
# False = a faixa avisa e o anúncio carrega de imediato; quem recusar deixa de
# receber. True = nada de anúncio até "Entendi" (mais conservador, menos receita).
# Igual ao Vestígio.
CONSENTIMENTO_BLOQUEIA = False
CHAVE_CONSENTIMENTO = "xb-consentimento"


# Episódios anunciados que ainda não têm página.
EM_PRODUCAO = []

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
        return f'<a class="{classe}" href="{CANAL}" target="_blank" rel="noopener">{e(texto)}</a>'
    return f'<span class="{classe}" aria-disabled="true">{e(sem_link)}</span>'


# --- carga e conferência ----------------------------------------------------
ROTULO_LEIA = "Mais"
ITEM_LEIA = lambda y: (f'<li><a href="{y["slug"]}.html"><span class="rotulo">Episódio <b>{e(y["num"])}</b> · {e(y["campanha"])}</span>'
                       f'<strong>{e(y["batalha"])}</strong><span class="onde">{e(y["data"])}</span></a></li>')


def conferir_relacionados(x, slugs):
    """`relacionados` (opcional): três slugs do MESMO site, de assunto
    próximo, para o bloco "Leia também". Para se o slug não existir, se
    repetir, se apontar para a própria página ou para o `proximo` (que já
    tem bloco próprio)."""
    rel = x.get("relacionados")
    if rel is None:
        return
    if not isinstance(rel, list) or len(rel) != 3 or len(set(rel)) != 3:
        falha(f"{x['slug']}: relacionados deve ter 3 slugs diferentes: {rel!r}")
    for s in rel:
        if s not in slugs:
            falha(f"{x['slug']}: relacionado '{s}' não existe")
        if s == x["slug"]:
            falha(f"{x['slug']}: relacionado aponta para a própria página")
        if s == x["proximo"]:
            falha(f"{x['slug']}: relacionado '{s}' já é o próximo episódio")


def leia_tambem(x, todos):
    """Bloco "Leia também": três links internos de assunto próximo."""
    rel = x.get("relacionados") or []
    if not rel:
        return ""
    por_slug = {y["slug"]: y for y in todos}
    itens = "".join(ITEM_LEIA(por_slug[s]) for s in rel)
    return (f'<section class="leia" aria-labelledby="leia"><h2 id="leia"><span class="n">{ROTULO_LEIA}</span>Leia também</h2>'
            f'<ul>{itens}</ul></section>')


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
        conferir_relacionados(b, slugs)
    if not bs:
        falha("nenhuma batalha em _src/batalhas")
    return bs


# --- peças comuns -------------------------------------------------------------

def adsense_head():
    if not ADSENSE_LIGADO:
        return "<!-- AdSense desligado em _src/build.py -->"
    return (f'<meta name="google-adsense-account" content="ca-{ADSENSE_PUB}">\n'
            '<link rel="preconnect" href="https://pagead2.googlesyndication.com" crossorigin>')


def consentimento(base):
    """A faixa de cookies. O script do AdSense não fica no HTML: entra por
    aqui, e só quando pode — mesmo desenho do site do Vestígio Oculto."""
    if not ADSENSE_LIGADO:
        return ""
    return f"""<div class="consentimento" id="consentimento" role="dialog" aria-live="polite" aria-label="Aviso de cookies" hidden>
  <div class="casca">
    <p>Este site usa cookies do Google AdSense para exibir anúncios e medir audiência. Não pedimos cadastro nem e-mail. Detalhes na <a href="{base}privacidade.html">política de privacidade</a>.</p>
    <div class="botoes">
      <button type="button" data-consent="recusar">Recusar anúncios</button>
      <button type="button" data-consent="aceitar" class="principal">Entendi</button>
    </div>
  </div>
</div>
<script>
(function(){{
  var CHAVE='{CHAVE_CONSENTIMENTO}', PUB='{ADSENSE_PUB}', BLOQUEIA={'true' if CONSENTIMENTO_BLOQUEIA else 'false'};
  function ler(){{try{{return localStorage.getItem(CHAVE)}}catch(e){{return null}}}}
  function gravar(v){{try{{localStorage.setItem(CHAVE,v)}}catch(e){{}}}}
  function carrega(){{
    if(!PUB||document.getElementById('ads-google'))return;
    var s=document.createElement('script');s.id='ads-google';s.async=true;s.crossOrigin='anonymous';
    s.src='https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-'+PUB;
    document.head.appendChild(s);
  }}
  // "Rever escolha de cookies", no rodapé: apaga a escolha salva e recarrega,
  // e a faixa volta a aparecer.
  document.querySelectorAll('[data-rever-cookies]').forEach(function(a){{
    a.addEventListener('click',function(ev){{
      ev.preventDefault();
      try{{localStorage.removeItem(CHAVE)}}catch(e){{}}
      location.reload();
    }});
  }});
  var escolha=ler();
  if(escolha==='aceitar'||(escolha===null&&!BLOQUEIA))carrega();
  var caixa=document.getElementById('consentimento');
  if(escolha===null&&caixa){{
    caixa.hidden=false;
    caixa.addEventListener('click',function(ev){{
      var b=ev.target.closest('[data-consent]');if(!b)return;
      var v=b.dataset.consent;gravar(v);caixa.hidden=true;
      if(v==='aceitar')carrega();else{{var x=document.getElementById('ads-google');if(x)x.remove();}}
    }});
  }}
  // Europa, Reino Unido, Suíça: quem pergunta é a mensagem do Google (a
  // plataforma certificada que o AdSense exige lá). Se ela diz que o GDPR se
  // aplica, esta faixa sai da frente. Sem a mensagem publicada, não dispara.
  if(escolha===null&&caixa){{
    var n=0,t=setInterval(function(){{
      if(typeof window.__tcfapi==='function'){{
        clearInterval(t);
        window.__tcfapi('addEventListener',2,function(tc,ok){{if(ok&&tc&&tc.gdprApplies)caixa.hidden=true;}});
      }}else if(++n>40)clearInterval(t);
    }},250);
  }}
}})();
</script>
"""

def css_inline():
    """O CSS vai dentro do <head>: o arquivo externo custava uma ida e volta
    inteira bloqueando a primeira pintura (PageSpeed, 03/10/2026). Fontes com
    caminho absoluto, porque o <style> resolve a partir da página."""
    css = (SRC / "xadrez.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r"\n\s*\n+", "\n", css).strip()


CSS_INLINE = None


def cabeca(titulo, descricao, url, imagem, base, jsonld, tipo="website", indexar=True, extra=""):
    global CSS_INLINE
    if CSS_INLINE is None:
        CSS_INLINE = css_inline()
    if indexar:
        # max-image-preview:large: deixa o Google Discover usar a og:image grande
        canon = (f'<link rel="canonical" href="{e(url)}">\n'
                 '<meta name="robots" content="max-image-preview:large">')
    else:
        canon = '<meta name="robots" content="noindex, follow">'
    lds = jsonld if isinstance(jsonld, list) else [jsonld]
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in lds)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descricao)}">
{canon}
<meta name="theme-color" content="#171310">
<link rel="icon" href="{base}assets/marca/cavalo-64.png" type="image/png">
<link rel="apple-touch-icon" href="{base}assets/marca/cavalo-180.png">
<link rel="preload" href="{base}assets/fontes/libre-baskerville-latin-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{base}assets/fontes/libre-franklin-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
{extra}
{adsense_head()}
<style>{CSS_INLINE}</style>
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
{ld}
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
      <a href="{base}sobre.html"{cur('sobre')}>Sobre</a>
      {link_canal('yt', 'YouTube', 'YouTube em breve')}
    </nav>
  </div>
</header>
"""


def rodape(base):
    ano = dt.date.today().year
    canal = f'<p><a href="{CANAL}" target="_blank" rel="noopener">Assista no YouTube</a></p>' if CANAL else ""
    rever = ' <a href="#" role="button" data-rever-cookies>Rever escolha de cookies</a>.' if ADSENSE_LIGADO else ""
    return f"""<footer class="rodape">
  <div class="casca">
    <div>
      <h2>Xadrez Bélico</h2>
      <p>Batalha explicada como partida: terreno, peças, lances e o erro de planejamento. Não é canal de heroísmo, é canal de causa.</p>
      {canal}
    </div>
    <div>
      <h2>Do mesmo criador</h2>
      <ul>
        <li><a href="https://vestigiooculto.com.br" rel="noopener">Vestígio Oculto</a> — arqueologia e mistério</li>
        <li><a href="https://arquiteturadoimpossivel.com.br" rel="noopener">Arquitetura do Impossível</a> — como as grandes obras foram erguidas</li>
      </ul>
    </div>
    <div>
      <h2>Este site</h2>
      <ul>
        <li><a href="{base}sobre.html">Sobre</a> · <a href="{base}contato.html">Contato</a></li>
        <li>Exibe anúncios do Google AdSense. <a href="{base}privacidade.html">Política de privacidade</a>.{rever}</li>
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


def webp(jpg):
    """Cópia WebP ao lado do JPEG (o JPEG fica como reserva no <picture>).
    Só regera se faltar ou se o JPEG for mais novo."""
    destino = jpg.with_suffix(".webp")
    if not destino.exists() or destino.stat().st_mtime < jpg.stat().st_mtime:
        Image.open(jpg).convert("RGB").save(destino, "WEBP", quality=78, method=5)
    return destino.name


def webp_srcset(arquivo, base):
    """(srcset WebP, tem versão de 800?) da imagem `arquivo`."""
    nome = Path(arquivo).stem
    menor = IMG / f"{nome}-800.jpg"
    w = Image.open(IMG / arquivo).size[0]
    grande = f"{base}assets/img/{webp(IMG / arquivo)}"
    if menor.exists():
        return f"{base}assets/img/{webp(menor)} 800w, {grande} {w}w", True
    return grande, False


def img_tag(arquivo, alt, base, tamanhos="100vw", carregar="lazy", foco=None):
    """<picture> com WebP e reserva JPEG. `carregar="eager"` é a imagem do LCP
    (a capa): sai com fetchpriority alto; o resto é lazy."""
    nome = Path(arquivo).stem
    w, h = Image.open(IMG / arquivo).size
    srcset = ""
    if (IMG / f"{nome}-800.jpg").exists():
        srcset = f' srcset="{base}assets/img/{nome}-800.jpg 800w, {base}assets/img/{arquivo} {w}w" sizes="{tamanhos}"'
    st = f' style="object-position:{e(foco)}"' if foco else ""
    prio = ' fetchpriority="high"' if carregar == "eager" else ""
    ws, tem800 = webp_srcset(arquivo, base)
    sz = f' sizes="{tamanhos}"' if tem800 else ""
    return (f'<picture><source type="image/webp" srcset="{ws}"{sz}>'
            f'<img src="{base}assets/img/{e(arquivo)}"{srcset} width="{w}" height="{h}" '
            f'alt="{e(alt)}" loading="{carregar}"{prio} decoding="async"{st}></picture>')


def preload_capa(arquivo, base, tamanhos="100vw"):
    """Avisa o navegador da capa (LCP) já no <head>, antes do HTML do corpo."""
    ws, tem800 = webp_srcset(arquivo, base)
    sz = f' imagesizes="{tamanhos}"' if tem800 else ""
    return f'<link rel="preload" as="image" type="image/webp" imagesrcset="{ws}"{sz} fetchpriority="high">'


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


# --- SEO -------------------------------------------------------------------------
TITULO_MAX = 60
DESCRICAO_MIN, DESCRICAO_MAX = 120, 155
LOGO = f"{DOMINIO}/assets/marca/cavalo-512.png"
ORG = {"@type": "Organization", "name": NOME, "url": DOMINIO + "/",
       "logo": {"@type": "ImageObject", "url": LOGO, "width": 512, "height": 512}}


def anos(b):
    a = sorted(set(re.findall(r"\b(1\d{3})\b", b["data"])))
    return f"{a[0]}–{a[-1]}" if len(a) > 1 else a[0]


def titulo_seo(b):
    """Assunto primeiro, marca no fim, até 60 caracteres. "Lance a lance" é o
    que a página entrega (a seção de lances); sai se não couber, e o artigo
    inicial também, antes de cortar a marca."""
    # `nome_busca` (opcional no JSON): o nome como as pessoas buscam a batalha
    # ("Batalha de Stalingrado", "Ataque a Pearl Harbor"). Só muda o <title>;
    # o h1 e o resto da página seguem com `batalha`.
    base = b.get("nome_busca") or b["batalha"]
    nomes = [base, re.sub(r"^(A|O|As|Os) ", "", base)]
    for meio in (", lance a lance", ""):
        for n in nomes:
            t = f"{n} ({anos(b)}){meio} · {NOME}"
            if len(t) <= TITULO_MAX:
                return t
    falha(f"{b['slug']}: não há título de até {TITULO_MAX} caracteres")


def data_git(caminho, primeira=False):
    """Data (AAAA-MM-DD) do primeiro ou do último commit do arquivo; hoje se
    ele ainda tem mudança não publicada (ou não está no git)."""
    rel = str(Path(caminho).relative_to(RAIZ)).replace("\\", "/")
    try:
        if not primeira:
            sujo = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=RAIZ,
                                  capture_output=True, text=True).stdout.strip()
            if sujo:
                return dt.date.today().isoformat()
        args = ["git", "log", "--format=%cs", "--", rel]
        if primeira:
            args[2:2] = ["--diff-filter=A"]
        datas = subprocess.run(args, cwd=RAIZ, capture_output=True, text=True).stdout.split()
        if datas:
            return datas[-1] if primeira else datas[0]
    except OSError:
        pass
    return dt.date.today().isoformat()


def migalhas(*itens):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": n, "item": u}
                                for i, (n, u) in enumerate(itens, start=1)]}


def conferir_seo(paginas):
    """Porteiro: título até 60 e único; descrição de 120 a 155 e única."""
    erros, vt, vd = [], {}, {}
    for nome, (t, d) in paginas.items():
        if len(t) > TITULO_MAX:
            erros.append(f"{nome}: título com {len(t)} caracteres")
        if not DESCRICAO_MIN <= len(d) <= DESCRICAO_MAX:
            erros.append(f"{nome}: descrição com {len(d)} caracteres ({DESCRICAO_MIN}–{DESCRICAO_MAX})")
        if t in vt:
            erros.append(f"{nome}: título igual ao de {vt[t]}")
        if d in vd:
            erros.append(f"{nome}: descrição igual à de {vd[d]}")
        vt[t], vd[d] = nome, nome
    if erros:
        falha("SEO\n  " + "\n  ".join(erros))


TITULO_HOME = f"{NOME}: a batalha explicada como partida"
DESC_HOME = "História militar lida como tabuleiro: terreno, peças, lances e o erro de planejamento. Por que o ataque deu certo, ou não deu. Com fonte."
TITULO_SOBRE = f"Sobre o {NOME}: como cada página é apurada"
DESC_SOBRE = (f"O que é o {NOME}, projeto independente de história militar: como cada página é apurada, "
              "o selo de confiança dos números, as imagens e quem faz.")
TITULO_CONTATO = f"Contato · {NOME}"
DESC_CONTATO = (f"Como falar com o {NOME} por e-mail: correções com fonte, créditos e retirada de imagens, "
                "pedidos sobre seus dados (LGPD), pautas e imprensa.")
TITULO_PRIV = f"Política de privacidade · {NOME}"
DESC_PRIV = (f"Como o {NOME} trata dados, cookies e publicidade do Google AdSense: o que coleta, o que não "
             "coleta e quais são os seus direitos sob a LGPD.")


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


# o escudo da abertura mede 300 px (160 no celular); servir o de 720 era o LCP do celular
ESCUDO_SIZES = "(max-width:820px) 160px, 300px"


def home(bs, og):
    base = ""
    nomes = {"2+": "Confirmado", "1": "Fonte única", "DIV": "Divergência", "sem": "Sem registro"}
    graus = "".join(f"<li>{conf_selo(k)}<p><strong>{nomes[k]}</strong>{e(v[2])}</p></li>" for k, v in CONF.items())
    org = dict(ORG, sameAs=[CANAL] if CANAL else [])
    jsonld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "name": NOME, "url": DOMINIO + "/", "inLanguage": "pt-BR",
         "description": "História militar explicada como partida de xadrez.",
         "publisher": {"@type": "Organization", "name": NOME, "url": DOMINIO + "/"}},
        org]}
    cards = "\n".join(card(b, base) for b in bs) + "\n" + "\n".join(card_producao(a) for a in EM_PRODUCAO)
    return (cabeca(TITULO_HOME, DESC_HOME, DOMINIO + "/", f"{DOMINIO}/assets/img/{og}", base, jsonld)
            + topo(base) + f"""<main id="conteudo">
<section class="abre">
  <picture><source type="image/webp" srcset="assets/img/banner.webp"><img src="_src-banner" width="{{BANNER_W}}" height="{{BANNER_H}}" alt="" aria-hidden="true" fetchpriority="high" decoding="async"></picture>
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
    <div class="escudo"><picture><source type="image/webp" srcset="assets/marca/{webp(RAIZ / 'assets' / 'marca' / 'escudo-360.jpg')} 360w, assets/marca/{webp(RAIZ / 'assets' / 'marca' / 'escudo.jpg')} 720w" sizes="{ESCUDO_SIZES}"><img src="assets/marca/escudo.jpg" srcset="assets/marca/escudo-360.jpg 360w, assets/marca/escudo.jpg 720w" sizes="{ESCUDO_SIZES}" width="720" height="886" alt="Escudo do Xadrez Bélico: um cavalo de xadrez com elmo de crista" fetchpriority="high" decoding="async"></picture></div>
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
""" + rodape(base) + consentimento(base) + fim())


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
    arq = SRC / "batalhas" / f"{b['num']}-{b['slug']}.json"
    jsonld = [{
        "@context": "https://schema.org", "@type": "Article", "headline": f"{b['batalha']}: a partida explicada",
        "description": b["resumo"], "inLanguage": "pt-BR", "url": url,
        "image": {"@type": "ImageObject", "url": f"{DOMINIO}/assets/img/{og}", "width": 1200, "height": 630},
        "datePublished": data_git(arq, primeira=True), "dateModified": data_git(arq),
        "author": {"@type": "Organization", "name": NOME, "url": DOMINIO + "/"}, "publisher": ORG,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "articleSection": b["campanha"],
        "about": {"@type": "Event", "name": b["batalha"], "location": b["lugar"]},
    }, migalhas((NOME, DOMINIO + "/"), (b["batalha"], url))]
    return (cabeca(titulo_seo(b), b["resumo"], url, f"{DOMINIO}/assets/img/{og}", base, jsonld, "article",
                   extra=preload_capa(capa["arquivo"], base))
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
        <h3>{e(b['titulo_video']) if b['titulo_video'] else 'Episódio em produção'}</h3>
      </div>
      {link_canal('botao cheio', 'Ver no YouTube')}
    </section>

    {leia_tambem(b, bs)}

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
        <div><dt>Episódio</dt><dd>{e(b['num'])} · {e(data_br(b['estreia'])) if b['estreia'] else e(b['campanha'])}</dd></div>
      </dl>
    </div>
    <span class="rotulo">Nesta página</span>
    <ol>{indice_html}</ol>
  </aside>
</div>
{nav}
</main>
<div class="lupa" role="dialog" aria-modal="true" aria-label="Imagem ampliada"><button type="button">Fechar</button><img alt=""><p></p></div>
""" + rodape(base) + consentimento(base) + fim())


def pagina_404():
    base = "/"
    return (cabeca(f"Página não encontrada · {NOME}", "Esta página não existe.", DOMINIO + "/404.html",
                   f"{DOMINIO}/assets/img/og-home.jpg", base, {"@context": "https://schema.org", "@type": "WebPage", "name": "404"},
                   indexar=False)
            + topo(base) + """<main id="conteudo" class="simples"><div class="casca">
  <div class="filete">Erro 404</div>
  <h1>Lance <span class="destaque">ilegal</span></h1>
  <p>Esta casa do tabuleiro não existe, ou a página mudou de endereço.</p>
  <div class="botoes"><a class="botao cheio" href="/index.html#batalhas">Ver as batalhas</a></div>
</div></main>
""" + rodape(base) + consentimento(base) + fim())



PRIVACIDADE = """<main id="conteudo"><div class="casca privacidade">
  <span class="rotulo">Documento · atualizado em 03 de outubro de 2026</span>
  <h1>Política de privacidade</h1>
  <p class="lead">Um site que cobra fonte dos outros deve ser claro sobre si mesmo. Aqui está o que o {{NOME}} coleta, o que não coleta, quem mais está envolvido e o que você pode exigir.</p>

  <div class="resumo"><strong>O resumo, em três linhas.</strong> Não pedimos cadastro, não temos formulário e não guardamos seu e-mail. O que existe são cookies de publicidade do Google, usados para exibir anúncios. Você pode recusá-los na faixa que aparece na primeira visita, rever essa escolha a qualquer momento pelo link “Rever escolha de cookies”, no rodapé, ou desligá-los nas configurações do Google.</div>

  <h2>1. Quem é o responsável</h2>
  <p>O <strong>{{NOME}}</strong> é um projeto editorial independente, publicado em xadrezbelico.com.br, {{CANAL_FRASE}}. Para qualquer assunto desta política — inclusive pedidos de exclusão ou de informação —, o contato é o e-mail divulgado no canal.</p>

  <h2>2. O que coletamos, e o que não</h2>
  <p>Não há cadastro, login, comentários, newsletter nem formulário de contato. Nenhuma página pede seu nome, e-mail, telefone ou documento. Não montamos perfil de leitor e não vendemos nem compartilhamos lista de ninguém, porque lista não existe.</p>
  <p>O que existe é o que qualquer site recebe por ser acessado: o servidor que hospeda estas páginas registra o endereço IP, a data e a hora, a página pedida e o navegador usado. Esses registros servem para segurança e diagnóstico de falha, e não são usados para identificar pessoas.</p>

  <h2>3. Cookies e publicidade</h2>
  <p>Este site exibe anúncios por meio do <strong>Google AdSense</strong>. Para isso, o Google e seus parceiros usam cookies — pequenos arquivos gravados no seu navegador — para selecionar e medir os anúncios.</p>
  <ul>
    <li>O Google, como fornecedor terceirizado, utiliza cookies para exibir anúncios neste site.</li>
    <li>O <strong>cookie DART</strong> permite que o Google veicule anúncios com base nas visitas do usuário a este e a outros sites da internet.</li>
    <li>Parceiros e redes de terceiros também podem usar cookies, identificadores de dispositivo ou tecnologia semelhante para medir e personalizar os anúncios.</li>
    <li>Nenhum desses dados passa por nós: o site não recebe, não armazena e não tem acesso ao que essas redes coletam.</li>
  </ul>
  <p>Você pode desativar a publicidade personalizada — em todos os sites da rede do Google, não só neste — em <a href="https://adssettings.google.com" rel="noopener">adssettings.google.com</a>. As regras completas do Google estão em <a href="https://policies.google.com/technologies/ads?hl=pt-BR" rel="noopener">policies.google.com/technologies/ads</a>, e para sair da publicidade comportamental de várias redes de uma vez existe o <a href="https://www.aboutads.info/choices/" rel="noopener">aboutads.info/choices</a>.</p>
  <p>Todo navegador também permite bloquear ou apagar cookies. Fazer isso não impede a leitura de nada: o conteúdo deste site não depende de cookie para funcionar.</p>

  <h2>4. O que guardamos no seu navegador</h2>
  <p>Uma única coisa, e ela não sai do seu aparelho: quando você responde à faixa de cookies, a escolha fica registrada no armazenamento local do navegador, sob a chave <code>{{CHAVE}}</code>. Serve só para não perguntar de novo a cada página. Não é cookie, não é enviada a servidor nenhum e some quando você limpa os dados do site ou clica em “Rever escolha de cookies”, no rodapé de qualquer página: a escolha salva é apagada e a faixa volta a aparecer.</p>

  <h2>5. Conteúdo de terceiros</h2>
  <p>Um único serviço externo participa da exibição destas páginas: o <strong>Google AdSense</strong>, que entrega os anúncios. Se você recusar na faixa, o script de anúncios é retirado e deixa de ser carregado nas próximas páginas.</p>
  <p>O <strong>YouTube</strong> só entra em cena se você clicar num link para o canal: nenhum vídeo é incorporado nestas páginas. Todo o resto — as imagens das páginas de batalha e as fontes tipográficas — vem deste mesmo domínio.</p>

  <h2>6. Seus direitos sob a LGPD</h2>
  <p>A Lei nº 13.709/2018 garante a você o direito de confirmar se há tratamento de dados seus, de acessá-los, de corrigi-los, de pedir anonimização ou eliminação, de solicitar portabilidade, de saber com quem foram compartilhados e de revogar consentimento a qualquer momento.</p>
  <p>Aqui o exercício desses direitos é curto, porque a base de dados que poderíamos entregar é praticamente vazia. Ainda assim, qualquer pedido feito pelo contato do canal será respondido. Para revogar a escolha feita na faixa de cookies, use o link “Rever escolha de cookies”, no rodapé de qualquer página. Para os dados que o Google coleta através dos anúncios, o pedido precisa ser feito ao próprio Google — nós exibimos o espaço, mas é ele quem trata esses dados.</p>

  <h2>7. Crianças e adolescentes</h2>
  <p>O conteúdo deste site não se dirige a menores de 13 anos, e não coletamos conscientemente dados de crianças. Se você é responsável por uma criança e acredita que algum dado dela chegou até aqui, entre em contato para que seja eliminado.</p>

  <h2>8. Mudanças nesta política</h2>
  <p>Se algo mudar — uma nova rede de anúncios, uma ferramenta de medição, uma área de comentários —, esta página muda junto, e a data no topo é atualizada.</p>

  <div class="botoes" style="margin-top:2.5rem"><a class="botao cheio" href="index.html#batalhas">Ver as batalhas</a></div>
</div></main>
"""


def pagina_privacidade():
    """Escrita para ESTE site, não copiada de modelo: diz só o que ele faz.
    Adaptada da política do Vestígio Oculto, que tem o mesmo desenho."""
    base = ""
    if CANAL:
        canal = f'com canal correspondente no YouTube, <a href="{CANAL}" target="_blank" rel="noopener">@XadrezBélico</a>'
    else:
        canal = "com canal correspondente no YouTube"
    corpo = (PRIVACIDADE.replace("{{NOME}}", NOME).replace("{{CANAL_FRASE}}", canal)
             .replace("{{CHAVE}}", CHAVE_CONSENTIMENTO))
    u = DOMINIO + "/privacidade.html"
    return (cabeca(TITULO_PRIV, DESC_PRIV, u, f"{DOMINIO}/assets/img/og-home.jpg", base,
                   [{"@context": "https://schema.org", "@type": "WebPage", "name": TITULO_PRIV, "description": DESC_PRIV,
                     "url": u, "inLanguage": "pt-BR"},
                    migalhas((NOME, DOMINIO + "/"), ("Política de privacidade", u))])
            + topo(base) + corpo + rodape(base) + consentimento(base) + fim())


def pagina_sobre():
    base = ""
    canal = f'no YouTube, <a href="{CANAL}" target="_blank" rel="noopener">@XadrezBélico</a>' if CANAL else "no YouTube"
    corpo = f"""<main id="conteudo"><div class="casca privacidade">
  <span class="rotulo">Sobre</span>
  <h1>Sobre o {NOME}</h1>

  <h2>1. O que é</h2>
  <p>O <strong>Xadrez Bélico</strong> é um projeto editorial independente, feito no Brasil, de história militar. Cada página deste site acompanha um episódio do canal {canal}, e vai além dele: traz a ficha da batalha, a partida lance a lance, as fontes, as imagens com crédito e as divergências que não cabem num vídeo.</p>
  <p>A pergunta é sempre a mesma: <em>por que este ataque deu certo, ou não deu, do ponto de vista do tabuleiro</em> — o terreno, as peças de cada lado, a ordem dos lances e o erro de planejamento. Não é um projeto de heroísmo nem de efeméride: é de causa.</p>

  <h2>2. Como uma página é feita</h2>
  <ul>
    <li><strong>Nome de unidade e horário só entram depois de conferidos.</strong> Público de história militar corrige data, unidade e calibre — e com razão.</li>
    <li><strong>Cada número leva um selo de confiança:</strong> confirmado em duas ou mais fontes, fonte única (o texto diz qual), divergência (mostramos as versões e não escolhemos) ou sem registro.</li>
    <li><strong>Onde o texto corrige um mito, usa o número cheio.</strong> Arredondar sempre a favor do argumento não é fala coloquial, é tese.</li>
    <li><strong>Texto integralmente autoral.</strong> As fontes ficam listadas no fim de cada página.</li>
  </ul>

  <h2>3. Imagens</h2>
  <p>Só entram fotografias e documentos de época, cartas militares e fotos do lugar como ele é hoje — essas com o ano escrito na própria imagem. Tudo de acervos em domínio público ou sob licença Creative Commons que permite uso comercial, com autor e licença creditados. Imagem gerada por IA não entra neste site, e símbolos de regime não aparecem como assunto de imagem.</p>

  <h2>4. Correções</h2>
  <p>Errou-se uma data, um nome, um número? Escreva pela página de <a href="contato.html">contato</a>, de preferência com a fonte. O erro confirmado é corrigido aqui, e a correção vale também para o que vier depois no canal.</p>

  <h2>5. Quem faz</h2>
  <p>O {NOME} é escrito, apurado e mantido de forma independente, sem vínculo com universidade, empresa ou órgão público. É do mesmo criador de outros dois projetos com o mesmo cuidado com a fonte: <a href="https://vestigiooculto.com.br" rel="noopener">Vestígio Oculto</a>, sobre arqueologia e mistério, e <a href="https://arquiteturadoimpossivel.com.br" rel="noopener">Arquitetura do Impossível</a>, sobre como as grandes obras foram erguidas.</p>
  <p>O site se mantém com anúncios do Google AdSense, descritos na <a href="privacidade.html">política de privacidade</a>. Nenhum anúncio interfere no que é escrito.</p>
</div></main>
"""
    u = DOMINIO + "/sobre.html"
    return (cabeca(TITULO_SOBRE, DESC_SOBRE, u, f"{DOMINIO}/assets/img/og-home.jpg", base,
                   [{"@context": "https://schema.org", "@type": "AboutPage", "name": TITULO_SOBRE, "description": DESC_SOBRE,
                     "url": u, "inLanguage": "pt-BR"},
                    migalhas((NOME, DOMINIO + "/"), ("Sobre", u))])
            + topo(base, "sobre") + corpo + rodape(base) + consentimento(base) + fim())


def pagina_contato():
    base = ""
    corpo = f"""<main id="conteudo"><div class="casca privacidade">
  <span class="rotulo">Contato</span>
  <h1>Fale com o {NOME}</h1>
  <p class="lead">Correção, crédito de imagem, pedido sobre seus dados ou qualquer outro assunto: o caminho é um só.</p>
  <div class="resumo"><strong>E-mail:</strong> <a href="mailto:allangipa@gmail.com">allangipa@gmail.com</a></div>

  <h2>Para que escrever</h2>
  <ul>
    <li><strong>Correções.</strong> Uma data, um nome ou um número errado. Mande a fonte junto: é o que permite corrigir rápido.</li>
    <li><strong>Imagens e créditos.</strong> Se você é autor de uma imagem usada aqui e o crédito está incompleto, ou quer que ela saia, escreva.</li>
    <li><strong>Seus dados.</strong> Pedidos sob a LGPD, conforme a <a href="privacidade.html">política de privacidade</a>.</li>
    <li><strong>Pautas, imprensa e parcerias.</strong> Sugestões de tema também são bem-vindas.</li>
  </ul>

  <h2>Como respondemos</h2>
  <p>Não há formulário nem cadastro: a conversa é por e-mail, e o seu endereço não é usado para mais nada além de responder. Correção confirmada entra na página.</p>
</div></main>
"""
    u = DOMINIO + "/contato.html"
    return (cabeca(TITULO_CONTATO, DESC_CONTATO, u, f"{DOMINIO}/assets/img/og-home.jpg", base,
                   [{"@context": "https://schema.org", "@type": "ContactPage", "name": TITULO_CONTATO, "description": DESC_CONTATO,
                     "url": u, "inLanguage": "pt-BR"},
                    migalhas((NOME, DOMINIO + "/"), ("Contato", u))])
            + topo(base, "contato") + corpo + rodape(base) + consentimento(base) + fim())

def main():
    bs = carregar()
    seo = {"home": (TITULO_HOME, DESC_HOME), "sobre": (TITULO_SOBRE, DESC_SOBRE),
           "contato": (TITULO_CONTATO, DESC_CONTATO), "privacidade": (TITULO_PRIV, DESC_PRIV)}
    seo.update({b["slug"]: (titulo_seo(b), b["resumo"]) for b in bs})
    conferir_seo(seo)
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
    webp(IMG / "banner.jpg")

    og = {b["slug"]: og_batalha(b) for b in bs}
    (RAIZ / "index.html").write_text(home(bs, og_home()).replace('src="_src-banner"', 'src="assets/img/banner.jpg"')
        .replace("{BANNER_W}", str(ban.width)).replace("{BANNER_H}", str(ban.height)), encoding="utf-8")
    gerados = set()
    for b in bs:
        (RAIZ / "batalhas" / f"{b['slug']}.html").write_text(pagina(b, bs, og[b["slug"]]), encoding="utf-8")
        gerados.add(f"{b['slug']}.html")
    for velho in (RAIZ / "batalhas").glob("*.html"):
        if velho.name not in gerados:
            velho.unlink()
            print("removido (batalha sem JSON):", velho.name)
    (RAIZ / "404.html").write_text(pagina_404(), encoding="utf-8")
    (RAIZ / "privacidade.html").write_text(pagina_privacidade(), encoding="utf-8")
    (RAIZ / "sobre.html").write_text(pagina_sobre(), encoding="utf-8")
    (RAIZ / "contato.html").write_text(pagina_contato(), encoding="utf-8")
    ads = RAIZ / "ads.txt"
    if ADSENSE_LIGADO:
        ads.write_text("# Declaração de vendedor autorizado (IAB ads.txt)\n"
                       "# Gerado por _src/build.py a partir de ADSENSE_PUB. Não editar à mão.\n"
                       f"google.com, {ADSENSE_PUB}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    elif ads.exists():
        ads.unlink()

    # lastmod: batalha = último commit do JSON dela (hoje, se mudou e não foi
    # publicado); páginas fixas = último commit do build.py; home = a mais nova.
    fixas = data_git(Path(__file__).resolve())
    datas = {f"{DOMINIO}/batalhas/{b['slug']}.html": data_git(SRC / "batalhas" / f"{b['num']}-{b['slug']}.json") for b in bs}
    for pg in ("sobre", "contato", "privacidade"):
        datas[f"{DOMINIO}/{pg}.html"] = fixas
    datas = {DOMINIO + "/": max([fixas, *datas.values()]), **datas}
    (RAIZ / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in datas.items()) + "</urlset>\n", encoding="utf-8")
    (RAIZ / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /_src/\n\nSitemap: {DOMINIO}/sitemap.xml\n", encoding="utf-8")

    print(f"ok: {len(bs)} batalhas, {len(EM_PRODUCAO)} em produção" + ("" if CANAL else " · CANAL do YouTube não definido"))
    for b in bs:
        print(f"  {b['num']} {b['batalha']}: {len(b['ficha'])} linhas de ficha, {len(b['lances'])} lances, {len(b['imagens'])} imagens")


if __name__ == "__main__":
    main()
