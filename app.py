import streamlit as st
import pandas as pd
import re
from fuzzywuzzy import fuzz, process

# ============================================================
# 📜 Histórico de perguntas e respostas
# ============================================================
if "historico" not in st.session_state:
    st.session_state["historico"] = []

def adicionar_historico(pergunta, resposta):
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})
    if len(st.session_state["historico"]) > 3:
        st.session_state["historico"] = st.session_state["historico"][-3:]

# ============================================================
# 💻 Layout principal
# ============================================================
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
uploaded_file = st.file_uploader(
    "📂 Envie planilha",
    type=["xlsx", "csv"]
)
item = st.text_input("💬 Digite o item que deseja consultar (ex: Fígado)")

if st.button("🔍 Consultar") and uploaded_file and item:
    resposta = ""
    try:
        # Ler a planilha
        if uploaded_file.type == "text/csv":
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        colunas = df.columns.tolist()

        # Procurar a coluna do item usando fuzzy matching
        melhor_coluna, score_item = process.extractOne(item, colunas, scorer=fuzz.partial_ratio)
        if score_item < 60:
            resposta = f"❌ Nenhuma coluna próxima de '{item}' encontrada."
        else:
            # Procurar coluna de Estado (assumindo que exista alguma coluna relacionada)
            estado_colunas = [c for c in colunas if "estado" in c.lower() or "uf" in c.lower()]
            if estado_colunas:
                estado_coluna = estado_colunas[0]
            else:
                estado_coluna = None

            resultados = []
            for _, row in df.iterrows():
                estado = row[estado_coluna] if estado_coluna else "Linha " + str(_+1)
                valor = str(row[melhor_coluna])
                match = re.search(r'\d+[.,]\d+', valor)
                if match:
                    v = match.group().replace(".", ",")
                    resultados.append({"Estado": estado, item: f"R$ {v}"})
            
            if resultados:
                df_result = pd.DataFrame(resultados)
                st.dataframe(df_result)
                resposta = f"💰 Valores encontrados para '{item}' por estado."
            else:
                resposta = f"❌ Nenhum valor encontrado para '{item}'."

    except Exception as e:
        resposta = f"❌ Erro ao processar planilha: {e}"

    adicionar_historico(item, resposta)
    st.success(resposta)

# ============================================================
# 🕓 Histórico (máx. 3)
# ============================================================
st.subheader("📜 Histórico das últimas perguntas")
for item_hist in reversed(st.session_state["historico"]):
    st.write(f"**Pergunta:** {item_hist['pergunta']}")
    st.write(f"**Resposta:** {item_hist['resposta']}")
    st.markdown("---")

# ============================================================
# 🧹 Limpar histórico
# ============================================================
if st.button("🧹 Limpar histórico"):
    st.session_state["historico"] = []
    st.success("✅ Histórico limpo!")
