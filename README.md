# 🧙‍♂️ Abadats.AI — Assistente Text-to-SQL

# A ssistente de 
# BA nco de
# DA dos
# T ext-to
# S ql ----> ABADATS



## Visão Geral

**Abadats.AI** é uma aplicação web (Streamlit) que converte perguntas em linguagem natural (português) em consultas SQL executáveis contra um banco de dados relacional (PostgreSQL ou MySQL), usando um LLM local via Ollama.

**Problema que resolve:** em geral, só quem sabe SQL consegue consultar um banco de dados diretamente. O Abadats.AI permite que qualquer pessoa faça perguntas em português e receba respostas baseadas nos dados reais do banco, sem escrever uma linha de SQL.

---

## Arquitetura

O projeto é dividido em 3 módulos, seguindo separação de responsabilidades:

```
app.py          → Interface (Streamlit) — chat, sidebar de conexão, exibição de resultados
database.py     → Camada de dados — conexão, extração de schema, execução de queries
llm_engine.py   → Motor de IA — geração de SQL e análise de insights via Ollama
```

```
Usuário pergunta (PT)
        │
        ▼
[llm_engine.py] Monta prompt (regras + schema + pergunta) ──► Ollama (gemma4:e4b)
        │                                                          │
        ▼                                                          ▼
Limpeza/extração do SQL (_extrair_sql_limpo)  ◄────────── resposta bruta do LLM
        │
        ▼
[database.py] Executa via SQLAlchemy ──► retorna DataFrame (pandas)
        │
        ├── sucesso ──► exibe tabela + SQL, habilita botão de Insights
        └── erro ────► captura exception, exibe mensagem amigável, registra no histórico
```

O estado da conversa (`st.session_state`) guarda histórico de mensagens, schema atual e os dados pendentes para insight, mantendo a reatividade do Streamlit entre os `st.rerun()`.

---

## Extração do Schema

Antes de qualquer pergunta, `database.py` percorre o banco via `inspect()` do SQLAlchemy e monta um texto descritivo do schema, que é injetado no prompt:

```python
def extrair_esquema(engine) -> str:
    inspector = inspect(engine)
    for tabela in inspector.get_table_names():
        colunas = inspector.get_columns(tabela)
        pk_info = inspector.get_pk_constraint(tabela)
        colunas_pk = pk_info.get('constrained_columns', [])
        # marca cada coluna que está em colunas_pk como [CHAVE PRIMÁRIA]
        ...
        fks = inspector.get_foreign_keys(tabela)
        # para cada FK: constrained_columns[0] -> referred_table.referred_columns[0]
```

Saída gerada (exemplo):

```
Tabela: pedidos
Colunas:
  - id (INTEGER) [CHAVE PRIMÁRIA]
  - cliente_id (INTEGER)
  - valor_total (NUMERIC)
Relacionamentos (Chaves Estrangeiras):
  - Coluna 'cliente_id' aponta para 'clientes.id'
```

Marcar PKs e FKs explicitamente é o que permite ao LLM montar JOINs corretos — sem essa informação, ele tende a "adivinhar" relacionamentos e errar.

> **Limitação técnica:** a leitura de FK usa `fk['constrained_columns'][0]` e `fk['referred_columns'][0]`, ou seja, só captura a primeira coluna de chaves estrangeiras compostas (multi-coluna). Para os schemas testados isso não foi um problema, mas é uma simplificação consciente.

---

## Engenharia de Prompts

O prompt de sistema em `gerar_sql()` é dividido em dois blocos de regras: um conjunto geral de boas práticas e um conjunto de regras "absolutas" adicionado depois para fechar brechas observadas nos testes.

| Regra | Motivo |
|---|---|
| Responder só com SQL puro, sem markdown, sem texto antes/depois | O parser de limpeza precisa de um SQL "limpo" para ter o mínimo de trabalho |
| Usar apenas tabelas/colunas do schema informado | Previne alucinação de colunas inexistentes |
| JOINs baseados estritamente nas FKs do contexto | Evita relacionamentos inventados entre tabelas |
| Apenas SELECT — proibido DELETE/UPDATE/INSERT | Restringe o escopo a consultas de leitura (reforçado só via prompt — ver Limitações) |
| Proibido alias de uma letra (`c`, `ad`) — exigir nome completo da tabela | Reduz ambiguidade em JOINs com várias tabelas |
| Proibido "Opção 1 / Opção 2" — exatamente uma query | LLMs tendem a oferecer alternativas quando inseguros; isso quebraria o parser |
| **Usar a sintaxe do dialeto do banco alvo** (`GROUP_CONCAT` no MySQL vs. `STRING_AGG` no PostgreSQL) | O mesmo schema pode estar rodando em bancos diferentes — a regra força o modelo a gerar SQL compatível com o dialeto real, não um SQL "genérico" que falharia em um dos dois |

