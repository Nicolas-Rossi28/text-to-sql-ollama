import streamlit as st
import pandas as pd

from database import conectar_banco, extrair_esquema, executar_query
from llm_engine import gerar_sql, analisar_dados

# Configura o título que aparece na aba do navegador e o layout expandido
st.set_page_config(page_title="Abadats.AI", page_icon="🧙‍♂️", layout="wide")

st.title("🧙‍♂️ ABADATS, O Assistente de Banco de Dados Text-to-SQL")
st.subheader("Converse com seus dados em linguagem natural")

# Inicialização de variáveis de estado para o Chat e Insights
if 'mensagens' not in st.session_state:
    st.session_state['mensagens'] = []
if 'dados_para_insight' not in st.session_state:
    st.session_state['dados_para_insight'] = None
if 'pergunta_para_insight' not in st.session_state:
    st.session_state['pergunta_para_insight'] = ""

# ---------------------------------------------------------------------------
# BARRA LATERAL — CONFIGURAÇÃO DE CONEXÃO
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header(" Configuração da Conexão")
    
    tipo_banco = st.selectbox("Tipo do Banco", ["PostgreSQL", "MySQL"])
    
    host = st.text_input("Host/Servidor", value="localhost")
    porta = st.text_input("Porta", value="5432" if tipo_banco == "PostgreSQL" else "3306")
    usuario = st.text_input("Usuário", value="")
    senha = st.text_input("Senha", type="password")
    nome_banco = st.text_input("Nome do Banco de Dados")
    
    botao_conectar = st.button("Conectar ao Banco")
    
if botao_conectar:
    try:
        engine = conectar_banco(tipo_banco, usuario, senha, host, porta, nome_banco)
        esquema = extrair_esquema(engine)
        
        st.session_state['engine'] = engine
        st.session_state['esquema'] = esquema
        st.session_state['conectado'] = True
        
        # Limpa o histórico visual do chat ao conectar em um novo banco
        st.session_state['mensagens'] = []
        st.session_state['dados_para_insight'] = None
        
        st.sidebar.success("Conectado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao conectar: {str(e)}")
        st.session_state['conectado'] = False
        


# ---------------------------------------------------------------------------
# INTERFACE PRINCIPAL DE CHAT (só exibe se estiver conectado)
# ---------------------------------------------------------------------------
if st.session_state.get('conectado', False):
    
    # Mostra para o usuário o esquema que a IA está lendo
    with st.expander(" Mapeamento do Schema Atual (O que a IA enxerga)"):
        st.text(st.session_state['esquema'])
        
    st.write("---")

    # 1. RENDERIZA O HISTÓRICO VISUAL
    for msg in st.session_state['mensagens']:
        # Define o ícone correto dependendo de quem está falando
        icone_avatar = "🧙‍♂️" if msg["role"] == "assistant" else "👤"
        
        with st.chat_message(msg["role"], avatar=icone_avatar):
            st.write(msg["content"])
            
            # Se a mensagem do assistente contiver SQL, desenha o bloco de código
            if "sql" in msg and msg["sql"]:
                st.code(msg["sql"], language="sql")
                
            # Se a mensagem do assistente contiver dados, desenha a tabela
            if "dados" in msg and msg["dados"] is not None:
                st.dataframe(msg["dados"])

    # 2. BOTÃO DE INSIGHTS (Aparece logo abaixo da última resposta bem-sucedida)
    if st.session_state['dados_para_insight'] is not None:
        col1, col2, col3 = st.columns([4, 4, 2]) # Alinha à direita
        with col3:
            if st.button("🔮 Gerar Insights da Última Consulta", use_container_width=True):
                # Avatar de mago também no momento da análise!
                with st.chat_message("assistant", avatar="🧙‍♂️"):
                    with st.spinner("Abadats está utilizando de magia negra para analisar os dados..."):
                        pergunta_ref = st.session_state['pergunta_para_insight']
                        dados_brutos = st.session_state['dados_para_insight']
                        
                        insights = analisar_dados(pergunta_ref, dados_brutos)
                        
                        st.info(insights)
                        
                        # Salva o insight gerado no histórico do chat
                        st.session_state['mensagens'].append({
                            "role": "assistant",
                            "content": f"**🔮 Insights da Análise:**\n\n{insights}"
                        })
                        
                # Limpa a variável para o botão desaparecer após o uso
                st.session_state['dados_para_insight'] = None
                st.rerun()

    # 3. CAMPO DE ENTRADA DO CHAT
    if pergunta := st.chat_input("Digite sua pergunta em português:"):
        
        # Exibe a pergunta na tela imediatamente com o ícone de usuário
        with st.chat_message("user", avatar="👤"):
            st.write(pergunta)
            
        # Salva a pergunta no histórico visual
        st.session_state['mensagens'].append({"role": "user", "content": pergunta})
        
        # Inicia a resposta do assistente com o ícone de mago
        with st.chat_message("assistant", avatar="🧙‍♂️"):
            with st.spinner("Abadats está consultando o oraculo para gerar a query..."):
                
                sql_gerado = gerar_sql(pergunta, st.session_state['esquema'])
                
            st.code(sql_gerado, language="sql")
            
            try:
                with st.spinner("Abadats está executando a query no banco de dados..."):
                    df_resultados = executar_query(sql_gerado, st.session_state['engine'])
                
                if not df_resultados.empty:
                    st.success(f"Encontrados {len(df_resultados)} registros!")
                    st.dataframe(df_resultados)
                    
                    # Salva a resposta de sucesso no histórico visual
                    st.session_state['mensagens'].append({
                        "role": "assistant",
                        "content": "Aqui estão os resultados encontrados:",
                        "sql": sql_gerado,
                        "dados": df_resultados
                    })
                    
                    # Prepara os dados para o botão de insights aparecer (limitando a 100 linhas para economizar memória e contexto)
                    st.session_state['dados_para_insight'] = df_resultados.head(100).to_markdown(index=False)
                    st.session_state['pergunta_para_insight'] = pergunta
                    
                else:
                    st.warning("A consulta executou, mas o banco retornou zero linhas.")
                    st.session_state['mensagens'].append({
                        "role": "assistant",
                        "content": "A consulta executou perfeitamente, mas o banco retornou zero linhas.",
                        "sql": sql_gerado
                    })
                    st.session_state['dados_para_insight'] = None
                    
            except Exception as sql_err:
                texto_erro = f"Erro de execução no Banco de Dados: {str(sql_err)}"
                st.error(texto_erro)
                
                # Registra o erro no histórico visual
                st.session_state['mensagens'].append({
                    "role": "assistant",
                    "content": texto_erro,
                    "sql": sql_gerado
                })
                st.session_state['dados_para_insight'] = None
                
        # Atualiza a tela para exibir tudo corretamente
        st.rerun()

else:
    st.info("Aguardando conexão com o banco de dados na barra lateral para liberar o chat.")