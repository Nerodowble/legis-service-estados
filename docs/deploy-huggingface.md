# Deploy gratuito no Hugging Face Spaces

Guia para quem nunca usou Hugging Face. Cada passo descreve **exatamente
o que vai aparecer na tela**. Se travar em qualquer ponto, mande print.

## Por que Hugging Face Spaces?

- ✅ Não pede cartão de crédito (só email)
- ✅ 16 GB de RAM no free tier (sobra muito)
- ✅ Suporta Docker direto (usa nosso Dockerfile sem mexer)
- ✅ SSL + URL pública prontos
- ✅ Logs em tempo real no navegador
- ❌ Dorme após 48h sem acesso (acorda em ~10-15s no primeiro request)

---

## ETAPA 1 — Criar conta no Hugging Face (3 minutos)

1. Abra: **https://huggingface.co/join**
2. Preencha:
   - **Email** (use seu Gmail/Outlook)
   - **Password** (mínimo 8 caracteres)
   - **Username** (vai virar URL pública, ex: `willian-lima`)
   - **Full name**
3. Marque "I have read and agree with the Terms"
4. Clique no botão grande **"Sign up"**
5. Vai para `https://huggingface.co/email-verification` — você vê: "Please check your email"
6. Abra o email do HF e clique no link de confirmação
7. Volta pro site automaticamente, agora logado

> Tela final: canto superior direito tem a sua foto/inicial. Se aparecer, deu certo.

---

## ETAPA 2 — Criar o Space (2 minutos)

1. Clique no seu avatar (canto superior direito) → **"+ New Space"**
   Ou acesse direto: **https://huggingface.co/new-space**

2. Preencha o formulário:

   | Campo | O que digitar |
   |---|---|
   | **Space name** | `legis-service-estados` (sem espaços, sem maiúsculas) |
   | **License** | `mit` |
   | **Select the Space SDK** | Clique no card **"Docker"** (não Streamlit/Gradio!) |
   | **Choose a Docker template** | **"Blank"** |
   | **Space hardware** | Deixe `CPU basic - 2 vCPU 16GB FREE` |
   | **Public/Private** | `Public` (não importa, é só pra teste) |

3. Clique em **"Create Space"** (botão azul no final)

4. Vai pra uma página com 3 abas: **App**, **Files**, **Community**
   - Aba "App" mostra "Building..." (ainda não tem código, então fica vazio)
   - Aba "Files" tem só um README.md auto-gerado
   - Mostra também: "Clone this repository"

> URL do seu Space vai ser: `https://huggingface.co/spaces/<SEU_USERNAME>/legis-service-estados`

---

## ETAPA 3 — Conectar o repositório do GitHub (manual, sem instalar nada)

Vamos copiar os arquivos do GitHub pro HF via Git puro (sem instalar
nada além do Git que você já usa).

### 3.1 — Pegar a URL Git do Space

Na página do Space, clique no botão **"Clone this repository"** (ou nos
3 pontinhos `⋮` no topo direito → "Clone repository").

Vai abrir uma caixa com 2 URLs:

```
git clone https://huggingface.co/spaces/<SEU_USERNAME>/legis-service-estados
```

Copie essa URL (com o seu username no lugar).

### 3.2 — Gerar Token de acesso (HF não aceita senha no git push)

1. Acesse: **https://huggingface.co/settings/tokens**
2. Clique em **"+ Create new token"**
3. Preencha:
   - **Name**: `deploy-spaces` (qualquer coisa)
   - **Type**: **Write** (importante!)
4. Clique em **"Create token"**
5. Vai aparecer um token tipo `hf_AbcDefGhi123...` — **COPIE AGORA**,
   só aparece uma vez. Guarda num bloco de notas temporariamente.

### 3.3 — Fazer o deploy pelo PowerShell (no seu PC)

Abre o PowerShell na pasta do projeto:

```powershell
cd "c:\Users\willi\OneDrive\Documentos\Script_Validação_Api_Projeto_Lei\legis-service-estados"
```

Adicione o HF como segundo remote (mantendo o GitHub):

