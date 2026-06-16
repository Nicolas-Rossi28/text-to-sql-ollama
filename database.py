from sqlalchemy import create_engine, inspect
import pandas as pd

def conectar_banco(tipo_banco, usuario, senha, host, porta, nome_banco):
    """
    Cria o 'Engine' de conexão com o banco de dados baseado na escolha do usuário.
    """
    if tipo_banco.lower() == "mysql":
        # Usamos o driver 'pymysql' para o MySQL
        url = f"mysql+pymysql://{usuario}:{senha}@{host}:{porta}/{nome_banco}"
    else:
        # Usamos o driver 'psycopg2' para o PostgreSQL
        url = f"postgresql+psycopg2://{usuario}:{senha}@{host}:{porta}/{nome_banco}"
    
    # O create_engine não conecta de imediato, ele apenas prepara a ponte
    engine = create_engine(url)
    return engine

def extrair_esquema(engine) -> str:
    """
    Varre o banco de dados e monta um texto rico contendo Tabelas, 
    Colunas, Chaves Primárias e Chaves Estrangeiras (Relacionamentos).
    """
    inspector = inspect(engine)
    esquema_texto = ""
    
    tabelas = inspector.get_table_names()
    
    for tabela in tabelas:
        esquema_texto += f"Tabela: {tabela}\nColunas:\n"
        
        # 1. Puxa colunas e chaves primárias
        colunas = inspector.get_columns(tabela)
        pk_info = inspector.get_pk_constraint(tabela)
        colunas_pk = pk_info.get('constrained_columns', [])
        
        for coluna in colunas:
            nome_coluna = coluna['name']
            tipo_coluna = str(coluna['type'])
            
            # Se a coluna atual estiver na lista de PKs, adicionamos a marcação
            is_pk = " [CHAVE PRIMÁRIA]" if nome_coluna in colunas_pk else ""
            
            esquema_texto += f"  - {nome_coluna} ({tipo_coluna}){is_pk}\n"
        
        # 2. Puxa chaves estrangeiras (Relacionamentos)
        fks = inspector.get_foreign_keys(tabela)
        if fks:
            esquema_texto += "Relacionamentos (Chaves Estrangeiras):\n"
            for fk in fks:
                # coluna_local -> coluna_estrangeira na tabela_estrangeira
                coluna_local   = fk['constrained_columns'][0]
                tabela_destino = fk['referred_table']
                coluna_destino = fk['referred_columns'][0]
                
                esquema_texto += f"  - Coluna '{coluna_local}' aponta para '{tabela_destino}.{coluna_destino}'\n"
                
        esquema_texto += "\n" # Espaço entre tabelas
        
    return esquema_texto

def executar_query(sql_query, engine):
    """
    Executa a query SQL no banco de dados e retorna um DataFrame do Pandas.
    """
    # O pandas se conecta usando nossa engine, roda o SQL e já organiza em linhas e colunas
    df = pd.read_sql_query(sql_query, engine)
    return df