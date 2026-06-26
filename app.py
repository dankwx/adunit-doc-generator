#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de documento de Ad Units (.docx)

Interface web simples: cole o texto com os blocos <div data-adunit=...>,
revise/edite as descricoes e gere um .docx no mesmo formato do adunits.docx.

Sem dependencias externas: usa apenas a biblioteca padrao do Python.
O .docx de referencia (adunits.docx) e usado como modelo - apenas o
word/document.xml e substituido, preservando estilos, fontes, header e footer.
"""

import io
import os
import re
import json
import zipfile
import webbrowser
import threading
from html import escape as html_escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DOCX = os.path.join(BASE_DIR, "adunits.docx")
PREFIX_XML = os.path.join(BASE_DIR, "templates_xml", "prefix.xml")
SUFFIX_XML = os.path.join(BASE_DIR, "templates_xml", "suffix.xml")

DEFAULT_TITLE = "Ad Units Manuais | Web"

# Cores do syntax highlight (esquema VS Code Dark+), iguais ao documento original.
COL_PUNCT = "9b9b9b"   # < > = / e espacos
COL_TAG = "569cd6"     # nome da tag (div)
COL_ATTR = "9cdcfe"    # nomes de atributo (data-adunit, ...)
COL_STRING = "d69d85"  # valores entre aspas


def parse_text(text: str):
    """Extrai blocos <div ... data-adunit="NOME" ...></div> do texto."""
    blocks = []
    for m in re.finditer(r"<div\b[^>]*?>\s*</div>", text, re.IGNORECASE | re.DOTALL):
        raw = m.group(0)
        # normaliza para uma unica linha: <div ...></div>
        code = re.sub(r"\s*\n\s*", " ", raw).strip()
        code = re.sub(r">\s*</div>", "></div>", code)
        am = re.search(r'data-adunit\s*=\s*"([^"]*)"', code, re.IGNORECASE)
        adunit = am.group(1).strip() if am else ""
        if not adunit:
            continue
        blocks.append({
            "adunit": adunit,
            "code": code,
            # tokens p/ a previa fiel no navegador (mesmas cores do .docx)
            "tokens": tokenize_html(code),
        })
    return blocks


# ---------------------------------------------------------------------------
# Geracao do DOCX
# ---------------------------------------------------------------------------

def xescape(s: str) -> str:
    """Escapa texto para dentro de um elemento <w:t>."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def heading_xml(adunit: str) -> str:
    name = xescape(adunit)
    rpr_para = ('<w:rPr><w:rFonts w:ascii="Montserrat" w:cs="Montserrat" '
                'w:eastAsia="Montserrat" w:hAnsi="Montserrat"/><w:b w:val="1"/>'
                '<w:bCs w:val="1"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>')
    rpr_name = ('<w:rPr><w:rFonts w:ascii="Montserrat" w:cs="Montserrat" '
                'w:eastAsia="Montserrat" w:hAnsi="Montserrat"/><w:b w:val="1"/>'
                '<w:bCs w:val="1"/><w:sz w:val="24"/><w:szCs w:val="24"/>'
                '<w:rtl w:val="0"/></w:rPr>')
    return (
        '<w:p><w:pPr>' + rpr_para + '</w:pPr>'
        '<w:r>' + rpr_name + '<w:t xml:space="preserve">' + name + '</w:t></w:r>'
        '</w:p>'
    )


