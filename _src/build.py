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

Idiomas (desde 03/10/2026): o português fica na raiz, com os caminhos de
sempre; cada outro idioma ganha uma pasta (`en/`, `es/`) com os mesmos slugs.
Um idioma entra no ar quando existe `_src/i18n/<id>.json` (os textos da
interface); uma batalha sai nele quando existe `_src/batalhas/<id>/NN-slug.json`
e a tradução passa nas travas de `fundir_traducao()` — campo faltando, número
que não bate com o original, texto não traduzido: o build para.
"""
import datetime as dt
import html
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "_src"
IMG = RAIZ / "assets" / "img"

# Domínio principal desde 03/10/2026. O .com.br continua apontando para os
# mesmos arquivos e redireciona 301, caminho a caminho, pelo .htaccess.
DOMINIO = "https://xadrezbelico.com"
SITE_IRMAO_VO = "https://vestigiooculto.com.br"
SITE_IRMAO_AI = "https://arquiteturadoimpossivel.com"
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
    """Data por extenso no idioma da página (o nome ficou por história)."""
    d = dt.date.fromisoformat(iso)
    if longa:
        return cfg("data_longa").format(dia=d.day, mes=cfg("meses")[d.month - 1], ano=d.year)
    return cfg("data_curta").format(dia=d.day, mes=cfg("meses_curtos")[d.month - 1], ano=d.year)


def falha(msg):
    raise SystemExit("PARADO: " + msg)


# --- idiomas ------------------------------------------------------------------
# Português na raiz, com os caminhos de sempre; cada outro idioma numa pasta
# (en/, es/), com os MESMOS slugs (o hreflang casa página com página sem
# tabela de correspondência). Ordem = ordem do seletor. Só fica ativo o idioma
# que tem _src/i18n/<id>.json; e só sai nele a página que tem tradução.
IDIOMAS = ["pt", "en", "es"]
BASE_IDIOMA = "pt"
PASTA_ITENS = "batalhas"         # _src/batalhas/ e batalhas/<slug>.html
I18N_DIR = SRC / "i18n"
CONFIG_PT = {
    "nome": "Português", "curto": "PT", "hreflang": "pt-BR", "og_locale": "pt_BR",
    # subtítulo da marca nos outros idiomas ("Xadrez Bélico — War as a Chess
    # Game"); em português a marca é só o nome
    "marca_sub": "",
    "meses": MESES_LONGO,
    "meses_curtos": MESES,
    "data_longa": "{dia} de {mes} de {ano}",
    "data_curta": "{dia:02d} {mes} {ano}",
}
CHAVES_IDIOMA = set(CONFIG_PT)
I18N = {BASE_IDIOMA: {"_idioma": CONFIG_PT, "textos": {}}}
ATIVOS = [BASE_IDIOMA]
L = BASE_IDIOMA                  # idioma da página que está sendo gerada
PAGINA = "index.html"            # chave (caminho em português) da página atual
EXISTE = defaultdict(set)        # idioma -> chaves de página geradas nele
FALTANDO = defaultdict(set)      # idioma -> textos da interface sem tradução
USADOS = defaultdict(set)


def carregar_idiomas():
    """Lê _src/i18n/<id>.json: {"_idioma": {...como CONFIG_PT}, "textos":
    {"texto em português": "tradução"}}. A chave é o próprio texto em
    português: mudou o original, a tradução deixa de casar e o build para."""
    for lg in IDIOMAS:
        if lg == BASE_IDIOMA:
            continue
        arq = I18N_DIR / f"{lg}.json"
        if not arq.exists():
            continue
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except json.JSONDecodeError as ex:
            falha(f"i18n/{lg}.json não é JSON válido: {ex}")
        conf = d.get("_idioma") or {}
        falta = CHAVES_IDIOMA - set(conf)
        if falta:
            falha(f"i18n/{lg}.json: _idioma sem {sorted(falta)}")
        if len(conf["meses"]) != 12 or len(conf["meses_curtos"]) != 12:
            falha(f"i18n/{lg}.json: meses e meses_curtos precisam de 12 nomes")
        for k, v in (d.get("textos") or {}).items():
            if set(re.findall(r"\{(\w+)", k)) != set(re.findall(r"\{(\w+)", v)):
                falha(f"i18n/{lg}.json: marcadores {{…}} diferentes entre original e tradução: {k!r}")
            b = BASTIDOR.search(v) or BASTIDOR_TRAD.search(v)
            if b:
                falha(f"i18n/{lg}.json: bastidor no texto ({b.group(0)!r}): {v!r}")
        I18N[lg] = {"_idioma": conf, "textos": d.get("textos") or {}}
        ATIVOS.append(lg)


def tr(s, **kw):
    """Texto da interface no idioma da página. Em português devolve o próprio
    texto; nos outros, a tradução do dicionário — e anota o que faltar, para o
    build parar no fim em vez de publicar meia página em português."""
    if L != BASE_IDIOMA:
        USADOS[L].add(s)
        t = I18N[L]["textos"].get(s)
        if t and t.strip():
            s = t
        else:
            FALTANDO[L].add(s)
    return s.format(**kw) if kw else s


def cfg(k):
    return I18N[L]["_idioma"][k]


def prefixo(lg):
    return "" if lg == BASE_IDIOMA else f"{lg}/"


def url_de(lg, chave):
    """Endereço absoluto da página `chave` (caminho em português) no idioma lg."""
    return f"{DOMINIO}/{prefixo(lg)}{'' if chave == 'index.html' else chave}"


def link(base, chave, ancora=""):
    """href relativo para a página `chave` no idioma da página atual; se ela
    ainda não existe nesse idioma, cai no português (nunca num 404)."""
    lg = L if chave in EXISTE[L] else BASE_IDIOMA
    return f"{base}{prefixo(lg)}{chave}{ancora}"


def hreflang_de(chave):
    """' hreflang="pt-BR"' quando o link cai no português dentro de outro idioma."""
    if L != BASE_IDIOMA and chave not in EXISTE[L]:
        return f' hreflang="{CONFIG_PT["hreflang"]}"'
    return ""


def idiomas_da(chave):
    return [lg for lg in ATIVOS if chave in EXISTE[lg]]


def alternativos(chave):
    """[(hreflang, url)] da página em todos os idiomas em que ela existe, mais
    x-default (inglês quando existe, senão português). Vazio se só há um."""
    lgs = idiomas_da(chave)
    if len(lgs) < 2:
        return []
    alt = [(I18N[lg]["_idioma"]["hreflang"], url_de(lg, chave)) for lg in lgs]
    padrao = "en" if "en" in lgs else BASE_IDIOMA
    return alt + [("x-default", url_de(padrao, chave))]


def seletor_idioma(base):
    """Links para a mesma página nos outros idiomas — só os que existem."""
    lgs = idiomas_da(PAGINA)
    if len(lgs) < 2:
        return ""
    itens = []
    for lg in lgs:
        c = I18N[lg]["_idioma"]
        atual = ' aria-current="true"' if lg == L else ""
        itens.append(f'<a class="idioma" href="{base}{prefixo(lg)}{PAGINA}" hreflang="{c["hreflang"]}" lang="{c["hreflang"]}" '
                     f'aria-label="{e(c["nome"])}" title="{e(c["nome"])}"{atual}>{e(c["curto"])}</a>')
    return f'<div class="idiomas" role="group" aria-label="{e(tr("Idioma"))}">{"".join(itens)}</div>'


def marca_completa():
    sub = cfg("marca_sub")
    return f"{NOME} — {sub}" if sub else NOME


def licenca_rotulo(lic):
    return tr("Domínio público") if re.match(r"dom[ií]nio p[uú]blico$", lic.strip(), re.I) else lic


# --- tradução de conteúdo: travas -----------------------------------------------
# Campos que não se traduzem: se a tradução os trouxer, têm de ser idênticos;
# se omitir, vêm do original.
CAMPOS_FIXOS = {"num", "slug", "estreia", "proximo", "relacionados", "conf",
                "arquivo", "licenca", "licenca_url", "origem_url", "tipo", "ano", "foco", "url"}
# Campos que a tradução pode ter mesmo que o original não tenha.
EXTRAS_TRAD = {"nome_busca", "_excecoes_numeros", "_nota"}
# Texto citado (título de obra, de artigo) pode ficar igual ao original.
PODE_FICAR_IGUAL = re.compile(r"^fontes\[\d+\]\.texto$|\.autor$")
# "TBD" é bastidor, menos no nome do avião (Douglas TBD Devastator, Midway).
# "TODO" só em maiúscula: em espanhol "todo" é palavra comum.
BASTIDOR_TRAD = re.compile(r"(?-i:\bTODO\b)|\bTBD\b(?!-?\d*\s+Devastator)|\bFIXME\b|\[\?\]|\bto (?:check|verify|confirm)\b"
                           r"|\bpor (?:verificar|confirmar)\b|\bpendiente\b", re.I)

MESES_NOMES = {
    "pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
           "setembro", "outubro", "novembro", "dezembro"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre|setiembre", "octubre", "noviembre", "diciembre"],
}
MULTIPLICADOR = [  # o mais longo antes ("mil millones" = bilhão)
    (r"mil\s+millones", 10 ** 9), (r"bilh(?:ão|ões)|billions?", 10 ** 9),
    (r"milh(?:ão|ões)|millions?|millón|millones", 10 ** 6), (r"mil|thousand", 10 ** 3),
]
_MULT = "|".join(f"(?:{p})" for p, _ in MULTIPLICADOR)
_NUM = r"(?<![\w.,/:])(\d+(?:[.,]\d+)*)"


def _valor(s, lg):
    dec, mil = (".", ",") if lg == "en" else (",", ".")
    if re.fullmatch(rf"\d{{1,3}}(?:\{mil}\d{{3}})+(?:\{dec}\d+)?", s):
        s = s.replace(mil, "")
    s = s.replace(dec, ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def numeros_do_texto(txt, lg):
    """Multiconjunto dos números do texto, normalizados: 1.000 (pt) = 1,000 (en)
    = 1000; "20 mil" = "20,000"; "250–300 mil" = 250000 e 300000; 3/11/1924 =
    3 + novembro + 1924; o mês por extenso conta como número (M11)."""
    t = re.sub(r"(?<![\d/])(\d{1,2})º?/(\d{1,2})/(\d{4})\b", lambda m: f"{m[1]} §M{int(m[2])}§ {m[3]}", txt)
    c = Counter()
    for m in re.finditer(r"§M(\d+)§", t):
        c[f"M{int(m[1])}"] += 1
    # mês na caixa da ortografia (minúsculo em pt/es, maiúsculo em en):
    # "Rio de Janeiro" não é janeiro, e "may" (verbo) não é May
    for i, nomes in enumerate(MESES_NOMES[lg]):
        n = len(re.findall(rf"\b(?:{nomes})\b", t))
        if n:
            c[f"M{i + 1}"] += n
    # faixa com multiplicador no fim: "250–300 mil" → os dois lados multiplicam
    def faixa(m):
        mult = next(v for p, v in MULTIPLICADOR if re.fullmatch(p, m[3], re.I))
        a, b = _valor(m[1], lg), _valor(m[2], lg)
        if a is None or b is None:
            return m[0]
        # o primeiro lado só herda o multiplicador se veio "abreviado":
        # "250–300 mil" sim; "de 800.000 a 1,5 milhão" não
        return f"§N{a * mult if a < 1000 else a}§ – §N{b * mult}§"
    t = re.sub(_NUM + r"\s*(?:–|-|a|to|y|e|ou|or|o)\s*" + r"(\d+(?:[.,]\d+)*)\s+(" + _MULT + r")\b", faixa, t, flags=re.I)
    for m in re.finditer(r"§N([\d.]+)§", t):
        c[format(Decimal(m[1]).normalize(), "f")] += 1
    t = re.sub(r"§N[\d.]+§", " ", t)
    for m in re.finditer(_NUM + r"(?:\s+(" + _MULT + r")\b)?", t, re.I):
        v = _valor(m[1], lg)
        if v is None:
            continue
        if m[2]:
            v *= next(val for p, val in MULTIPLICADOR if re.fullmatch(p, m[2], re.I))
        c[format(v.normalize(), "f")] += 1
    return c


def conferir_numeros(orig, trad, lg, onde, excecoes):
    a, b = numeros_do_texto(orig, BASE_IDIOMA), numeros_do_texto(trad, lg)
    for x in excecoes:
        a.pop(x, None)
        b.pop(x, None)
    falta = a - b
    sobra = Counter({k: v for k, v in (b - a).items() if not k.startswith("M")})
    erros = []
    if falta:
        erros.append(f"{onde}: número do original ausente na tradução {dict(falta)}")
    if sobra:
        erros.append(f"{onde}: número na tradução que o original não tem {dict(sobra)}")
    return erros


def fundir_traducao(orig, trad, lg, onde="", excecoes=(), erros=None):
    """Confere a tradução contra o original, campo a campo, e devolve o objeto
    completo (campos fixos vêm do original). Acumula os erros em `erros`."""
    if isinstance(orig, dict):
        if not isinstance(trad, dict):
            erros.append(f"{onde or 'raiz'}: esperava objeto")
            return orig
        out = {}
        for k, v in orig.items():
            caminho = f"{onde}.{k}" if onde else k
            if k in CAMPOS_FIXOS:
                if k in trad and trad[k] != v:
                    erros.append(f"{caminho}: campo fixo diferente do original ({trad[k]!r} ≠ {v!r})")
                out[k] = v
            elif k not in trad:
                if v in (None, [], ""):
                    out[k] = v
                else:
                    erros.append(f"{caminho}: falta na tradução")
            else:
                out[k] = fundir_traducao(v, trad[k], lg, caminho, excecoes, erros)
        for k in trad:
            if k not in orig:
                if k in EXTRAS_TRAD:
                    out[k] = trad[k]
                else:
                    erros.append(f"{onde + '.' if onde else ''}{k}: campo que o original não tem")
        return out
    if isinstance(orig, list):
        if not isinstance(trad, list) or len(trad) != len(orig):
            erros.append(f"{onde}: a lista tem de ter {len(orig)} itens, como o original")
            return orig
        return [fundir_traducao(o, t, lg, f"{onde}[{i}]", excecoes, erros) for i, (o, t) in enumerate(zip(orig, trad))]
    if isinstance(orig, str):
        if not isinstance(trad, str) or not trad.strip():
            erros.append(f"{onde}: texto vazio na tradução")
            return orig
        erros += conferir_numeros(orig, trad, lg, onde, excecoes)
        if trad.strip() == orig.strip() and len(orig) >= 25 and " " in orig and not PODE_FICAR_IGUAL.search(onde):
            erros.append(f"{onde}: igual ao português — não traduzido?")
        b = BASTIDOR.search(trad) or BASTIDOR_TRAD.search(trad)
        if b:
            erros.append(f"{onde}: bastidor de produção ({b.group(0)!r})")
        return trad
    if trad != orig:
        erros.append(f"{onde}: valor {trad!r} diferente do original {orig!r}")
    return orig


def carregar_traducoes(itens, campos_obrigatorios, nome_item):
    """{idioma: {slug: item traduzido}} a partir de _src/<pasta>/<id>/NN-slug.json."""
    por_slug = {x["slug"]: x for x in itens}
    trads = {}
    for lg in ATIVOS:
        if lg == BASE_IDIOMA:
            continue
        trads[lg] = {}
        for f in sorted((SRC / PASTA_ITENS / lg).glob("[0-9][0-9]-*.json")):
            try:
                t = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as ex:
                falha(f"{PASTA_ITENS}/{lg}/{f.name} não é JSON válido: {ex}")
            orig = next((x for x in itens if f.name == f"{x['num']}-{x['slug']}.json"), None)
            if orig is None:
                falha(f"{PASTA_ITENS}/{lg}/{f.name}: não há {nome_item} com esse nome em _src/{PASTA_ITENS}/")
            erros = []
            exc = [format(_valor(x, BASE_IDIOMA).normalize(), "f") if re.fullmatch(r"[\d.,]+", x) else x
                   for x in t.get("_excecoes_numeros", [])]
            obj = fundir_traducao(orig, t, lg, "", exc, erros)
            falta = [c for c in campos_obrigatorios if c not in obj]
            if falta:
                erros.append(f"faltam campos obrigatórios {falta}")
            if erros:
                falha(f"tradução {PASTA_ITENS}/{lg}/{f.name} incompleta ou divergente:\n  " + "\n  ".join(erros))
            obj.pop("_excecoes_numeros", None)
            obj.pop("_nota", None)
            obj["_arquivo"] = f
            trads[lg][obj["slug"]] = obj
    return trads


def carregar_temas_traduzidos(temas, membros_por_idioma):
    """_src/temas.<id>.json: [{slug, nome, titulo, resumo, intro}] com os mesmos
    slugs de temas.json; a lista de membros vem do original. O tema só sai no
    idioma se tiver 2 ou mais membros traduzidos."""
    out = {}
    por_slug = {t["slug"]: t for t in temas}
    for lg in ATIVOS:
        if lg == BASE_IDIOMA:
            continue
        out[lg] = []
        arq = SRC / f"temas.{lg}.json"
        if not arq.exists():
            continue
        for tt in json.loads(arq.read_text(encoding="utf-8")):
            orig = por_slug.get(tt.get("slug"))
            if orig is None:
                falha(f"temas.{lg}.json: tema '{tt.get('slug')}' não existe em temas.json")
            erros = []
            base = {k: v for k, v in orig.items() if k != CHAVE_MEMBROS}
            obj = fundir_traducao(base, tt, lg, f"tema {orig['slug']}", (), erros)
            if erros:
                falha(f"temas.{lg}.json:\n  " + "\n  ".join(erros))
            obj[CHAVE_MEMBROS] = [s for s in orig[CHAVE_MEMBROS] if s in membros_por_idioma[lg]]
            if len(obj[CHAVE_MEMBROS]) >= 2:
                out[lg].append(obj)
    return out




def link_canal(classe, texto, sem_link="Em breve no YouTube"):
    if CANAL:
        return f'<a class="{classe}" href="{CANAL}" target="_blank" rel="noopener">{e(tr(texto))}</a>'
    return f'<span class="{classe}" aria-disabled="true">{e(tr(sem_link))}</span>'


# --- carga e conferência ----------------------------------------------------
ROTULO_LEIA = "Mais"


def ITEM_LEIA(y, base="../"):
    ch = f"batalhas/{y['slug']}.html"
    return (f'<li><a href="{link(base, ch)}"{hreflang_de(ch)}><span class="rotulo">{e(tr("Episódio"))} <b>{e(y["num"])}</b> · {e(y["campanha"])}</span>'
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
    temas = temas_de(x["slug"])
    if not rel and not temas:
        return ""
    base = "../../" if L != BASE_IDIOMA else "../"
    por_slug = {y["slug"]: y for y in todos}
    itens = "".join(ITEM_LEIA(por_slug[s], base) for s in rel)
    lista = f"<ul>{itens}</ul>" if itens else ""
    links = ""
    if temas:
        links = (f'<p class="temas-link"><span class="rotulo">{e(tr("Tema"))}</span> '
                 + " · ".join(f'<a href="{link(base, "temas/" + t["slug"] + ".html")}"{hreflang_de("temas/" + t["slug"] + ".html")}>{e(t["nome"])}</a>' for t in temas) + "</p>")
    return (f'<section class="leia" aria-labelledby="leia"><h2 id="leia"><span class="n">{e(tr(ROTULO_LEIA))}</span>{e(tr("Leia também"))}</h2>'
            f'{lista}{links}</section>')


def conferir_perguntas(nome, x):
    """`perguntas` (opcional): 3 a 5 itens {"p": "…?", "r": "…"}. O texto
    passa pela mesma trava de bastidor do resto da página (a conferência
    abaixo, em carregar(), lê o JSON inteiro menos imagens e fontes)."""
    ps = x.get("perguntas")
    if ps is None:
        return
    if not isinstance(ps, list) or not 3 <= len(ps) <= 5:
        falha(f"{nome}: perguntas deve ter de 3 a 5 itens")
    for it in ps:
        if not isinstance(it, dict) or set(it) != {"p", "r"} or not it["p"].strip() or not it["r"].strip():
            falha(f"{nome}: pergunta malformada {it!r}")
        if not it["p"].strip().endswith("?"):
            falha(f"{nome}: pergunta sem '?': {it['p']!r}")
        m = BASTIDOR.search(it["p"] + " " + it["r"])
        if m:
            falha(f"{nome}: bastidor de produção numa pergunta ({m.group(0)!r}): {it['p']!r}")


ROTULO_PERGUNTAS = "Perguntas"


def perguntas_html(x):
    """Seção "Perguntas frequentes" (h2 + h3/p). Sem JSON-LD de FAQ, de propósito."""
    ps = x.get("perguntas") or []
    if not ps:
        return ""
    itens = "".join(f"<h3>{e(it['p'])}</h3><p>{para(it['r'])}</p>" for it in ps)
    return f'<h2 id="perguntas"><span class="n">{e(tr(ROTULO_PERGUNTAS))}</span>{e(tr("Perguntas frequentes"))}</h2><div class="perguntas">{itens}</div>'


# --- temas ------------------------------------------------------------------
# Páginas-índice por assunto, em temas/<slug>.html, a partir de _src/temas.json.
TEMAS = []
CHAVE_MEMBROS = "batalhas"


def carregar_temas(itens):
    arq = SRC / "temas.json"
    if not arq.exists():
        return []
    try:
        temas = json.loads(arq.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        falha(f"temas.json não é JSON válido: {ex}")
    slugs = {x["slug"] for x in itens}
    vistos = set()
    for t in temas:
        for k in ("slug", "nome", "titulo", "resumo", "intro", CHAVE_MEMBROS):
            if not t.get(k):
                falha(f"tema sem '{k}': {t.get('slug')}")
        if not re.fullmatch(r"[a-z0-9-]+", t["slug"]) or t["slug"] in vistos:
            falha(f"tema com slug inválido ou repetido: {t['slug']!r}")
        vistos.add(t["slug"])
        if not 2 <= len(t["intro"]) <= 3:
            falha(f"tema {t['slug']}: a introdução tem de ter 2 ou 3 parágrafos")
        m = t[CHAVE_MEMBROS]
        if len(m) < 2 or len(set(m)) != len(m):
            falha(f"tema {t['slug']}: precisa de 2 ou mais itens, sem repetir")
        for s in m:
            if s not in slugs:
                falha(f"tema {t['slug']}: '{s}' não existe")
        texto = json.dumps(t, ensure_ascii=False)
        b = BASTIDOR.search(texto)
        if b:
            falha(f"tema {t['slug']}: bastidor de produção no texto público ({b.group(0)!r})")
    return temas


def titulo_tema(t):
    for x in (f"{t['titulo']} · {NOME}", t["titulo"]):
        if len(x) <= TITULO_MAX:
            return x
    falha(f"tema {t['slug']}: título com mais de {TITULO_MAX} caracteres")


def temas_de(slug):
    return [t for t in TEMAS if slug in t[CHAVE_MEMBROS]]


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
        conferir_perguntas(f.name, b)
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
    priv = f'<a href="{link(base, "privacidade.html")}"{hreflang_de("privacidade.html")}>{e(tr("política de privacidade"))}</a>'
    return f"""<div class="consentimento" id="consentimento" role="dialog" aria-live="polite" aria-label="{e(tr('Aviso de cookies'))}" hidden>
  <div class="casca">
    <p>{e(tr("Este site usa cookies do Google AdSense para exibir anúncios e medir audiência. Não pedimos cadastro nem e-mail."))} {tr("Detalhes na {politica}.", politica=priv)}</p>
    <div class="botoes">
      <button type="button" data-consent="recusar">{e(tr("Recusar anúncios"))}</button>
      <button type="button" data-consent="aceitar" class="principal">{e(tr("Entendi"))}</button>
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
    alt = alternativos(PAGINA) if indexar else []
    if alt:
        canon += "\n" + "\n".join(f'<link rel="alternate" hreflang="{h}" href="{e(u)}">' for h, u in alt)
    locs = "".join(f'\n<meta property="og:locale:alternate" content="{I18N[lg]["_idioma"]["og_locale"]}">'
                   for lg in idiomas_da(PAGINA) if lg != L) if indexar else ""
    return f"""<!doctype html>
<html lang="{cfg('hreflang')}">
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
<meta property="og:site_name" content="{e(marca_completa())}">
<meta property="og:locale" content="{cfg('og_locale')}">{locs}
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
<a class="pular" href="#conteudo">{e(tr("Pular para o conteúdo"))}</a>
"""


