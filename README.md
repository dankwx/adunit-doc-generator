# Gerador de Ad Units (.docx)

Interface web simples para gerar um documento `.docx` (igual ao `adunits.docx`)
preenchendo os blocos de código a partir de um texto colado.

O servidor usa **apenas a biblioteca padrão do Python 3** — não há dependências
para instalar.

---

## Uso local (desenvolvimento)

```bash
python3 app.py
```

O navegador abre em `http://127.0.0.1:8420/`. Então:

1. Cole o texto com os blocos `<div data-adunit=...></div>` (ex.: o `texto.txt`).
2. Clique em **Detectar ad units** — cada `div` vira uma linha com o nome da
   ad unit e o código.
3. Clique em **Gerar DOCX**.

O arquivo `adunits-gerado.docx` é baixado, no mesmo formato do modelo.

### Variáveis de ambiente

| Variável        | Default       | Descrição                                            |
|-----------------|---------------|------------------------------------------------------|
| `HOST`          | `127.0.0.1`   | Endereço de bind. Mantenha `127.0.0.1` atrás do nginx. |
| `PORT`          | `8420`        | Porta do servidor. **Mudada de 8000 → 8420** para não colidir com outro serviço na VPS. |
| `OPEN_BROWSER`  | `1`           | `0` desativa a abertura automática do navegador (use na VPS). |

---

## Deploy na VPS (Ubuntu + DuckDNS + nginx + Let's Encrypt)

Guia do zero, para deixar o site acessível de qualquer lugar em
`https://gerar-adunit.duckdns.org`.

> Substitua `SEU_USUARIO` pelo seu usuário Linux e ajuste o caminho do projeto
> se você clonou em outro lugar. Este guia assume o clone em
> `/home/SEU_USUARIO/adunit-doc-generator`.

### 1. Pré-requisitos

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 nginx curl
```

Confirme que o projeto está clonado e roda:

```bash
cd ~/adunit-doc-generator
OPEN_BROWSER=0 python3 app.py
# Deve imprimir: "Servidor rodando em http://127.0.0.1:8420/"
# Ctrl+C para parar.
```

### 2. DuckDNS — apontar o domínio para a VPS

1. Acesse https://www.duckdns.org e faça login.
2. Crie o subdomínio **`gerar-adunit`** (domínio final: `gerar-adunit.duckdns.org`).
3. No campo **current ip**, coloque o IP público da sua VPS e clique em **update ip**.
   - Descubra o IP da VPS com: `curl -s ifconfig.me`

Teste a resolução (pode levar alguns minutos para propagar):

```bash
ping -c 2 gerar-adunit.duckdns.org
```

**(Opcional) Manter o IP atualizado** caso seja dinâmico — pegue o *token* no
painel do DuckDNS e crie um cron:

```bash
mkdir -p ~/duckdns
cat > ~/duckdns/duck.sh <<'EOF'
#!/bin/bash
echo url="https://www.duckdns.org/update?domains=gerar-adunit&token=SEU_TOKEN_DUCKDNS&ip=" \
  | curl -k -o ~/duckdns/duck.log -K -
EOF
chmod 700 ~/duckdns/duck.sh
( crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1" ) | crontab -
```

### 3. Rodar o app como serviço (systemd)

Mantém o app sempre no ar (start no boot, restart se cair), ouvindo só em
`127.0.0.1:8420` — quem expõe para a internet é o nginx.

```bash
sudo tee /etc/systemd/system/adunit-generator.service > /dev/null <<EOF
[Unit]
Description=Gerador de Ad Units (.docx)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/adunit-doc-generator
Environment=HOST=127.0.0.1
Environment=PORT=8420
Environment=OPEN_BROWSER=0
ExecStart=/usr/bin/python3 /home/$USER/adunit-doc-generator/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now adunit-doc-generator
sudo systemctl status adunit-doc-generator --no-pager
```

Logs: `journalctl -u adunit-doc-generator -f`

### 4. nginx como reverse proxy

```bash
sudo tee /etc/nginx/sites-available/gerar-adunit > /dev/null <<'EOF'
server {
    listen 80;
    server_name gerar-adunit.duckdns.org;

    location / {
        proxy_pass http://127.0.0.1:8420;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/gerar-adunit /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # remove o site padrão (opcional)
sudo nginx -t
sudo systemctl reload nginx
```

Neste ponto o site já responde em `http://gerar-adunit.duckdns.org`.

### 5. Firewall

Se usar UFW, libere HTTP/HTTPS e SSH:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

> Na maioria das VPS há também um firewall no painel do provedor: garanta que
> as portas **80** e **443** estejam abertas. A porta **8420** **não** precisa
> ser exposta (fica só no localhost).

### 6. HTTPS com Let's Encrypt (Certbot)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d gerar-adunit.duckdns.org \
  --non-interactive --agree-tos -m danielkondlatsch.p@gmail.com --redirect
```

O Certbot edita o nginx automaticamente, adiciona o certificado e redireciona
HTTP → HTTPS. A renovação automática já vem configurada; teste com:

```bash
sudo certbot renew --dry-run
```

### Pronto ✅

Acesse de qualquer lugar do mundo:

**https://gerar-adunit.duckdns.org**

---

## Atualizar o app depois de mudanças

```bash
cd ~/adunit-doc-generator
git pull
sudo systemctl restart adunit-doc-generator
```

---

## Solução de problemas

- **502 Bad Gateway no nginx** → o app não está rodando ou está em outra porta.
  Verifique: `sudo systemctl status adunit-doc-generator` e
  `curl -I http://127.0.0.1:8420`.
- **Certbot falha** → o DNS do DuckDNS ainda não propagou, ou as portas 80/443
  estão fechadas no firewall do provedor. Cheque com
  `dig +short gerar-adunit.duckdns.org`.
- **Porta 8420 também em uso** → escolha outra e ajuste nos dois lugares:
  `Environment=PORT=` no serviço systemd **e** `proxy_pass` no nginx; depois
  `sudo systemctl restart adunit-doc-generator && sudo systemctl reload nginx`.

---

## Arquivos

- `app.py` — servidor web + gerador do `.docx` (somente biblioteca padrão do Python).
- `adunits.docx` — documento de referência, usado como modelo (estilos, fontes,
  header e footer são preservados; apenas o conteúdo é regerado).
- `templates_xml/prefix.xml` / `suffix.xml` — cabeçalho/intro e rodapé do documento.
- `texto.txt` — exemplo de entrada.
</content>
</invoke>