```powershell
git remote add huggingface https://huggingface.co/spaces/<SEU_USERNAME>/legis-service-estados
```

Antes do primeiro push, renomeia o `HUGGINGFACE_README.md` temporariamente
no Git pra ele virar o `README.md` do HF Space (o HF lê o YAML do
`README.md` do raiz). Vamos fazer isso via branch separada pra não bagunçar
o GitHub:

```powershell
git checkout -b hf-deploy
git mv HUGGINGFACE_README.md README.md --force
git commit -m "deploy: substitui README pelo de HF Spaces (com YAML metadata)"
```

Agora faz o push pra `huggingface`:

```powershell
git push huggingface hf-deploy:main
```

Quando pedir credenciais:
- **Username**: seu username do HF
- **Password**: cole o **token** `hf_AbcDef...` que você criou na etapa 3.2

> ⚠️ É o **token**, não a senha do login. Se errar, aparece "authentication failed".

### 3.4 — Voltar pra branch main local

Pra não deixar o `main` local bagunçado:

```powershell
git checkout main
git branch -D hf-deploy
```

(o `README.md` correto continua no GitHub, intacto)

---

## ETAPA 4 — Acompanhar o build

1. Volta pro navegador na página do Space
2. Aba **"App"** mostra agora: `Building...` com log do Docker
3. Build leva **5-10 minutos na primeira vez** (instala todas as deps)
4. Quando terminar: status muda pra `Running` (verde)
5. A aba "App" passa a mostrar a interface do FastAPI

### Testar

URL pública do seu Space vai ser:

```
https://<SEU_USERNAME>-legis-service-estados.hf.space
```

Teste no navegador ou via cURL:

```bash
# Swagger interativo
https://<SEU_USERNAME>-legis-service-estados.hf.space/docs

# Health check
https://<SEU_USERNAME>-legis-service-estados.hf.space/health

# Listagem real do ALEPE
https://<SEU_USERNAME>-legis-service-estados.hf.space/propositions/fetch-live?source=al_pe&ano=2024&per_page=3
```

---

## ETAPA 5 — Atualizações futuras

Quando você fizer mudanças no código e quiser atualizar o Space:

```powershell
cd "c:\Users\willi\OneDrive\Documentos\Script_Validação_Api_Projeto_Lei\legis-service-estados"

# 1. Push normal pro GitHub (como sempre)
git push origin main

# 2. Atualizar o Space com branch híbrida
git checkout -b hf-update
git mv HUGGINGFACE_README.md README.md --force
git commit -m "deploy: atualiza HF Space"
git push huggingface hf-update:main --force
git checkout main
git branch -D hf-update
```

Ou um atalho via GitHub Actions (configurável depois se você quiser).

---

## Troubleshooting

### Build falha com "permission denied"
- Confirme o token é **Write**, não Read

### "Build failed: no app_port found"
- Confira que o `README.md` no HF tem o bloco YAML no topo com `app_port: 7860`

### App roda mas só dá 502 / "no healthy upstream"
- Container está iniciando — aguarde mais 30s
- Confirme no log do build que o uvicorn diz "Application startup complete"

### Como ver os logs em tempo real
- Aba **"App"** → clique nos 3 pontinhos `⋮` → "View runtime logs"

### Como derrubar/recomeçar o Space
- Aba **"Settings"** → "Factory reboot" (reinicia container limpo)
- Ou "Delete this Space" (apaga geral)

### Mudou os arquivos no GitHub mas o HF não atualizou
- O HF é um Git separado. Cada deploy precisa do push manual da Etapa 5.

---

## Limites do free tier

| Recurso | Limite |
|---|---|
| RAM | 16 GB |
| vCPU | 2 |
| Disk | 50 GB |
| Storage permanente | ❌ não tem (mas nosso serviço é stateless) |
| Cold start | ~10-15s após 48h ocioso |
| Build time | sem limite específico |
| Outbound HTTP | liberado (vai bater nas ALs sem problema) |
| URL custom | ❌ (só `*.hf.space`) |

> Pra URL própria tipo `legis.legalbot.com.br`, precisa Spaces Pro ($9/mês — fora do escopo aqui).