def topo(base, atual=""):
    cur = lambda k: ' aria-current="page"' if k == atual else ""
    sub = f'<small class="marca-sub" lang="{cfg("hreflang")}">{e(cfg("marca_sub"))}</small>' if cfg("marca_sub") else ""
    return f"""<header class="topo">
  <div class="casca">
    <a class="marca" href="{link(base, 'index.html')}"{'' if L == BASE_IDIOMA else ' lang="pt-BR"'}><img src="{base}assets/marca/cavalo-128.png" width="40" height="40" alt=""><span>Xadrez Bélico{sub}</span></a>
    <nav class="nav" aria-label="{e(tr('Principal'))}">
      <a href="{link(base, 'index.html', '#batalhas')}"{cur('batalhas')}>{e(tr('Batalhas'))}</a>
      <a href="{link(base, 'index.html', '#metodo')}"{cur('metodo')}>{e(tr('Método'))}</a>
      <a href="{link(base, 'sobre.html')}"{hreflang_de('sobre.html')}{cur('sobre')}>{e(tr('Sobre'))}</a>
      {link_canal('yt', 'YouTube', 'YouTube em breve')}{seletor_idioma(base)}
    </nav>
  </div>
</header>
"""


def rodape(base):
    ano = dt.date.today().year
    canal = f'<p><a href="{CANAL}" target="_blank" rel="noopener">{e(tr("Assista no YouTube"))}</a></p>' if CANAL else ""
    rever = f' <a href="#" role="button" data-rever-cookies>{e(tr("Rever escolha de cookies"))}</a>.' if ADSENSE_LIGADO else ""
    priv = f'<a href="{link(base, "privacidade.html")}"{hreflang_de("privacidade.html")}>{e(tr("Política de privacidade"))}</a>'
    return f"""<footer class="rodape">
  <div class="casca">
    <div>
      <h2>{e(marca_completa())}</h2>
      <p>{e(tr("Batalha explicada como partida: terreno, peças, lances e o erro de planejamento. Não é canal de heroísmo, é canal de causa."))}</p>
      {canal}
    </div>
    <div>
      <h2>{e(tr("Do mesmo criador"))}</h2>
      <ul>
        <li><a href="{SITE_IRMAO_VO}" rel="noopener">Vestígio Oculto</a> — {e(tr("arqueologia e mistério"))}</li>
        <li><a href="{SITE_IRMAO_AI}" rel="noopener">Arquitetura do Impossível</a> — {e(tr("como as grandes obras foram erguidas"))}</li>
      </ul>
    </div>
    <div>
      <h2>{e(tr("Este site"))}</h2>
      <ul>
        <li><a href="{link(base, 'sobre.html')}"{hreflang_de('sobre.html')}>{e(tr("Sobre"))}</a> · <a href="{link(base, 'contato.html')}"{hreflang_de('contato.html')}>{e(tr("Contato"))}</a></li>
        <li>{e(tr("Exibe anúncios do Google AdSense."))} {priv}.{rever}</li>
        <li>{e(tr("Só material de época ou foto real, com crédito. Nenhuma imagem gerada por IA."))}</li>
      </ul>
    </div>
    <div class="linha"><span>© {ano} {NOME} · {e(tr("textos autorais"))}</span><span>{e(tr("o que estava à vista, lido de novo"))}</span></div>
  </div>
</footer>
"""


