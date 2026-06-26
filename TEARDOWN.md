# Remover o projeto / reverter o deploy

Guia para **desligar o site e apagar todos os vestígios** do projeto na VPS e na
máquina local. Remove apenas o que é deste projeto — não toca em nginx, UFW,
Oracle Cloud ou outros serviços que já existiam na VPS.

> ⚠️ A VPS roda outros serviços (Minecraft, portas 3000/5000/8080, etc.).
> **Não** remova o nginx, o UFW, nem mexa nas regras da Oracle Cloud — isso
> quebraria as outras aplicações. Os passos abaixo removem só o deste projeto.

---

## Na VPS

Autentique o sudo primeiro (evita que comandos colados sejam "engolidos" pelo
prompt de senha):

```bash
sudo -v
```

### 1. Parar e remover o serviço systemd
(É o processo que sobe com a VPS e consome memória — depois disto, consumo zero.)

```bash
sudo systemctl disable --now adunit-doc-generator
sudo rm -f /etc/systemd/system/adunit-doc-generator.service
sudo systemctl daemon-reload
sudo systemctl reset-failed adunit-doc-generator
```

### 2. Remover o certificado Let's Encrypt
(Para de tentar renovar a cada 90 dias.)

```bash
sudo certbot delete --cert-name gerar-adunit.duckdns.org
```

### 3. Remover a config do nginx deste site
(Não afeta os outros sites/serviços do nginx.)

```bash
sudo rm -f /etc/nginx/sites-enabled/gerar-adunit
sudo rm -f /etc/nginx/sites-available/gerar-adunit
sudo nginx -t && sudo systemctl reload nginx
```

### 4. Remover o cron do DuckDNS
(Só se você criou o cron opcional de atualização de IP.)

```bash
crontab -l | grep -v 'duckdns' | crontab -
rm -rf ~/duckdns
```

### 5. Apagar a pasta do projeto
(Código, histórico git, tudo.)

```bash
rm -rf ~/adunit-doc-generator
```

### 6. Confirmar que não sobrou nada

```bash
systemctl status adunit-doc-generator   # deve dizer "could not be found"
ls ~/adunit-doc-generator                # deve dizer "No such file or directory"
```

---

## Passos manuais (fora do terminal)

- **DuckDNS** — entre em <https://www.duckdns.org> e **delete o subdomínio
  `gerar-adunit`** (botão de remover ao lado dele).
- **Oracle Cloud** — **deixe como está.** As regras de ingress 80/443 já existiam
  antes e outros serviços podem usá-las.
- **UFW** — **não mexa.** O `Nginx Full` (80/443) provavelmente é usado por
  outros sites. Deixar aberto não consome recursos.

---

## Na máquina local (Windows)

As alterações feitas no `app.py` e `README.md` podem ser revertidas com git:

```bash
git restore app.py README.md
```

Ou apague a pasta local inteira: `C:\Users\danie\magics\adunit-generator`.

---

## O que de fato consumia recursos da VPS

O único processo rodando 24h (e que subia no boot) era o **serviço systemd**
(passo 1). Removendo-o, o consumo deste projeto vai a zero. O nginx e o UFW já
rodavam antes para outros fins — não são "peso" deste projeto.
</content>
