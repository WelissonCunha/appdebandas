# Exalte

Aplicativo web (instalável no celular como PWA) para organizar **ministérios de louvor e bandas**: escalas, repertório, eventos, avisos, mensagens e notificações em um só lugar, no lugar do grupo de WhatsApp.

Feito em **Python + Django**, pensado primeiro para o celular.

---

## Funcionalidades

### Para todos os membros
- **Início:** seus ministérios, avisos, próximas escalas, aniversariantes do mês, próximos eventos e registro de datas em que não pode participar.
- **Minhas escalas:** confirmar presença, recusar e **pedir troca**.
- **Trocas:** ver pedidos de colegas e aceitar a escala deles (o líder é avisado).
- **Repertório:** músicas com tom, BPM, link e cifra.
- **Mensagens:** chat por banda, com contador de não lidas e **@menções** (quem é mencionado recebe notificação no celular).
- **Página da banda:** foto, equipes (**Vocal, Back, Instrumental**) e lista de membros.
- **Evento:** escala, setlist e exportação da escala em **PNG ou PDF**.
- **Perfil:** foto, nome, aniversário, senha e preferências de notificação.

### Para líderes (menu ☰ Gerenciar)
- **Eventos:** criar, editar e excluir (inclusive vários de uma vez).
- **Importar calendário:** por **texto colado** ou **PDF**, com filtro por palavras, pré-visualização editável, aviso de duplicados e **desfazer**.
- **Eventos recorrentes:** gera "toda quinta às 19h30", "2º sábado do mês" etc. para um período inteiro.
- **Escala e setlist:** montar por evento, reordenar músicas.
- **Modelos de escala com rodízio:** define funções e pessoas uma vez e aplica a vários eventos; respeita indisponibilidades e distribui de forma justa. Aplicações podem ser desfeitas.
- **Músicas, bandas, membros e avisos:** cadastro completo (avisos podem ser fixados), com exclusão em lote.
- **Membros:** criar login, definir papel e equipes, **redefinir senha**.
- **Painel** com resumo e atalhos.

### Para o desenvolvedor
- `/admin/` do Django (visível só para usuários `is_staff`).

---

## Tecnologias
- Python 3.10+ e Django 5
- SQLite (desenvolvimento)
- `pywebpush` (notificações push) e `pdfplumber` (leitura de PDF)
- HTML/CSS/JS puros, sem framework de front-end; ícones em SVG
- PWA: `manifest` + service worker

## Estrutura do projeto
```
manage.py
requirements.txt
testar_email.py          # diagnóstico do envio de e-mail
config/                  # configurações gerais (settings.py, urls.py)
core/                    # o sistema
  models.py              # dados
  views.py               # telas e regras de negócio
  forms.py  urls.py  admin.py  decorators.py
  notificacoes.py        # e-mail + push (envio em segundo plano)
  mencoes.py  leitura.py # @menções e mensagens não lidas
  importacao.py          # leitor de texto de calendário
  importacao_pdf.py      # leitor de PDF de calendário
  recorrencia.py         # datas das regras recorrentes
  rodizio.py             # distribuição das escalas por rodízio
  templatetags/menu.py   # menu, avatar, contador, destaque de @menções
  templates/             # telas (HTML) e sw.js (service worker)
  static/core/icons/     # ícones do app
  management/commands/seed.py   # dados de exemplo
```

## Dados principais
`Banda`, `Membro` (papel líder/membro + equipes), `Evento`, `Escala`, `ItemSetlist`, `Musica`, `Aviso`, `Indisponibilidade`, `TrocaEscala`, `Mensagem`, `ModeloEscala`/`ModeloFuncao`, `Perfil` (aniversário, preferências), `FotoPerfil`/`BandaFoto` (fotos guardadas no banco), `PushSub` (aparelhos inscritos) e os lotes de importação/aplicação (para desfazer).

---

## Como rodar localmente

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python manage.py makemigrations core
python manage.py migrate
python manage.py seed           # opcional: dados de exemplo
python manage.py runserver
```
Acesse `http://127.0.0.1:8000/login/`.