SCRIPT = (RAIZ / "_src" / "pagina.js").read_text(encoding="utf-8") if (RAIZ / "_src" / "pagina.js").exists() else ""


def fim():
    return f"<script>\n{SCRIPT}\n</script>\n</body>\n</html>\n"


def conf_selo(c):
    cls, txt, tit = CONF[c]
    return f'<span class="conf {cls}" title="{e(tr(tit))}">{e(tr(txt))}</span>'


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
        return f'<span class="tarja">{e(tr("Foto de {ano}", ano=im["ano"]))}</span>'
    return ""


def credito(im):
    lic = e(licenca_rotulo(im["licenca"]))
    if im.get("licenca_url"):
        lic = f'<a href="{e(im["licenca_url"])}" rel="license noopener">{lic}</a>'
    autor = e(im["autor"])
    if im.get("origem_url"):
        autor = f'<a href="{e(im["origem_url"])}" rel="noopener">{autor}</a>'
    return f"{autor} · {lic}"


def selo_estreia(iso, classe="selo"):
    if not iso:
        return ""
    return f'<span class="{classe}" data-estreia="{iso}" data-no-ar="{e(tr("No ar"))}">{e(tr("Estreia"))} {e(data_br(iso))}</span>'


# --- imagem de compartilhamento -----------------------------------------------
def fonte(nome, tam):
    return ImageFont.truetype(str(SRC / "marca" / nome), tam)