def tokenize_html(code: str):
    """Quebra o trecho HTML em runs (texto, cor) p/ syntax highlight."""
    runs = []
    i, n = 0, len(code)
    expect_tag = False  # proximo identificador e um nome de tag?
    while i < n:
        c = code[i]
        if c == "<":
            if code[i:i + 2] == "</":
                runs.append(("</", COL_PUNCT)); i += 2
            else:
                runs.append(("<", COL_PUNCT)); i += 1
            expect_tag = True
        elif c == ">":
            runs.append((">", COL_PUNCT)); i += 1; expect_tag = False
        elif c in "/=":
            runs.append((c, COL_PUNCT)); i += 1
        elif c in "\"'":
            j = i + 1
            while j < n and code[j] != c:
                j += 1
            j = min(j + 1, n)
            runs.append((code[i:j], COL_STRING)); i = j
        elif c.isspace():
            j = i
            while j < n and code[j].isspace():
                j += 1
            runs.append((code[i:j], COL_PUNCT)); i = j
        elif c.isalpha() or c == "_":
            j = i
            while j < n and (code[j].isalnum() or code[j] in "-_:"):
                j += 1
            word = code[i:j]
            runs.append((word, COL_TAG if expect_tag else COL_ATTR))
            expect_tag = False
            i = j
        else:
            runs.append((c, COL_PUNCT)); i += 1
    # junta runs adjacentes de mesma cor
    merged = []
    for txt, col in runs:
        if merged and merged[-1][1] == col:
            merged[-1] = (merged[-1][0] + txt, col)
        else:
            merged.append([txt, col])
    return merged


def code_run_xml(text: str, color: str) -> str:
    rpr = ('<w:rPr><w:rFonts w:ascii="Consolas" w:cs="Consolas" '
           'w:eastAsia="Consolas" w:hAnsi="Consolas"/><w:color w:val="' + color + '"/>'
           '<w:shd w:fill="1e1e1e" w:val="clear"/><w:rtl w:val="0"/></w:rPr>')
    return ('<w:r>' + rpr + '<w:t xml:space="preserve">'
            + xescape(text) + '</w:t></w:r>')


def code_table_xml(code: str) -> str:
    ppr_rpr = ('<w:rPr><w:rFonts w:ascii="Consolas" w:cs="Consolas" '
               'w:eastAsia="Consolas" w:hAnsi="Consolas"/><w:color w:val="9b9b9b"/>'
               '<w:shd w:fill="1e1e1e" w:val="clear"/></w:rPr>')
    runs = "".join(code_run_xml(t, c) for t, c in tokenize_html(code))
    return (
        '<w:tbl><w:tblPr><w:tblStyle w:val="Table2"/>'
        '<w:tblW w:w="8630.0" w:type="dxa"/><w:jc w:val="left"/>'
        '<w:tblLayout w:type="fixed"/><w:tblLook w:val="0600"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="8630"/></w:tblGrid>'
        '<w:tr><w:trPr><w:cantSplit w:val="0"/><w:tblHeader w:val="0"/></w:trPr>'
        '<w:tc><w:tcPr><w:shd w:fill="1e1e1e" w:val="clear"/>'
        '<w:tcMar><w:top w:w="100.0" w:type="dxa"/><w:left w:w="100.0" w:type="dxa"/>'
        '<w:bottom w:w="100.0" w:type="dxa"/><w:right w:w="100.0" w:type="dxa"/></w:tcMar>'
        '<w:vAlign w:val="top"/></w:tcPr>'
        '<w:p><w:pPr><w:widowControl w:val="0"/>'
        '<w:spacing w:after="0" w:before="0" w:line="276" w:lineRule="auto"/>'
        '<w:jc w:val="left"/>' + ppr_rpr + '</w:pPr>'
        + runs +
        '</w:p></w:tc></w:tr></w:tbl>'
    )


def spacer_paragraph() -> str:
    return ('<w:p><w:pPr><w:rPr><w:rFonts w:ascii="Montserrat" w:cs="Montserrat" '
            'w:eastAsia="Montserrat" w:hAnsi="Montserrat"/><w:sz w:val="20"/>'
            '<w:szCs w:val="20"/></w:rPr></w:pPr></w:p>')