> No PowerShell, se a ativação for bloqueada: `Set-ExecutionPolicy -Scope Process RemoteSigned`.

**Contas do `seed` (apenas para teste):** `admin / admin123` (líder e superusuário) e `ana`, `bruno`, `carla` com senha `senha123`. **Apague-as antes de colocar online.**

Criar um superusuário próprio: `python manage.py createsuperuser`.

## Configuração (variáveis de ambiente)

Nada de segredo vai no código. Todas são opcionais em desenvolvimento.

| Variável | Para que serve |
|---|---|
| `EMAIL_HOST` | Servidor SMTP (ex.: `smtp.gmail.com`). **Sem ela, os e-mails aparecem no terminal.** |
| `EMAIL_PORT` | Porta (padrão 587; com `EMAIL_SSL=1`, 465) |
| `EMAIL_USER` / `EMAIL_PASSWORD` | Conta de envio e **senha de app** (Gmail) |
| `EMAIL_FROM` | Remetente, ex.: `Exalte <conta@gmail.com>` |
| `EMAIL_TLS` / `EMAIL_SSL` | `1` ou `0` (padrão: TLS ligado, SSL desligado) |
| `SITE_URL` | Endereço do site, usado nos links das mensagens |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Chaves das notificações push. Sem elas, são geradas em `vapid.json` |
| `VAPID_EMAIL` | E-mail de contato exigido pelos serviços de push |

Exemplo (PowerShell):
```powershell
$env:EMAIL_HOST="smtp.gmail.com"
$env:EMAIL_USER="conta@gmail.com"
$env:EMAIL_PASSWORD="senhadeapp"
python manage.py runserver
```
Para diagnosticar o e-mail: `python testar_email.py` (ou `python testar_email.py voce@email.com` para enviar um teste).

## Notificações
- **E-mail:** pessoa escalada (inclusive por modelo), aviso novo, troca aceita.
- **Push no celular/computador:** os mesmos eventos, mais **@menções** no chat. Cada pessoa ativa em 🔔 (Perfil) e pode desligar cada canal.
- Exige **HTTPS** (exceto em `localhost`). No iPhone, só depois de instalar o app na tela inicial.

## Permissões e segurança
- Líder só gerencia as bandas que lidera; todas as ações são conferidas no servidor.
- Usuários criados pelo líder são **obrigados a trocar a senha** no primeiro acesso.
- Líderes não redefinem a senha de outros líderes nem de administradores.
- Uma banda nunca fica sem líder.

---

## Checklist para colocar online
- [ ] Trocar a `SECRET_KEY` (hoje fixa em `config/settings.py`) por variável de ambiente
- [ ] `DEBUG = False`, `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` com o domínio `https`
- [ ] Banco persistente (Postgres ou disco persistente) e rotina de backup
- [ ] Servidor de produção (gunicorn) e arquivos estáticos (`collectstatic` + WhiteNoise)
- [ ] Definir `SITE_URL`, `EMAIL_*` e as chaves `VAPID_*` no painel da hospedagem
- [ ] Apagar as contas do `seed` e criar o superusuário real
- [ ] Versionar `core/migrations/` e manter fora do Git: `.venv/`, `db.sqlite3`, `vapid.json`

> Estes itens ainda **não** estão configurados no projeto; são o próximo passo.

## Limitações conhecidas
- O leitor de PDF foi ajustado ao desenho da agenda atual (meses em grade com a lista de eventos abaixo). Outros layouts usam o texto corrido; PDFs escaneados (só imagem) não são lidos.
- Eventos têm só horário de início.
- A exportação da escala em PNG/PDF usa bibliotecas carregadas de um CDN (precisa de internet).
- O contador de mensagens e o chat atualizam por consulta periódica (a cada 12–30 s), não em tempo real.

## Ideias futuras
- Modelo de setlist (repertório padrão por tipo de evento)
- Calendário mensal e exportação da escala do mês
- Escolher quem começa o rodízio
- Aviso de menções também por e-mail (opcional)