def og_batalha(b, nome_arq=None, rotulo=None, titulo=None):
    """Imagem de compartilhamento 1200x630. Também serve às páginas de tema
    (nome_arq, rotulo e titulo próprios, sobre a capa da primeira batalha)."""
    destino = IMG / (nome_arq or f"og-{prefixo(L).replace('/', '-')}{b['slug']}.jpg")
    rotulo = rotulo or tr("EPISÓDIO {num}  ·  {data}", num=b['num'], data=b['data'].upper())
    titulo = (titulo or b["batalha"]).upper()
    capa = Image.open(IMG / b["imagens"][0]["arquivo"]).convert("RGB")
    im = ImageOps.fit(capa, (1200, 630), Image.LANCZOS, centering=(0.5, 0.45))
    im = Image.blend(im, ImageOps.colorize(ImageOps.grayscale(im), (23, 19, 16), (227, 210, 170)), 0.55)
    sombra = Image.new("L", (1, 630))
    for y in range(630):
        sombra.putpixel((0, y), int(245 * min(1, max(0, (y - 150) / 330)) ** 1.1))
    im = Image.composite(Image.new("RGB", im.size, (23, 19, 16)), im, sombra.resize((1200, 630)))
    d = ImageDraw.Draw(im)
    d.text((58, 372), rotulo, font=fonte("rotulo.ttf", 26), fill=(217, 151, 63))
    tam = 76
    while tam > 40 and d.textlength(titulo, font=fonte("titulo.ttf", tam)) > 1084:
        tam -= 4
    d.text((54, 412), titulo, font=fonte("titulo.ttf", tam), fill=(227, 210, 170))
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
    nomes = [base, re.sub(r"^(A|O|As|Os|The|La|El|Los|Las) ", "", base)]
    for meio in (tr(", lance a lance"), ""):
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


def conferir_seo(paginas, lg="pt"):
    """Porteiro: título até 60 e único; descrição de 120 a 155 e única —
    dentro de cada idioma."""
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
        falha(f"SEO [{lg}]\n  " + "\n  ".join(erros))


def seo_fixas():
    """(título, descrição) das páginas fixas no idioma da página atual."""
    return {
        "index.html": (tr("{nome}: a batalha explicada como partida", nome=NOME),
                       tr("História militar lida como tabuleiro: terreno, peças, lances e o erro de planejamento. "
                          "Por que o ataque deu certo, ou não deu. Com fonte.")),
        "sobre.html": (tr("Sobre o {nome}: como cada página é apurada", nome=NOME),
                       tr("O que é o {nome}, projeto independente de história militar: como cada página é apurada, "
                          "o selo de confiança dos números, as imagens e quem faz.", nome=NOME)),
        "contato.html": (tr("Contato · {nome}", nome=NOME),
                         tr("Como falar com o {nome} por e-mail: correções com fonte, créditos e retirada de imagens, "
                            "pedidos sobre seus dados (LGPD), pautas e imprensa.", nome=NOME)),
        "privacidade.html": (tr("Política de privacidade · {nome}", nome=NOME),
                             tr("Como o {nome} trata dados, cookies e publicidade do Google AdSense: o que coleta, o que não "
                                "coleta e quais são os seus direitos sob a LGPD.", nome=NOME)),
    }


# Sobre, contato e privacidade: em português o texto mora aqui no build; nos
# outros idiomas, em _src/paginas/<id>/<pagina>.html (só o <main>, com os
# marcadores {{…}} de corpo_fixo()). Sem o arquivo, a página não existe naquele
# idioma e os links para ela caem no português.
PAGINAS_FIXAS = ("sobre.html", "contato.html", "privacidade.html")


def fixa_traduzida(lg, chave):
    return SRC / "paginas" / lg / chave


