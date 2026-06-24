# Gerador de Ad Units (.docx)

Interface web simples para gerar um documento `.docx` (igual ao `adunits.docx`)
preenchendo os blocos de código a partir de um texto colado.

## Como usar

```
python app.py
```

O navegador abre em `http://127.0.0.1:8000/`. Então:

1. Cole o texto com os blocos `<div data-adunit=...></div>` (ex.: o `texto.txt`).
2. Clique em **Detectar ad units** — cada `div` vira uma linha com o nome da
   ad unit e o código.
3. Clique em **Gerar DOCX**.

O arquivo `adunits-gerado.docx` é baixado, no mesmo formato do modelo:
título, texto introdutório e, para cada ad unit, um cabeçalho (nome)
seguido do bloco de código em fundo escuro **com syntax highlight** (mesmas
cores do documento original: tag em azul, atributos em azul-claro, valores em
laranja, pontuação em cinza).

## Arquivos

- `app.py` — servidor web + gerador do `.docx` (somente biblioteca padrão do Python).
- `adunits.docx` — documento de referência, usado como modelo (estilos, fontes,
  header e footer são preservados; apenas o conteúdo é regerado).
- `templates_xml/prefix.xml` / `suffix.xml` — cabeçalho/intro e rodapé do documento.
- `texto.txt` — exemplo de entrada.
