# Sales Grid (Flask + GitHub JSON Storage)

App web estilo “Excel” para registrar vendas (vendedores x itens) por equipe e período, **SEM banco de dados**.
A persistência é feita em **um único JSON versionado no GitHub**, atualizado automaticamente via GitHub Contents API.

## ✅ Requisitos atendidos
- Flask com Blueprints
- Templates Jinja2 + Bootstrap 5 + JS Fetch
- Grid com +/−, input numérico, sem negativos, autosave com status
- Totais por linha, coluna e total geral
- Busca vendedor/item + modo foco (celular)
- Login email/senha
- Papéis: **ADMIN** (tudo) e **MANAGER** (somente sua equipe)
- Auditoria (últimas alterações do grid)
- Export CSV por equipe + período
- Persistência obrigatória em **/data/sales-grid.json** no GitHub

---

## 1) Estrutura do JSON (resumo)
O arquivo `data/sales-grid.json` contém:
- `company`: {name, logo_url, watermark_url}
- `teams`: lista (5 no seed)
- `sellers`: lista (com `team_id`)
- `items`: lista (com `photo_url` e `video_url` opcional)
- `periods`: lista (1 período atual no seed)
- `users`: managers (email, role, team_id, password_hash)
- `sales`: vendas por período/equipe/vendedor/item
- `audit`: log de alterações (cell updates)

> **Seed automático:** se o arquivo não existir no repo, o app cria um seed inicial e faz commit automaticamente.

---

## 2) Rodar local
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export SECRET_KEY="dev"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="admin123"

# Para usar GitHub storage:
export GITHUB_TOKEN="..."
export GITHUB_REPO="usuario/sales-grid"
export GITHUB_BRANCH="main"
export GITHUB_PATH="data/sales-grid.json"

flask --app wsgi run --debug
```

Acesse:
- `http://localhost:5000/login`

### Credenciais seed
- **Admin:** usa `ADMIN_EMAIL` / `ADMIN_PASSWORD`
- **Managers (seed):**  
  `manager.norte@example.com`, `manager.sul@example.com`, ...  
  Senha padrão: `manager123`

---

## 3) Deploy na Railway (GitHub)
1. Suba este projeto para um repositório no GitHub (ex: `usuario/sales-grid`).
2. Na Railway: **New Project → Deploy from GitHub Repo**.
3. Em **Variables**, configure:

### Variáveis obrigatórias (Railway)
- `SECRET_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `GITHUB_TOKEN`
- `GITHUB_REPO` (ex: `usuario/sales-grid`)
- `GITHUB_BRANCH` (ex: `main`)
- `GITHUB_PATH` (ex: `data/sales-grid.json`)

### Token do GitHub
Crie um token com permissão para **ler e escrever contents no repo**.

- **Fine-grained token (recomendado):**
  - Repository access: selecione o repo
  - Permissions: **Contents = Read and write**

- **Classic token:**
  - Scope: `repo` (ou ao menos permissão equivalente para editar arquivos)

> Depois do primeiro deploy, o app vai:
> 1) tentar ler o arquivo `data/sales-grid.json`
> 2) se não existir, criar o seed e commitar no GitHub automaticamente.

---

## 4) Rotas
### Pages
- `/login`, `/logout`
- `/home`
- `/team/<id>`
- Admin:
  - `/admin/settings`
  - `/admin/teams`
  - `/admin/sellers`
  - `/admin/items`
  - `/admin/audit`

### API
- `GET /api/grid?team_id=...&period_id=...`
- `PATCH /api/cell` (autosave)
- `GET /api/export.csv?team_id=...&period_id=...`
- Admin (JSON):
  - `GET /api/admin/teams`
  - `GET /api/admin/sellers`
  - `GET /api/admin/items`

---

## 5) Observações importantes
- **Sem upload**: imagens e vídeos são somente URLs (com preview no admin).
- Para evitar race conditions, o save usa `threading.Lock`.
- O app tenta manter um cache em memória, e faz commit a cada alteração.

---

## 6) Produção
A Railway usa o `Procfile`:
```
web: gunicorn wsgi:app
```