def corpo_fixo(pt, chave, marcas):
    """O <main> da página fixa no idioma atual: o modelo em português (pt) ou o
    arquivo traduzido, com os marcadores {{…}} trocados. Para se sobrar um."""
    txt = pt if L == BASE_IDIOMA else fixa_traduzida(L, chave).read_text(encoding="utf-8")
    for k, v in marcas.items():
        txt = txt.replace("{{" + k + "}}", v)
    resto = re.findall(r"\{\{\w*\}\}", txt)
    if resto:
        falha(f"{L}/{chave}: marcador sem valor {sorted(set(resto))}")
    b = BASTIDOR.search(re.sub(r"<[^>]+>", " ", txt)) or (L != BASE_IDIOMA and BASTIDOR_TRAD.search(txt))
    if b:
        falha(f"{L}/{chave}: bastidor de produção no texto ({b.group(0)!r})")
    return txt


def canal_a():
    return f'<a href="{CANAL}" target="_blank" rel="noopener">@XadrezBélico</a>' if CANAL else ""


# --- home ------------------------------------------------------------------------
def card(b, base, texto=None):
    capa = b["imagens"][0]
    ch = f"batalhas/{b['slug']}.html"
    return f"""<li class="card revela">
  <div class="foto">{img_tag(capa['arquivo'], capa['alt'], base, '(max-width:720px) 100vw, 400px', foco=capa.get('foco'))}
    <span class="num">{e(b['num'])}</span>
    {selo_estreia(b['estreia'], 'selo')}
  </div>
  <div class="corpo">
    <span class="rotulo">{e(b['campanha'])}</span>
    <h3><a href="{link(base, ch)}"{hreflang_de(ch)}>{e(b['batalha'])}</a></h3>
    <div class="quando">{e(b['data'])} · {e(b['lugar'])}</div>
    <p class="perg">{para(texto or b['pergunta'])}</p>
    <div class="pe"><span>{e(tr('Episódio'))} {e(b['num'])}</span><span>{e(tr('Ler a partida →'))}</span></div>
  </div>
</li>"""


def card_producao(a):
    return f"""<li class="card producao revela">
  <div class="foto"><span class="num">{e(a['num'])}</span><span class="selo">{e(tr('Em produção'))}</span></div>
  <div class="corpo">
    <h3>{e(a['batalha'])}</h3>
    <div class="quando">{e(a['data'])} · {e(a['lugar'])}</div>
    <p class="perg">{para(a['pergunta'])}</p>
    <div class="pe"><span>{e(tr('Episódio'))} {e(a['num'])}</span><span>{(e(tr('Estreia')) + ' ' + e(data_br(a['estreia']))) if a.get('estreia') else ''}</span></div>
  </div>
</li>"""


# o escudo da abertura mede 300 px (160 no celular); servir o de 720 era o LCP do celular
ESCUDO_SIZES = "(max-width:820px) 160px, 300px"


def site_jsonld(descricao):
    """WebSite + Organization: a mesma entidade em todos os idiomas."""
    subs = [I18N[lg]["_idioma"]["marca_sub"] for lg in ATIVOS if I18N[lg]["_idioma"]["marca_sub"]]
    site = {"@type": "WebSite", "@id": DOMINIO + "/#site", "name": NOME, "url": DOMINIO + "/", "inLanguage": cfg("hreflang"),
            "description": tr("História militar explicada como partida de xadrez."),
            "publisher": {"@type": "Organization", "name": NOME, "url": DOMINIO + "/"}}
    if subs:
        site["alternateName"] = subs
    return {"@context": "https://schema.org", "@graph": [site, dict(ORG, sameAs=[CANAL] if CANAL else [])]}


def home(bs, og, total=None, banner=(0, 0)):
    """`bs`: as batalhas que existem no idioma da página; `total`: quantas há
    em português (nos outros idiomas, a home avisa que o resto está em português)."""
    base = "../" if L != BASE_IDIOMA else ""
    titulo, desc = seo_fixas()["index.html"]
    nomes = {"2+": tr("Confirmado"), "1": tr("Fonte única"), "DIV": tr("Divergência"), "sem": tr("Sem registro")}
    graus = "".join(f"<li>{conf_selo(k)}<p><strong>{e(nomes[k])}</strong>{e(tr(v[2]))}</p></li>" for k, v in CONF.items())
    prod = EM_PRODUCAO if L == BASE_IDIOMA else []
    cards = "\n".join(card(b, base) for b in bs) + "\n" + "\n".join(card_producao(a) for a in prod)
    resto = ""
    if total and total > len(bs):
        resto = (f'<p class="em-portugues"><a href="{base}index.html#batalhas" hreflang="{CONFIG_PT["hreflang"]}">'
                 f'{e(tr("As outras {n} batalhas ainda estão só em português →", n=total - len(bs)))}</a></p>')
    m = f"{base}assets/marca/"
    return (cabeca(titulo, desc, url_de(L, "index.html"), f"{DOMINIO}/assets/img/{og}", base, site_jsonld(desc))
            + topo(base) + f"""<main id="conteudo">
<section class="abre">
  <picture><source type="image/webp" srcset="{base}assets/img/banner.webp"><img src="{base}assets/img/banner.jpg" width="{banner[0]}" height="{banner[1]}" alt="" aria-hidden="true" fetchpriority="high" decoding="async"></picture>
  <div class="casca">
    <div>
      <div class="filete">{e(tr('Terreno · peças · lances'))}</div>
      <h1>{tr('A batalha, <em>como partida</em>')}</h1>
      <p class="lead">{e(tr('Por que este ataque deu certo, ou não deu, do ponto de vista do tabuleiro. O terreno, as peças de cada lado, a ordem dos lances e o erro de planejamento. Não é canal de heroísmo: é canal de causa.'))}</p>
      <div class="botoes">
        <a class="botao cheio" href="#batalhas">{e(tr('Ver as batalhas'))}</a>
        {link_canal('botao', 'Canal no YouTube')}
      </div>
    </div>
    <div class="escudo"><picture><source type="image/webp" srcset="{m}{webp(RAIZ / 'assets' / 'marca' / 'escudo-360.jpg')} 360w, {m}{webp(RAIZ / 'assets' / 'marca' / 'escudo.jpg')} 720w" sizes="{ESCUDO_SIZES}"><img src="{m}escudo.jpg" srcset="{m}escudo-360.jpg 360w, {m}escudo.jpg 720w" sizes="{ESCUDO_SIZES}" width="720" height="886" alt="{e(tr('Escudo do Xadrez Bélico: um cavalo de xadrez com elmo de crista'))}" fetchpriority="high" decoding="async"></picture></div>
  </div>
</section>

<section class="secao" id="batalhas">
  <div class="casca">
    <header>
      <div>
        <span class="rotulo">{e(tr('Tabuleiro'))} · <b>{len(bs) + len(prod):02d}</b> {e(tr('episódios'))}</span>
        <h2>{e(tr('As batalhas'))}</h2>
        <p>{e(tr('Cada página tem a ficha da batalha, a partida lance a lance, o veredito, os mitos contra o registro e as fontes.'))}</p>
      </div>
    </header>
    <ul class="batalhas">
{cards}
    </ul>{resto}
  </div>
</section>

{secao_temas(base)}
<section class="secao metodo" id="metodo">
  <div class="casca">
    <div>
      <span class="rotulo">{e(tr('Método'))}</span>
      <h2>{tr('O que estava à vista, <span class="destaque">lido de novo</span>')}</h2>
      <p>{e(tr('Público de história militar corrige data, unidade e calibre — e com razão. Cada número aqui leva um selo dizendo quanto se pode confiar nele.'))}</p>
      <p>{e(tr('Quando as fontes divergem, mostramos as versões e não escolhemos. Nome de unidade e horário só entram depois de conferidos. E nenhuma imagem deste site foi gerada por IA: é material de época, carta militar ou foto do lugar, com o ano na tela.'))}</p>
    </div>
    <ul class="graus">{graus}</ul>
  </div>
</section>
</main>
""" + rodape(base) + consentimento(base) + fim())


def secao_temas(base, atual=None, titulo="Temas", rotulo="Por assunto"):
    """Lista de temas: na home (seção #temas) e no pé de cada página de tema."""
    ts = [t for t in TEMAS if t["slug"] != atual]
    if not ts:
        return ""
    itens = "".join(f'<li><a href="{link(base, "temas/" + t["slug"] + ".html")}"><span class="rotulo">{len(t[CHAVE_MEMBROS]):02d} {e(tr("batalhas"))}</span>'
                    f'<strong>{e(t["nome"])}</strong></a></li>' for t in ts)
    sid = ' id="temas"' if atual is None else ""
    return f"""<section class="secao temas"{sid}>
  <div class="casca">
    <header><div><span class="rotulo">{e(tr(rotulo))}</span><h2>{e(tr(titulo))}</h2>
      <p>{e(tr('As batalhas agrupadas por guerra e por frente, para ler a campanha inteira.'))}</p></div></header>
    <ul class="temas-lista">{itens}</ul>
  </div>
</section>
"""