Chamada ao modelo (`ollama.generate`, stateless — sem histórico entre chamadas):

```python
resposta = ollama.generate(
    model='gemma4:e4b',
    system=prompt_sistema,
    prompt=prompt_usuario,
    options={"temperature": 0.1}  # baixa: queremos determinismo, não criatividade
)
```

A chamada é envolvida em `try/except`: se o Ollama estiver fora do ar ou o modelo não existir, a função retorna uma string de erro em vez de quebrar a aplicação.

### Limpeza do SQL gerado

Mesmo com as regras, o LLM ocasionalmente retorna texto extra. `_extrair_sql_limpo()` é a camada defensiva:

```python
def _extrair_sql_limpo(texto_bruto: str) -> str:
    # 1. Tenta extrair de bloco ```sql ... ```; se não achar, tenta bloco genérico ``` ... ```
    # 2. Corta tudo antes do primeiro SELECT ou WITH
    # 3. Corta tudo após o primeiro ponto e vírgula
    # 4. Remove comentários SQL (/* */ e --)
    return sql.strip()
```

| Entrada do LLM | Depois da limpeza |
|---|---|
| `Claro! Aqui está:\n\`\`\`sql\nSELECT * FROM users;\n\`\`\`\nEspero ter ajudado` | `SELECT * FROM users;` |
| `-- comentário\nSELECT * FROM users; -- nota extra` | `SELECT * FROM users;` |

### Geração de Insights

Após a execução da query, o botão "Gerar Insights" reenvia pergunta + dados retornados ao LLM, com `temperature=0.5` (mais liberdade que a geração de SQL, já que aqui o objetivo é interpretação, não exatidão sintática). Os dados são limitados a `df.head(100)` e convertidos para markdown antes de irem ao prompt — controla o tamanho do contexto enviado ao modelo em consultas que retornam muitas linhas.

---

## Segurança e Limitações Conhecidas

- **Restrição a SELECT é aplicada via prompt, não via código.** `executar_query()` em `database.py` executa `pd.read_sql_query(sql_query, engine)` diretamente, sem nenhuma validação prévia da query. Se o LLM desobedecer a regra do prompt, nada no código impede um DELETE/UPDATE de rodar. Em produção, isso seria reforçado com uma checagem explícita (regex validando que a query começa com `SELECT`/`WITH`) e, idealmente, uma conexão ao banco com um usuário restrito a permissões de leitura (`GRANT SELECT`).
- **FKs compostas não são totalmente capturadas** no mapeamento de schema (ver seção acima).
- **Schema grande pode estourar o contexto do prompt.** Para bancos com muitas tabelas, o texto de schema enviado ao LLM cresce proporcionalmente, podendo ultrapassar a janela de contexto do modelo.
- **O LLM pode alucinar mesmo seguindo as regras** — especialmente em perguntas ambíguas ou schemas com nomes de colunas pouco descritivos.

---

## Como Executar

```bash
# 1. Criar e ativar ambiente virtual
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Instalar Ollama (https://ollama.com) e baixar o modelo
ollama pull gemma4:e4b

# 4. Ter um banco PostgreSQL ou MySQL acessível com as credenciais em mãos

# 5. Rodar a aplicação
streamlit run app.py
```

A aplicação abre em `http://localhost:8501`. As credenciais do banco (host, porta, usuário, senha, nome do banco) são preenchidas na barra lateral.

---

## Solução de Problemas

| Erro | Causa provável | Solução |
|---|---|---|
| `Connection error: ... ollama server` | Ollama não está rodando | `ollama serve` (Linux) ou abrir o app Ollama; testar com `curl http://localhost:11434` |
| `model 'gemma4:e4b' not found` | Modelo não baixado | `ollama pull gemma4:e4b` |
| SQL gerado é inválido/vazio | Pergunta ambígua ou schema incompleto | Conferir o schema exibido no expander; reformular a pergunta com termos mais próximos dos nomes reais de tabelas/colunas |

---

## Hardware utilizado para o desenvolvimento

CPU: I5 12400F
GPU: RTX 3070ti 8GB 
OS: Windows 11
RAM: 16GB ddr4 
MEMORIA: SSD 1tb sata 3

---

## Design

A interface do **Abadats.AI** foi projetada quebrando o padrão sóbrio e puramente técnico de ferramentas tradicionais de banco de dados. Como o processo de traduzir linguagem natural para código estruturado e executar queries complexas em segundos pode parecer "mágica" para o usuário final, adotou-se o design lúdico focado na **metáfora de um mago e seus rituais místicos**.

---

## Conclusão

O Abadats.AI demonstra a aplicação de engenharia de prompts e introspecção de schema via SQLAlchemy para reduzir a barreira entre linguagem natural e consulta a bancos relacionais, mantendo a operação restrita a leitura de dados.

# Autor

Nicolas Rossi Gariba
github.com/Nicolas-Rossi28