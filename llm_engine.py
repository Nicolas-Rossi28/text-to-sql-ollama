import ollama
import re

def gerar_sql(pergunta: str, schema_banco: str) -> str:
    """
    Envia o esquema do banco e a pergunta em linguagem natural para o Qwen
    e retorna a query SQL gerada.
    """
    prompt_sistema = (
        "Você é um especialista em bancos de dados SQL. "
        "Sua tarefa é converter perguntas em linguagem natural em consultas SQL válidas.\n\n"
        "Regras estritas:\n"
        "1. Responda APENAS com o código SQL executável.\n"
        "2. Não adicione explicações, saudações ou textos antes/depois do código.\n"
        "3. Não use blocos de Markdown (como ```sql ... ```) na sua resposta final se puder, "
        "mas caso use, garanta que o código esteja correto.\n"
        "4. Use apenas as tabelas e colunas informadas no contexto abaixo.\n"
        "5. Não realize qualquer modificação no contexto ou na pergunta.\n"
        "6. Se a consulta SQL gerada não retornar resultados, responda com 'Nenhum resultado encontrado'.\n"
        "7. Não realize nenhuma modificação como DELETE, UPDATE ou INSERT. Apenas SELECTs são permitidos."
    )
    
    prompt_usuario = f"""
    Contexto do Banco de Dados (Esquema):
    {schema_banco}
    
    Pergunta do Usuário: "{pergunta}"
    
    Consulta SQL:
    """
    
    try:
        resposta = ollama.generate(
            model='qwen2.5-coder:7b',
            system=prompt_sistema,
            prompt=prompt_usuario,
            options={"temperature": 0.1}
        )
        
        sql_gerado = resposta['response'].strip()
        sql_gerado = re.sub(r'```sql\s*|\s*```', '', sql_gerado)
        sql_gerado = re.sub(r'```\s*|\s*```', '', sql_gerado)
        
        return sql_gerado.strip()

    except Exception as e:
        return f"Erro ao nos comunicar com o Ollama: {str(e)}"


def analisar_dados(pergunta_original: str, dados_brutos: str) -> str:
    """
    Nova Função: Recebe a pergunta que o usuário fez e os dados que o banco retornou,
    e pede para o Qwen gerar uma análise de negócios resumida.
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
    )
    
    prompt_usuario = f"""
    O usuário fez a seguinte pergunta ao sistema: "{pergunta_original}"
    
    O banco de dados retornou o seguinte resultado (em formato de tabela/texto):
    {dados_brutos}
    
    Forneça uma análise resumida e insights sobre estes dados com base na pergunta original:
    """
    
    try:
        resposta = ollama.generate(
            model='qwen2.5-coder:7b', # Podemos usar o mesmo modelo, ele é ótimo para lógica geral também
            system=prompt_sistema,
            prompt=prompt_usuario,
            options={"temperature": 0.5} # Temperatura ligeiramente maior para o texto soar mais natural e menos robótico
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
    print(f"SQL: {sql}\n")
    
    # Simulação dos dados que o banco devolveria para esse SQL
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