def pagina_tema(t, bs, og):
    base = "../../" if L != BASE_IDIOMA else "../"
    ch = f"temas/{t['slug']}.html"
    url = url_de(L, ch)
    por_slug = {b["slug"]: b for b in bs}
    membros = sorted((por_slug[s] for s in t[CHAVE_MEMBROS]), key=lambda b: b["num"])
    cards = "\n".join(card(b, base, b["resumo"]) for b in membros)
    inicio = url_de(L, "index.html")
    jsonld = [{
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": t["nome"], "headline": t["titulo"], "description": t["resumo"], "url": url, "inLanguage": cfg("hreflang"),
        "isPartOf": {"@type": "WebSite", "name": NOME, "url": DOMINIO + "/"},
        "image": {"@type": "ImageObject", "url": f"{DOMINIO}/assets/img/{og}", "width": 1200, "height": 630},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(membros), "itemListElement": [
            {"@type": "ListItem", "position": i, "url": url_de(L if f"batalhas/{b['slug']}.html" in EXISTE[L] else BASE_IDIOMA, f"batalhas/{b['slug']}.html"), "name": b["batalha"]}
            for i, b in enumerate(membros, start=1)]},
    }, migalhas((NOME, inicio), (tr("Temas"), inicio + "#temas"), (t["nome"], url))]
    intro = "".join(f"<p>{para(p)}</p>" for p in t["intro"])
    return (cabeca(titulo_tema(t), t["resumo"], url, f"{DOMINIO}/assets/img/{og}", base, jsonld)
            + topo(base, "temas") + f"""<main id="conteudo">
<section class="tema-abre">
  <div class="casca">
    <nav class="migalhas" aria-label="{e(tr('Você está em'))}"><a href="{link(base, 'index.html')}">{e(tr('Início'))}</a> / <a href="{link(base, 'index.html', '#temas')}">{e(tr('Temas'))}</a> / <span>{e(t['nome'])}</span></nav>
    <span class="rotulo">{e(tr('Tema'))} · <b>{len(membros):02d}</b> {e(tr('batalhas'))}</span>
    <h1>{e(t['nome'])}</h1>
    <div class="intro">{intro}</div>
  </div>
</section>
<section class="secao" id="batalhas">
  <div class="casca">
    <header><div><span class="rotulo">{e(tr('Tabuleiro'))}</span><h2>{e(tr('As batalhas deste tema'))}</h2></div></header>
    <ul class="batalhas">
{cards}
    </ul>
  </div>
</section>
{secao_temas(base, t['slug'], 'Outros temas', 'Mais')}
</main>
""" + rodape(base) + consentimento(base) + fim())


# --- página de batalha ---------------------------------------------------------------
def figura(im, n, base):
    leg = f"{im['legenda']} — {im['autor']}, {licenca_rotulo(im['licenca'])}"
    return f"""<figure class="fig revela">
  <button type="button" data-grande="{base}assets/img/{e(im['arquivo'])}" data-legenda="{e(leg)}" aria-label="{e(tr('Ampliar imagem: {alt}', alt=im['alt']))}">{img_tag(im['arquivo'], im['alt'], base, '(max-width:980px) 100vw, 720px')}{tarja(im)}</button>
  <figcaption><span class="fn">FIG. {n:02d}</span><span>{para(im['legenda'])}</span><small>{credito(im)}</small></figcaption>
</figure>"""