def build_document_xml(title: str, blocks: list) -> str:
    prefix = open(PREFIX_XML, encoding="utf-8").read()
    suffix = open(SUFFIX_XML, encoding="utf-8").read()

    # Troca o titulo (primeiro <w:t> do documento, dentro do paragrafo Title).
    if title and title != DEFAULT_TITLE:
        prefix = prefix.replace(
            ">" + DEFAULT_TITLE + "<",
            ">" + xescape(title) + "<",
            1,
        )

    body = []
    for b in blocks:
        body.append(heading_xml(b["adunit"]))
        body.append(code_table_xml(b["code"]))
        body.append(spacer_paragraph())

    return prefix + "".join(body) + suffix


def build_docx(title: str, blocks: list) -> bytes:
    document_xml = build_document_xml(title, blocks)
    src = zipfile.ZipFile(TEMPLATE_DOCX, "r")
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                data = document_xml.encode("utf-8")
            dst.writestr(item, data)
    src.close()
    return out_buf.getvalue()


# ---------------------------------------------------------------------------
# Servidor web
# ---------------------------------------------------------------------------

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gerador de Ad Units (.docx)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root { --bg:#1e1e1e; --fg:#e8e8e8; --accent:#ff7c1d; --muted:#9b9b9b; }
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", Roboto, Arial, sans-serif; margin:0;
         background:#f4f5f7; color:#26292c; }
  header { background:#36384c; color:#fff; padding:18px 24px; }
  header h1 { margin:0; font-size:20px; }
  header span { color:var(--accent); }
  main { max-width:1400px; margin:0 auto; padding:24px; }
  .layout { display:flex; gap:24px; align-items:flex-start; }
  .pane-left { flex:1 1 0; min-width:340px; }
  .pane-right { flex:1 1 0; min-width:340px; position:sticky; top:24px;
               align-self:flex-start; }
  @media (max-width:900px) { .layout { flex-direction:column; }
               .pane-right { position:static; } }
  label { font-weight:600; display:block; margin:14px 0 6px; }
  input[type=text], textarea { width:100%; padding:10px; border:1px solid #ccc;
         border-radius:6px; font-size:14px; font-family:inherit; }
  textarea { min-height:300px; font-family:Consolas,monospace; }
  .btn { background:var(--accent); color:#fff; border:none; padding:10px 18px;
         border-radius:6px; font-size:14px; cursor:pointer; font-weight:600; }
  .btn.secondary { background:#36384c; }
  .btn:disabled { opacity:.5; cursor:not-allowed; }
  .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:12px; }
  .muted { color:#777; font-size:13px; }
  .hide { display:none; }
  .err { color:#c0392b; font-weight:600; }

  /* ----- Previa fiel do .docx ----- */
  .preview-title { font-weight:600; margin:0 0 8px; font-size:13px; color:#555; }
  .doc { background:#fff; border:1px solid #d9d9d9; border-radius:6px;
         box-shadow:0 1px 6px rgba(0,0,0,.08); padding:40px 44px;
         max-height:78vh; overflow:auto; }
  .doc-h1 { font-family:"Montserrat",sans-serif; font-weight:700; font-size:18px;
            color:#26292c; margin:0 0 16px; }
  .doc-unit { font-family:"Montserrat",sans-serif; font-weight:700; font-size:12px;
              color:#26292c; margin:18px 0 6px; }
  .doc-code { background:var(--bg); border-radius:2px; padding:8px 10px;
              font-family:Consolas,"Courier New",monospace; font-size:12px;
              line-height:1.7; white-space:pre-wrap; word-break:break-all; }
  .doc-empty { color:#999; font-style:italic; text-align:center; padding:40px 0; }
</style>
</head>
<body>
<header><h1>Gerador de Ad Units <span>| .docx</span></h1></header>
<main>
  <div class="layout">
    <section class="pane-left">
      <label for="title">Titulo do documento</label>
      <input type="text" id="title" value="Ad Units Manuais | Web">

      <label for="src">Cole o texto com os blocos de codigo</label>
      <textarea id="src" placeholder="Cole aqui o conteudo (ex: o texto.txt)..."></textarea>

      <div class="row">
        <button class="btn secondary" id="detect">Detectar ad units</button>
        <button class="btn" id="gen" disabled>Gerar DOCX</button>
        <span class="muted" id="status"></span>
      </div>
    </section>

    <section class="pane-right">
      <p class="preview-title">Previa do documento</p>
      <div class="doc" id="doc">
        <div class="doc-empty">A previa aparece aqui depois de "Detectar ad units".</div>
      </div>
    </section>
  </div>
</main>

<script>
let blocks = [];

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;')
          .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Monta o HTML colorido de um bloco a partir dos tokens [texto, corHex].
function codeHtml(tokens) {
  return (tokens || []).map(([txt, col]) =>
    `<span style="color:#${col}">${esc(txt)}</span>`).join('');
}

function renderPreview() {
  const doc = document.getElementById('doc');
  const title = document.getElementById('title').value || 'Ad Units Manuais | Web';
  if (!blocks.length) {
    doc.innerHTML = '<div class="doc-empty">Nenhum bloco detectado ainda.</div>';
    return;
  }
  let html = `<div class="doc-h1">${esc(title)}</div>`;
  blocks.forEach(b => {
    html += `<div class="doc-unit">${esc(b.adunit)}</div>` +
            `<div class="doc-code">${codeHtml(b.tokens)}</div>`;
  });
  doc.innerHTML = html;
}

document.getElementById('detect').addEventListener('click', async () => {
  const text = document.getElementById('src').value;
  const status = document.getElementById('status');
  const gen = document.getElementById('gen');
  status.textContent = 'Detectando...';
  const res = await fetch('/parse', {method:'POST', headers:{'Content-Type':'application/json'},
                                     body: JSON.stringify({text})});
  blocks = await res.json();
  if (!blocks.length) {
    status.innerHTML = '<span class="err">Nenhum bloco &lt;div data-adunit&gt; encontrado.</span>';
    gen.disabled = true;
    renderPreview();
    return;
  }
  status.textContent = blocks.length + ' ad unit(s) detectada(s).';
  gen.disabled = false;
  renderPreview();
});

// Mantem a previa em sincronia com o titulo digitado.
document.getElementById('title').addEventListener('input', () => {
  if (blocks.length) renderPreview();
});

document.getElementById('gen').addEventListener('click', async () => {
  const title = document.getElementById('title').value;
  const res = await fetch('/generate', {method:'POST', headers:{'Content-Type':'application/json'},
                                        body: JSON.stringify({title, blocks})});
  if (!res.ok) { alert('Erro ao gerar o documento.'); return; }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'adunits-gerado.docx';
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silencioso

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX_HTML.encode("utf-8"))
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        try:
            if self.path == "/parse":
                data = self._read_json()
                blocks = parse_text(data.get("text", ""))
                self._send(200, json.dumps(blocks).encode("utf-8"),
                           "application/json; charset=utf-8")
            elif self.path == "/generate":
                data = self._read_json()
                title = data.get("title", DEFAULT_TITLE)
                blocks = data.get("blocks", [])
                docx = build_docx(title, blocks)
                self._send(
                    200, docx,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    extra={"Content-Disposition": 'attachment; filename="adunits-gerado.docx"'},
                )
            else:
                self._send(404, b"Not found", "text/plain; charset=utf-8")
        except Exception as e:  # noqa
            msg = ("Erro: " + str(e)).encode("utf-8")
            self._send(500, msg, "text/plain; charset=utf-8")


def main():
    # Configuravel por ambiente (HOST/PORT). Default 127.0.0.1:8420 para
    # rodar atras de um reverse proxy (nginx) na VPS.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8420"))
    open_browser = os.environ.get("OPEN_BROWSER", "1") != "0"
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"Servidor rodando em {url}")
    print("Pressione Ctrl+C para encerrar.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando...")
        server.shutdown()


if __name__ == "__main__":
    main()
