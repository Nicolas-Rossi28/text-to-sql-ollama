import ollama
import re

def _extrair_sql_limpo(texto_bruto: str) -> str:
    """
    Forte camada de defesa. Extrai o SQL mesmo se o LLM "grudar" palavras ou enviar tutoriais.
    """
    sql = texto_bruto
    
    # 1. Tenta extrair de blocos markdown
    match = re.search(r'```sql\s*(.*?)\s*```', sql, re.DOTALL | re.IGNORECASE)
    if match:
        sql = match.group(1)
    else:
        match_generico = re.search(r'```\s*(.*?)\s*```', sql, re.DOTALL)
        if match_generico:
            sql = match_generico.group(1)
            
    # 2. Sniper: Corta tudo antes do primeiro SELECT ou WITH
    padrao_inicio = re.search(r'(?i)(SELECT|WITH)\s', sql)
    if padrao_inicio:
        sql = sql[padrao_inicio.start():]
        
    # 3. Corta e joga fora qualquer texto que o LLM tenha escrito DEPOIS do ponto e vírgula
    if ';' in sql:
        sql = sql.split(';')[0] + ';'
        
    # 4. Limpeza implacável de comentários
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL) # Remove /* bloco */
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)  # Remove -- linha
    
    return sql.strip()

def gerar_sql(pergunta: str, schema_banco: str) -> str:
    """
    Envia o esquema do banco e a pergunta em linguagem natural para o modelo
    e retorna a query SQL gerada e limpa.
    """
    prompt_sistema = """
Você é um especialista estrito em bancos de dados SQL. Sua tarefa é converter perguntas em linguagem natural em consultas SQL válidas.

Regras estritas:
1. Responda APENAS com o código SQL executável.
2. Não adicione explicações, saudações ou textos antes/depois do código.
3. Não use blocos de Markdown (como ```sql ... ```).
4. Use APENAS as tabelas e colunas informadas no contexto abaixo.
5. Para realizar JOINs (junções), baseie-se estritamente nas Chaves Estrangeiras informadas no contexto.
6. Não realize nenhuma modificação como DELETE, UPDATE ou INSERT. Apenas SELECTs são permitidos.
7. NUNCA invente colunas ou assuma que elas existem se não estiverem explicitamente listadas.
8. IMPORTANTE: Evite usar apelidos (aliases) curtos de uma única letra para as tabelas (como 'c' ou 'ad'). Em vez disso, use sempre o nome completo da tabela para referenciar as colunas no SELECT e no WHERE (Exemplo: use 'city.city' em vez de 'c.city'). Isso evita erros de ambiguidade.
9. Raciocine antes de enviar a resposta final para verificar erros, alucinações ou conclusões precipitadas. Certifique-se de que a consulta SQL seja lógica e baseada no esquema fornecido.
10. Não comente nada no codigo, apenas crie o sql necessario para a query, sem opcoes multiplas, sem comentarios ou explicações, apenas o SQL puro e simples.

Regras ABSOLUTAS:
1. O banco de dados alvo usa o dialeto: Use as funções exclusivas dele (ex: GROUP_CONCAT para MySQL, STRING_AGG para Postgres).
2. Responda APENAS com o código SQL executável puro. NADA MAIS. NENHUM TEXTO ANTES OU DEPOIS.
3. NUNCA ofereça "Opções" ou explicações (ex: Opção 1, Opção 2). Escreva exatamente UMA query.
4. É ESTRITAMENTE PROIBIDO incluir comentários dentro ou fora do código SQL.
5. Respeite as chaves primárias e estrangeiras informadas no esquema.
"""
    
    prompt_usuario = f"""
    Contexto do Banco de Dados (Esquema):
    {schema_banco}
    
    Pergunta do Usuário: "{pergunta}"
    
    Consulta SQL:
    """
    
    try:
        resposta = ollama.generate(
            model='gemma4:e4b', 
            system=prompt_sistema,
            prompt=prompt_usuario,
            options={"temperature": 0.1}
        )
        
        texto_bruto = resposta['response']
        
        # Passa o texto pela nossa defesa anti-comentários antes de retornar
        return _extrair_sql_limpo(texto_bruto)

    except Exception as e:
        return f"Erro ao nos comunicar com o Ollama: {str(e)}"


def analisar_dados(pergunta_original: str, dados_brutos: str) -> str:
    """
    Recebe a pergunta que o usuário fez e os dados que o banco retornou,
    e pede para o modelo gerar uma análise de negócios resumida.
    """
    prompt_sistema = (
        "Você é um analista de dados e de negócios experiente. "
        "Sua tarefa é interpretar tabelas de dados de forma clara, direta e executiva.\n\n"
        "Regras:\n"
        "1. Seja conciso. Vá direto ao ponto em no máximo um ou dois parágrafos curtos.\n"
        "2. Destaque anomalias, padrões ou informações mais importantes contidas nos dados.\n"
        "3. Mantenha o tom profissional e focado no contexto da pergunta feita pelo usuário."
        "4. Não use termos técnicos que possam ser difíceis de entender para um público não técnico. Use uma linguagem simples e acessível."
        "5. Seja claro e direto, evitando jargões ou explicações desnecessárias. O objetivo é fornecer insights acionáveis de forma rápida e fácil de entender."
        "6. Seja honesto e não esconda informações importantes ou detalhes que podem ser prejudiciais para o usuário."
        "7. Raciocine antes de enviar a resposta final para verificar erros, alucinações ou conclusões precipitadas. Certifique-se de que a análise seja lógica e baseada nos dados apresentados."
    )
    
    prompt_usuario = f"""
    O usuário fez a seguinte pergunta ao sistema: "{pergunta_original}"
    
    O banco de dados retornou o seguinte resultado (em formato de tabela/texto):
    {dados_brutos}
    
    Forneça uma análise resumida e insights sobre estes dados com base na pergunta original:
    """
    
    try:
        resposta = ollama.generate(
            model='gemma4:e4b',
            system=prompt_sistema,
            prompt=prompt_usuario,
            options={"temperature": 0.5} 
        )
        return resposta['response'].strip()
        
    except Exception as e:
        return f"Erro ao gerar análise: {str(e)}"

# Bloco de teste atualizado
if __name__ == "__main__":
    schema_teste = """
    Tabela: clientes (id INT, nome VARCHAR, email VARCHAR, data_cadastro DATE)
    Tabela: pedidos (id INT, cliente_id INT, valor_total DECIMAL, data_pedido DATE)
    """
    
    pergunta_teste = "Quais são os nomes dos clientes que fizeram pedidos com valor total maior que 500 reais?"
    
    print("1. Testando Geração de SQL...")
    sql = gerar_sql(pergunta_teste, schema_teste)
    print(f"SQL:\n{sql}\n")
    
    dados_simulados_banco = """
    | nome          | valor_total |
    |---------------|-------------|
    | João Silva    | 1250.00     |
    | Maria Souza   | 510.00      |
    | Carlos Rossi  | 2300.00     |
    """
    
    print("2. Testando Análise de Dados (Sua nova funcionalidade)...")
    analise = analisar_dados(pergunta_teste, dados_simulados_banco)
    print("--- ANÁLISE DO MODELO ---")
    print(analise)
    print("-------------------------")