def pagina(b, bs, og):
    base = "../../" if L != BASE_IDIOMA else "../"
    url = url_de(L, f"batalhas/{b['slug']}.html")
    capa, resto = b["imagens"][0], b["imagens"][1:]
    secoes = []
    for i, s in enumerate(b["lances"]):
        sid = f"l{i+1}"
        corpo = "".join(f"<p>{para(p)}</p>" for p in s["paragrafos"])
        fig = figura(resto[i], i + 2, base) if i < len(resto) else ""
        secoes.append((sid, s["titulo"], f'<h2 id="{sid}"><span class="n">{e(tr("Lance"))} {i+1}</span>{e(s["titulo"])}</h2>{corpo}{fig}'))
    sobra = "".join(figura(im, len(b["lances"]) + 2 + k, base) for k, im in enumerate(resto[len(b["lances"]):]))

    numeros = "".join(f'<li><span class="valor">{e(n["valor"])}</span><span class="rot">{e(n["rotulo"])}</span>{conf_selo(n["conf"])}</li>' for n in b["numeros"])
    ficha = "".join(
        f'<tr><th scope="row">{e(f["item"])}</th><td class="v">{para(f["valor"])}'
        + (f'<span class="nota">{para(f["nota"])}</span>' if f.get("nota") else "")
        + f'</td><td class="c">{conf_selo(f["conf"])}</td></tr>' for f in b["ficha"])
    legenda_conf = "".join(f"<span>{conf_selo(k)} {e(tr(v[2]))}</span>" for k, v in CONF.items())
    mitos = "".join(f'<li><div><span class="rotulo">{e(tr("O que se conta"))}</span><p>{para(m["circula"])}</p></div><div><span class="rotulo"><b>{e(tr("O que o registro mostra"))}</b></span><p>{para(m["registro"])}</p></div></li>' for m in b["mitos"])
    fontes = "".join(
        f'<li>{para(f["texto"])}' + (f' — <a href="{e(f["url"])}" rel="noopener">{e(re.sub(r"^https?://(www[.])?", "", f["url"]).split("/")[0])}</a>' if f.get("url") else "") + "</li>"
        for f in b["fontes"])
    creditos = "".join(f'<li>Fig. {i+1:02d} — {e(im["legenda"])}: {credito(im)}</li>' for i, im in enumerate(b["imagens"]))
    indice = ([("ficha", tr("Ficha da batalha"))] + [(sid, t) for sid, t, _ in secoes] + [("veredito", tr("Veredito")), ("mitos", tr("Mitos e registro"))]
              + ([("perguntas", tr("Perguntas frequentes"))] if b.get("perguntas") else []) + [("fontes", tr("Fontes"))])
    indice_html = "".join(f'<li><a href="#{a}">{e(t)}</a></li>' for a, t in indice)

    i_atual = [x["slug"] for x in bs].index(b["slug"])
    ant = bs[i_atual - 1] if i_atual > 0 else None
    prox = next((x for x in bs if x["slug"] == b["proximo"]), None) if b["proximo"] else None
    bt = lambda x: f"batalhas/{x['slug']}.html"
    nav = f'<nav class="seguinte" aria-label="{e(tr("Outras batalhas"))}">'
    nav += (f'<a href="{link(base, bt(ant))}"{hreflang_de(bt(ant))}><span class="rotulo">← {e(tr("Episódio"))} {ant["num"]}</span><strong>{e(ant["batalha"])}</strong></a>' if ant else "<span></span>")
    nav += (f'<a href="{link(base, bt(prox))}"{hreflang_de(bt(prox))}><span class="rotulo">{e(tr("Episódio"))} {prox["num"]} →</span><strong>{e(prox["batalha"])}</strong></a>' if prox
            else f'<a href="{link(base, "index.html", "#batalhas")}"><span class="rotulo">{e(tr("Todas as batalhas →"))}</span><strong>{e(tr("O tabuleiro"))}</strong></a>')
    nav += "</nav>"

    estreia = ""
    if b["estreia"]:
        estreia = f' · <span data-estreia="{b["estreia"]}" data-no-ar="{e(tr("no ar"))}">{e(tr("estreia"))} {e(data_br(b["estreia"], True))}</span>'
    arq = b.get("_arquivo") or SRC / "batalhas" / f"{b['num']}-{b['slug']}.json"
    jsonld = [{
        "@context": "https://schema.org", "@type": "Article", "headline": tr("{batalha}: a partida explicada", batalha=b['batalha']),
        "description": b["resumo"], "inLanguage": cfg("hreflang"), "url": url,
        "image": {"@type": "ImageObject", "url": f"{DOMINIO}/assets/img/{og}", "width": 1200, "height": 630},
        "datePublished": data_git(arq, primeira=True), "dateModified": data_git(arq),
        "author": {"@type": "Organization", "name": NOME, "url": DOMINIO + "/"}, "publisher": ORG,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "articleSection": b["campanha"],
        "about": {"@type": "Event", "name": b["batalha"], "location": b["lugar"]},
    }, migalhas((NOME, url_de(L, "index.html")), (b["batalha"], url))]
    return (cabeca(titulo_seo(b), b["resumo"], url, f"{DOMINIO}/assets/img/{og}", base, jsonld, "article",
                   extra=preload_capa(capa["arquivo"], base))
            + '<div class="progresso" aria-hidden="true"></div>' + topo(base, "batalhas") + f"""<main id="conteudo">
<header class="capa">
  {img_tag(capa['arquivo'], capa['alt'], base, '100vw', 'eager', foco=capa.get('foco'))}
  {tarja(capa)}
  <span class="credito-capa">{e(capa['legenda'])} — {credito(capa)}</span>
  <div class="casca">
    <span class="rotulo">{e(tr('Episódio'))} <b>{e(b['num'])}</b> · {e(b['campanha'])}</span>
    <h1>{e(b['batalha'])}</h1>
    <div class="sub">{e(b['data'])} · {e(b['lugar'])}</div>
    <p class="perg">{para(b['pergunta'])}</p>
  </div>
</header>
<section class="placar" aria-label="{e(tr('A batalha em números'))}"><ul>{numeros}</ul></section>
<div class="casca layout">
  <article class="texto">
    <div class="abertura">{''.join(f'<p>{para(p)}</p>' for p in b['abertura'])}</div>

    <h2 id="ficha"><span class="n">{e(tr('Ficha'))}</span>{e(tr('Ficha da batalha'))}</h2>
    <div class="dossie"><table class="ficha"><tbody>{ficha}</tbody></table></div>
    <div class="legenda-conf">{legenda_conf}</div>

    {''.join(h for _, _, h in secoes)}
    {sobra}

    <h2 id="veredito"><span class="n">{e(tr('Veredito'))}</span>{e(tr('Por que deu no que deu'))}</h2>
    <div class="veredito">{''.join(f'<p>{para(p)}</p>' for p in b['veredito'])}</div>

    <h2 id="mitos"><span class="n">{e(tr('Mitos'))}</span>{e(tr('O que se conta e o que o registro mostra'))}</h2>
    <ul class="mitos">{mitos}</ul>

    {perguntas_html(b)}

    <section class="video">
      <div>
        <span class="rotulo">{e(tr('Episódio'))} {e(b['num'])}{estreia}</span>
        <h3>{e(b['titulo_video']) if b['titulo_video'] else e(tr('Episódio em produção'))}</h3>
      </div>
      {link_canal('botao cheio', 'Ver no YouTube')}
    </section>

    {leia_tambem(b, bs)}

    <h2 id="fontes"><span class="n">{e(tr('Fontes'))}</span>{e(tr('Fontes'))}</h2>
    <ol class="fontes">{fontes}</ol>
    <h3 style="margin-top:2rem">{e(tr('Imagens'))}</h3>
    <ul class="creditos">{creditos}</ul>
  </article>
  <aside class="indice" aria-label="{e(tr('Nesta página'))}">
    <div class="lado-card">
      <span class="rotulo">{e(tr('Ficha rápida'))}</span>
      <dl>
        <div><dt>{e(tr('Onde'))}</dt><dd>{e(b['lugar'])}</dd></div>
        <div><dt>{e(tr('Quando'))}</dt><dd>{e(b['data'])}</dd></div>
        <div><dt>{e(tr('Episódio'))}</dt><dd>{e(b['num'])} · {e(data_br(b['estreia'])) if b['estreia'] else e(b['campanha'])}</dd></div>
      </dl>
    </div>
    <span class="rotulo">{e(tr('Nesta página'))}</span>
    <ol>{indice_html}</ol>
  </aside>
</div>
{nav}
</main>
<div class="lupa" role="dialog" aria-modal="true" aria-label="{e(tr('Imagem ampliada'))}"><button type="button">{e(tr('Fechar'))}</button><img alt=""><p></p></div>
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
  <p>O <strong>{{NOME}}</strong> é um projeto editorial independente, publicado em {{DOMINIO_NU}}, {{CANAL_FRASE}}. Para qualquer assunto desta política — inclusive pedidos de exclusão ou de informação —, o contato é o e-mail divulgado no canal.</p>

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
    base = "" if L == BASE_IDIOMA else "../"
    if CANAL:
        canal = f'com canal correspondente no YouTube, {canal_a()}'
    else:
        canal = "com canal correspondente no YouTube"
    corpo = corpo_fixo(PRIVACIDADE, "privacidade.html",
                       {"NOME": NOME, "CANAL_FRASE": canal, "CANAL_A": canal_a(), "CHAVE": CHAVE_CONSENTIMENTO,
                        "DOMINIO_NU": DOMINIO.split("//")[1]})
    u = url_de(L, "privacidade.html")
    TITULO_PRIV, DESC_PRIV = seo_fixas()["privacidade.html"]
    return (cabeca(TITULO_PRIV, DESC_PRIV, u, f"{DOMINIO}/assets/img/og-home.jpg", base,
                   [{"@context": "https://schema.org", "@type": "WebPage", "name": TITULO_PRIV, "description": DESC_PRIV,
                     "url": u, "inLanguage": cfg("hreflang")},
                    migalhas((NOME, url_de(L, "index.html")), (tr("Política de privacidade"), u))])
            + topo(base) + corpo + rodape(base) + consentimento(base) + fim())


def pagina_sobre():
    base = "" if L == BASE_IDIOMA else "../"
    canal = f'no YouTube, {canal_a()}' if CANAL else "no YouTube"
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
  <p>O {NOME} é escrito, apurado e mantido de forma independente, sem vínculo com universidade, empresa ou órgão público. É do mesmo criador de outros dois projetos com o mesmo cuidado com a fonte: <a href="{SITE_IRMAO_VO}" rel="noopener">Vestígio Oculto</a>, sobre arqueologia e mistério, e <a href="{SITE_IRMAO_AI}" rel="noopener">Arquitetura do Impossível</a>, sobre como as grandes obras foram erguidas.</p>
  <p>O site se mantém com anúncios do Google AdSense, descritos na <a href="privacidade.html">política de privacidade</a>. Nenhum anúncio interfere no que é escrito.</p>
</div></main>
"""
    corpo = corpo_fixo(corpo, "sobre.html", {"NOME": NOME, "CANAL_A": canal_a(),
                                             "SITE_IRMAO_VO": SITE_IRMAO_VO, "SITE_IRMAO_AI": SITE_IRMAO_AI})
    u = url_de(L, "sobre.html")
    TITULO_SOBRE, DESC_SOBRE = seo_fixas()["sobre.html"]
    return (cabeca(TITULO_SOBRE, DESC_SOBRE, u, f"{DOMINIO}/assets/img/og-home.jpg", base,
                   [{"@context": "https://schema.org", "@type": "AboutPage", "name": TITULO_SOBRE, "description": DESC_SOBRE,
                     "url": u, "inLanguage": cfg("hreflang")},
                    migalhas((NOME, url_de(L, "index.html")), (tr("Sobre"), u))])
            + topo(base, "sobre") + corpo + rodape(base) + consentimento(base) + fim())


def pagina_contato():
    base = "" if L == BASE_IDIOMA else "../"
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
    corpo = corpo_fixo(corpo, "contato.html", {"NOME": NOME})
    u = url_de(L, "contato.html")
    TITULO_CONTATO, DESC_CONTATO = seo_fixas()["contato.html"]
    return (cabeca(TITULO_CONTATO, DESC_CONTATO, u, f"{DOMINIO}/assets/img/og-home.jpg", base,
                   [{"@context": "https://schema.org", "@type": "ContactPage", "name": TITULO_CONTATO, "description": DESC_CONTATO,
                     "url": u, "inLanguage": cfg("hreflang")},
                    migalhas((NOME, url_de(L, "index.html")), (tr("Contato"), u))])
            + topo(base, "contato") + corpo + rodape(base) + consentimento(base) + fim())

def sitemap_xml(entradas):
    """Um sitemap só, com as versões de cada página em xhtml:link (hreflang)."""
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for lg, chave, data in entradas:
        alt = alternativos(chave)
        extra = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{h}" href="{u}"/>' for h, u in alt)
        linhas.append(f"  <url><loc>{url_de(lg, chave)}</loc><lastmod>{data}</lastmod>{extra}{chr(10) + '  ' if extra else ''}</url>")
    return "\n".join(linhas) + "\n</urlset>\n"


def main():
    global TEMAS, L, PAGINA
    bs = carregar()
    temas_pt = carregar_temas(bs)
    carregar_idiomas()
    trads = carregar_traducoes(bs, OBRIGATORIOS, "batalha")
    for lg, d in trads.items():
        for b in d.values():
            conferir_perguntas(f"{PASTA_ITENS}/{lg}/{b['_arquivo'].name}", b)
    temas_por = {BASE_IDIOMA: temas_pt, **carregar_temas_traduzidos(temas_pt, {lg: set(d) for lg, d in trads.items()})}
    # idioma sem nenhuma batalha traduzida ainda não entra no ar
    for lg in list(ATIVOS):
        if lg != BASE_IDIOMA and not trads.get(lg):
            ATIVOS.remove(lg)
            print(f"idioma '{lg}': dicionário pronto, nenhuma batalha traduzida — fica fora do ar")

    # o que existe em cada idioma (decide links, hreflang e seletor)
    EXISTE[BASE_IDIOMA] = ({"index.html", "sobre.html", "contato.html", "privacidade.html"}
                           | {f"batalhas/{b['slug']}.html" for b in bs} | {f"temas/{t['slug']}.html" for t in temas_pt})
    for lg in ATIVOS[1:]:
        EXISTE[lg] = ({"index.html"} | {f"batalhas/{s}.html" for s in trads[lg]}
                      | {f"temas/{t['slug']}.html" for t in temas_por[lg]}
                      | {c for c in PAGINAS_FIXAS if fixa_traduzida(lg, c).exists()})

    def lista_de(lg):
        """Todas as batalhas, na versão do idioma quando existe (links e "Leia também")."""
        return bs if lg == BASE_IDIOMA else [trads[lg].get(b["slug"], b) for b in bs]

    def traduzidas(lg):
        return bs if lg == BASE_IDIOMA else [trads[lg][b["slug"]] for b in bs if b["slug"] in trads[lg]]

    for lg in ATIVOS:
        L = lg
        TEMAS = temas_por[lg]
        fixas = seo_fixas()
        seo = {k: v for k, v in fixas.items() if k in EXISTE[lg]}
        seo.update({f"batalhas/{b['slug']}": (titulo_seo(b), b["resumo"]) for b in traduzidas(lg)})
        seo.update({f"temas/{t['slug']}": (titulo_tema(t), t["resumo"]) for t in TEMAS})
        conferir_seo(seo, lg)

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
    og_casa = og_home()

    saida = {}           # caminho relativo -> html (grava só no fim, se tudo passou)
    datas = {}           # (idioma, chave) -> lastmod
    fixas_data = data_git(Path(__file__).resolve())
    for lg in ATIVOS:
        L = lg
        TEMAS = temas_por[lg]
        pre = prefixo(lg)
        todas = lista_de(lg)
        delas = traduzidas(lg)
        for b in delas:
            PAGINA = f"batalhas/{b['slug']}.html"
            saida[pre + PAGINA] = pagina(b, todas, og_batalha(b))
            datas[(lg, PAGINA)] = data_git(b.get("_arquivo") or SRC / "batalhas" / f"{b['num']}-{b['slug']}.json")
        por_slug = {b["slug"]: b for b in todas}
        d_temas = data_git(SRC / ("temas.json" if lg == BASE_IDIOMA else f"temas.{lg}.json")) if TEMAS else fixas_data
        for t in TEMAS:
            PAGINA = f"temas/{t['slug']}.html"
            primeira = min((por_slug[s] for s in t[CHAVE_MEMBROS]), key=lambda b: b["num"])
            og_t = og_batalha(primeira, f"og-{pre.replace('/', '-')}tema-{t['slug']}.jpg",
                              tr("TEMA  ·  {n} BATALHAS", n=len(t[CHAVE_MEMBROS])), t["nome"])
            saida[pre + PAGINA] = pagina_tema(t, todas, og_t)
            datas[(lg, PAGINA)] = max([d_temas, fixas_data] + [datas[(lg, f"batalhas/{s}.html")] for s in t[CHAVE_MEMBROS]])
        PAGINA = "index.html"
        saida[pre + PAGINA] = home(delas, og_casa, total=len(bs), banner=(ban.width, ban.height))
        for chave, fn in (("privacidade.html", pagina_privacidade), ("sobre.html", pagina_sobre),
                          ("contato.html", pagina_contato)):
            if chave in EXISTE[lg]:
                PAGINA = chave
                saida[pre + chave] = fn()
                datas[(lg, chave)] = (fixas_data if lg == BASE_IDIOMA
                                      else max(fixas_data, data_git(fixa_traduzida(lg, chave))))
        if lg == BASE_IDIOMA:
            PAGINA = "404.html"
            saida["404.html"] = pagina_404()
        datas[(lg, "index.html")] = max([fixas_data] + [d for (l2, _), d in datas.items() if l2 == lg])

    faltam = {lg: sorted(v) for lg, v in FALTANDO.items() if v}
    if faltam:
        falha("textos da interface sem tradução (acrescente em _src/i18n/<id>.json, em \"textos\"):\n"
              + "\n".join(f"  [{lg}] {s!r}" for lg, v in faltam.items() for s in v))
    fonte_build = Path(__file__).read_text(encoding="utf-8")
    for lg in ATIVOS[1:]:
        # o que nenhuma página usou E não aparece mais no build: o original mudou
        sobra = {s for s in set(I18N[lg]["textos"]) - USADOS[lg] if s not in fonte_build}
        if sobra:
            print(f"aviso [{lg}]: {len(sobra)} texto(s) no dicionário que o build não usa mais (original mudou?):")
            for s in sorted(sobra):
                print("   ", repr(s[:90]))

    # grava, e apaga as páginas que deixaram de ser geradas
    for rel, txt in saida.items():
        destino = RAIZ / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(txt, encoding="utf-8")
    pastas = [RAIZ / "batalhas", RAIZ / "temas"] + [RAIZ / lg / sub for lg in IDIOMAS if lg != BASE_IDIOMA
                                                   for sub in ("batalhas", "temas", "")]
    for pasta in pastas:
        if pasta.is_dir():
            for velho in pasta.glob("*.html"):
                rel = str(velho.relative_to(RAIZ)).replace("\\", "/")
                if rel not in saida:
                    velho.unlink()
                    print("removido (fora do build):", rel)
    for lg in IDIOMAS:
        if lg != BASE_IDIOMA:
            for sub in ("batalhas", "temas", ""):
                d = RAIZ / lg / sub
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()

    ads = RAIZ / "ads.txt"
    if ADSENSE_LIGADO:
        ads.write_text("# Declaração de vendedor autorizado (IAB ads.txt)\n"
                       "# Gerado por _src/build.py a partir de ADSENSE_PUB. Não editar à mão.\n"
                       f"google.com, {ADSENSE_PUB}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    elif ads.exists():
        ads.unlink()

    # sitemap: português primeiro, na ordem de sempre; depois cada idioma
    ordem = []
    for lg in ATIVOS:
        chaves = (["index.html"] + [f"batalhas/{b['slug']}.html" for b in bs]
                  + list(PAGINAS_FIXAS)
                  + [f"temas/{t['slug']}.html" for t in temas_por[lg]])
        ordem += [(lg, c, datas[(lg, c)]) for c in chaves if (lg, c) in datas]
    (RAIZ / "sitemap.xml").write_text(sitemap_xml(ordem), encoding="utf-8")
    (RAIZ / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /_src/\n\nSitemap: {DOMINIO}/sitemap.xml\n", encoding="utf-8")

    L = BASE_IDIOMA
    print(f"ok: {len(bs)} batalhas, {len(EM_PRODUCAO)} em produção, {len(temas_pt)} temas · idiomas no ar: {', '.join(ATIVOS)}"
          + ("" if CANAL else " · CANAL do YouTube não definido"))
    for lg in ATIVOS[1:]:
        print(f"  [{lg}] {len(trads[lg])} batalha(s) traduzida(s): {', '.join(sorted(trads[lg]))}; {len(temas_por[lg])} tema(s)")
    for b in bs:
        print(f"  {b['num']} {b['batalha']}: {len(b['ficha'])} linhas de ficha, {len(b['lances'])} lances, {len(b['imagens'])} imagens")


if __name__ == "__main__":
    main()
