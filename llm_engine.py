import ollama
import re

def gerar_sql(pergunta: str, schema_banco: str) -> str:
    """
    Envia o esquema do banco e a pergunta em linguagem natural para o Qwen
    e retorna a query SQL gerada.
    """
    
    # O Prompt de Sistema molda o comportamento do modelo
    prompt_sistema = (
        "Você é um especialista em bancos de dados SQL. "
        "Sua tarefa é converter perguntas em linguagem natural em consultas SQL válidas.\n\n"
        "Regras estritas:\n"
        "1. Responda APENAS com o código SQL executável.\n"
        "2. Não adicione explicações, saudações ou textos antes/depois do código.\n"
        "3. Não use blocos de Markdown (como ```sql ... ```) na sua resposta final se puder, "
        "mas caso use, garanta que o código esteja correto.\n"
        "4. Use apenas as tabelas e colunas informadas no contexto abaixo."
        "5. Não realize qualquer modificação no contexto ou na pergunta.\n"
        "6. Se a consulta SQL gerada não retornar resultados, responda com 'Nenhum resultado encontrado'.\n\n"
        "7. Não realize nenhuma modificação como DELETE, UPDATE ou INSERT. Apenas SELECTs são permitidos."
    )
    
    # O Prompt do Usuario junta o esquema (contexto) com a pergunta real
    prompt_usuario = f"""
    Contexto do Banco de Dados (Esquema):
    {schema_banco}
    
    Pergunta do Usuário: "{pergunta}"
    
    Consulta SQL:
    """
    
    try:
        # Chamada para a API local do Ollama
        resposta = ollama.generate(
            model='qwen2.5-coder:7b', #seleciona modelo utilizado
            system=prompt_sistema,
            prompt=prompt_usuario,
            options={
                "temperature": 0.1 # Temperatura baixa = respostas mais precisas e menos "criativas"
            }
        )
        
        sql_gerado = resposta['response'].strip()
        
        # Limpeza extra: Caso o modelo insista em colocar as crases de markdown (```sql)
        sql_gerado = re.sub(r'```sql\s*|\s*```', '', sql_gerado)
        sql_gerado = re.sub(r'```\s*|\s*```', '', sql_gerado)
        
        return sql_gerado.strip()

    except Exception as e:
        return f"Erro ao nos comunicar com o Ollama: {str(e)}"

# Bloco de teste (Executa apenas se você rodar este arquivo diretamente)
if __name__ == "__main__":
    # Simulando um esquema de banco de dados que virá do SQLAlchemy depois
    schema_teste = """
    Tabela: clientes (id INT, nome VARCHAR, email VARCHAR, data_cadastro DATE)
    Tabela: pedidos (id INT, cliente_id INT, valor_total DECIMAL, data_pedido DATE)
    """
    
    pergunta_teste = "Quais são os nomes dos clientes que fizeram pedidos com valor total maior que 500 reais?"
    
    print("Enviando para o Qwen...")
    resultado = gerar_sql(pergunta_teste, schema_teste)
    
    print("\n--- SQL GERADO ---")
    print(resultado)
    print("------------------")