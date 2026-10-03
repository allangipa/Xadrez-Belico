# Xadrez Bélico — site

Site do canal **Xadrez Bélico**, em `xadrezbelico.com.br`. Estático, sem
framework e sem build no servidor — o mesmo desenho do site do Arquitetura do
Impossível: gera aqui, commit e push no GitHub, e a Hostinger publica.

## Como gerar

```bash
python _src/build.py
```

Nunca edite `index.html`, `batalhas/*.html` nem `404.html`: são gerados.

## De onde vem o conteúdo

Cada batalha é um JSON em `_src/batalhas/NN-slug.json` (esquema em
`_src/batalhas/ESQUEMA.md`). **Nenhum texto de batalha mora em template.**
O JSON sai da apuração do episódio, que é a fonte:

```
Canais do YouTube\Xadrez Bélico\Roteiros\NN Tema\VERIFICACAO.md
Canais do YouTube\Xadrez Bélico\Roteiros\APURACAO NN - Tema.md
```

e das NOTAS DE VERIFICAÇÃO no fim de cada roteiro. Se o site e o vídeo
divergirem, quem manda é a apuração.

As imagens saem de `arquivo\` e `cartas\` do episódio, com autor e licença do
`MANIFESTO.tsv`.

## Regras de imagem — mais duras que as do vídeo

- **Nenhuma imagem gerada por IA no site.** No vídeo elas entram com tarja;
  aqui não entram. Só material de época (`tipo: epoca`), carta militar
  (`carta`) ou foto do lugar hoje (`atual`, com `ano` — vira a tarja
  "FOTO DE AAAA", regra da casa de 01/10/2026). O build para se faltar.
- Domínio público, CC0, CC BY, CC BY-SA. **NC e "No known copyright
  restrictions" não entram**, e o build para.
- **Sem símbolo nazista em destaque**, sem foto de atrocidade, sem
  reconstituição moderna nem guerra/lugar/década errada (ver o CLAUDE.md do
  canal, "O símbolo nazista na tela").

## O build é porteiro

Para, sem gerar nada, quando falta campo, quando `proximo` aponta para
batalha inexistente, quando uma imagem não existe, tem licença recusada, é
gerada, ou é foto atual sem ano, e quando o texto público carrega bastidor
de produção ("apuração", "roteiro", "bloco 3", `[2+]`, nome de arquivo…).

## Nova batalha

1. `_src/batalhas/NN-slug.json` seguindo o esquema.
2. Fotos em `assets/img/NN-nome.jpg` (1600 px, JPEG 82) e `NN-nome-800.jpg`.
3. No JSON anterior, `proximo` aponta para o novo slug.
4. Se estava em `EM_PRODUCAO` no `_src/build.py`, tire de lá.
5. `python _src/build.py`.

## Identidade

Do CLAUDE.md do canal, "mesa de guerra à luz de lampião": fundo `#171310`,
tinta `#2A1D12`/`#4A3823`, pergaminho `#E3D2AA`/`#C9B384`, âmbar de lampião
`#D9973F`; vermelho `#8C2F2F` e azul `#3A5A80` são cores de facção. A ficha
de cada batalha é um dossiê em pergaminho.

Fontes: a marca usa Bookman Old Style e Franklin Gothic, que são da
Microsoft e **não podem ser servidas** num site. No lugar, todas SIL OFL e
servidas daqui (`assets/fontes/`): **Libre Baskerville** nos títulos,
**Archivo Narrow** nos rótulos, **Libre Franklin** no corpo. Cinzel é do
Vestígio e não entra.

O escudo e o cavalo (`assets/marca/`) são recortes do logo do canal
(`Youtube Logo Pequena.jpeg`); o fundo da abertura é o banner.

## Canal no YouTube

**@XadrezBélico** — `CANAL` em `_src/build.py`
(`https://www.youtube.com/@XadrezB%C3%A9lico`, confirmado pelo Allan em
02/10/2026). Alimenta o botão do menu, os da abertura e de cada batalha, o
rodapé e as páginas Sobre e Privacidade. `None` volta a mostrar "em breve no
YouTube", sem link.

## AdSense

Mesma conta e mesmo publisher do Vestígio Oculto: `pub-4401770243539507`.
Tudo sai de três constantes no topo do `_src/build.py`:

- `ADSENSE_LIGADO` — interruptor geral. `False` tira a meta e a faixa de
  todas as páginas e apaga o `ads.txt`.
- `ADSENSE_PUB` — o publisher; o `ads.txt` é gerado a partir dele.
- `CONSENTIMENTO_BLOQUEIA` — `False` (igual ao Vestígio): o anúncio carrega
  na hora e quem clica em "Recusar anúncios" deixa de receber. `True`: nada
  de anúncio até "Entendi".

O `<head>` de cada página leva só a meta `google-adsense-account` (é por ela
que o AdSense verifica o site). O script `adsbygoogle.js` **não** vai escrito
no HTML: a faixa de consentimento o injeta, e só quando pode. Os anúncios
são os automáticos, configurados no painel do AdSense — não há bloco de
anúncio posicionado à mão.

A página `privacidade.html` é gerada pelo build e descreve só o que este site
faz. Mudou algo (outra rede, medição, comentários): muda o texto e a data.

## Publicar

**No ar desde 02/10/2026** em https://xadrezbelico.com.br, com SSL (o http
redireciona para https, e o www funciona).

Repositório: https://github.com/allangipa/Xadrez-Belico, branch `main`.
**Cada push na `main` publica o site** — o Git do painel da Hostinger
(Sites → xadrezbelico.com.br → Avançado → Git, diretório = raiz) puxa o
commit e põe no ar em segundos.

```bash
python _src/build.py
git add -A
git commit -m "o que mudou"
git push
```

**Rode o build antes do commit.** O servidor não gera nada: ele publica os
`.html` que estão no repositório. Mudou um JSON e não rodou o build, o site
continua com o texto velho — sem erro nenhum.

E confira no ar, não no terminal: abra a página que mudou (ou
`curl -s https://xadrezbelico.com.br/batalhas/<slug>.html | grep "<trecho novo>"`).
O push dar certo não prova que o deploy deu.

### O que o `.htaccess` segura

Com o deploy por Git o repositório **inteiro** vai para o servidor. O
`.htaccess` é o que impede o resto de ser servido:

- `404.html` como página de erro;
- 404 para `_src/`, `.claude/`, `.git/`, `README.md` e `.gitignore`.

Arquivo novo na raiz que não seja página **fica público** até entrar nessa
lista. Na dúvida, ponha dentro de `_src/`.

### Publicação por pacote (só se o Git falhar)

A primeira publicação, antes de o Git ser ligado, foi por pacote, pelo plugin
da Hostinger: zip só com o que é servido (`index.html`, `404.html`,
`robots.txt`, `sitemap.xml`, `.htaccess`, `batalhas/` e `assets/`), envio
para `public_html` e "deploy static site archive". **Esse deploy apaga a
pasta inteira do site antes de extrair**: o pacote vai sempre completo.
