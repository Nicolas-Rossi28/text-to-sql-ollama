import streamlit as st
import pandas as pd

from database import conectar_banco, extrair_esquema, executar_query
from llm_engine import gerar_sql, analisar_dados

# Configura o título que aparece na aba do navegador e o layout expandido
st.set_page_config(page_title="Abadats.AI", page_icon="🧙‍♂️",layout="wide")

st.title("🧙‍♂️ ABADATS, O  Assistente de Banco de Dados Text-to-SQL")
st.subheader("Converse com seus dados em linguagem natural")

# Criando a barra lateral
with st.sidebar:
    st.header(" Configuração da Conexão")
    
    # Caixa de seleção para o tipo de banco
    tipo_banco = st.selectbox("Tipo do Banco", ["PostgreSQL", "MySQL"])
    
    # Campos de texto para as credenciais
    host = st.text_input("Host/Servidor", value="localhost")
    porta = st.text_input("Porta", value="5432" if tipo_banco == "PostgreSQL" else "3306")
    usuario = st.text_input("Usuário", value="")
    senha = st.text_input("Senha", type="password")
    nome_banco = st.text_input("Nome do Banco de Dados")
    
    # Botão para ativar a conexão
    botao_conectar = st.button("Conectar ao Banco")
    
    # Se o usuário clicar em conectar, tentamos estabelecer a ponte
if botao_conectar:
    try:
        # 1. Cria a engine usando nossa função do database.py
        engine = conectar_banco(tipo_banco, usuario, senha, host, porta, nome_banco)
        
        # 2. Extrai o esquema completo (com as PKs e FKs que ajustamos)
        esquema = extrair_esquema(engine)
        
        # 3. Salva tudo na memória da sessão para usar depois
        st.session_state['engine'] = engine
        st.session_state['esquema'] = esquema
        st.session_state['conectado'] = True
        
        st.sidebar.success("Conectado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao conectar: {str(e)}")
        st.session_state['conectado'] = False
        
# Se o banco estiver conectado com sucesso, exibe a interface de consulta
if st.session_state.get('conectado', False):
    
    # Mostra para o usuário o esquema que a IA está lendo (ajuda a auditar o app)
    with st.expander(" Mapeamento do Schema Atual (O que a IA enxerga)"):
        st.text(st.session_state['esquema'])
        
    # Caixa de texto para a pergunta em linguagem natural
    pergunta = st.text_input(" Digite sua pergunta em português (Ex: 'Quais produtos estão sem estoque?'):")
    
    if st.button("Buscar no Banco"):
        if pergunta:
            # animação de carregamento
            with st.spinner("Pensando... Traduzindo para SQL..."):
                # Busca a query gerada pelo Qwen
                sql_gerado = gerar_sql(pergunta, st.session_state['esquema'])
                
            st.code(sql_gerado, language="sql")
            
            try:
                # Executa o SQL gerado no nosso banco
                with st.spinner("Executando query no banco de dados..."):
                    df_resultados = executar_query(sql_gerado, st.session_state['engine'])
                
                # Se trouxer dados, exibe a tabela e guarda na sessão para a análise
                if not df_resultados.empty:
                    st.success(f"Encontrados {len(df_resultados)} registros!")
                    st.dataframe(df_resultados) # Desenha a tabela bonita na tela
                    
                    # Guarda os dados e a pergunta para a caixinha de insights usar
                    st.session_state['dados_atuais'] = df_resultados
                    st.session_state['pergunta_atual'] = pergunta
                else:
                    st.warning("A consulta executou, mas o banco retornou zero linhas.")
                    
            except Exception as sql_err:
                st.error(f"Erro de execução no Banco de Dados: {str(sql_err)}")
                
    # --- INSIGHTS APÓS OS DADOS ---
    if 'dados_atuais' in st.session_state:
        st.write("---") # Linha divisória
        
        # O botão de sugestão de análise só aparece após a tabela estar na tela
        if st.button(" Gerar Análise [Insights do ABADATS🔮] "):
            with st.spinner("Analisando os registros gerados..."):
                # Convertemos a tabela de dados em texto simples (Markdown) para o Qwen ler
                dados_em_texto = st.session_state['dados_atuais'].to_markdown(index=False)
                
                # Chama a segunda função do llm_engine.py
                insights = analisar_dados(st.session_state['pergunta_atual'], dados_em_texto)
                
                # Exibe a resposta analítica dentro de uma caixinha de informação azul
                st.info(insights)
else:
    st.info("Aguardando conexão com o banco de dados na barra lateral para liberar as consultas.")