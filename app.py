import pandas as pd
import streamlit as st
from openai import OpenAI
import matplotlib.pyplot as plt
import pdfplumber
import pytesseract
from PIL import Image
import io

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar tech")
st.markdown("1️⃣ Envie sua planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça sua pergunta → 4️⃣ Veja a resposta!")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -----------------------------
# Sessão
# -----------------------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []
if "respostas_uteis" not in st.session_state:
    st.session_state["respostas_uteis"] = 0
if "info_adicional" not in st.session_state:
    st.session_state["info_adicional"] = ""
if "tipo_planilha" not in st.session_state:
    st.session_state["tipo_planilha"] = ""

# -----------------------------
# Upload de arquivos
# -----------------------------
uploaded_file = st.file_uploader(
    "📂 Envie sua planilha Excel (.xlsx), PDF ou imagem (.png, .jpg)",
    type=["xlsx", "pdf", "png", "jpg", "jpeg"]
)

# -----------------------------
# Funções auxiliares
# -----------------------------
def detectar_colunas_avancado(df):
    keywords = ["gasto", "valor", "custo", "preço", "despesa", "total"]
    colunas_financeiras = []
    colunas_quase_numericas = []

    new_columns = []
    for i, x in enumerate(df.columns):
        if pd.isna(x) or str(x).strip().lower() in ["unnamed", "untitled"]:
            new_columns.append(f"Col_{i}")
        else:
            new_columns.append(x)
    df.columns = new_columns

    for col in df.columns:
        texto_col = str(col).lower()
        if any(k in texto_col for k in keywords):
            colunas_financeiras.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            colunas_financeiras.append(col)
        else:
            num_na = pd.to_numeric(df[col], errors="coerce")
            if num_na.notna().sum() > 0:
                colunas_quase_numericas.append(col)

    return list(set(colunas_financeiras)), list(set(colunas_quase_numericas)), df


def extrair_texto_pdf(file):
    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() or ""
    return texto


def extrair_texto_imagem(file):
    imagem = Image.open(file)
    return pytesseract.image_to_string(imagem, lang="por")


# -----------------------------
# Processamento de arquivo
# -----------------------------
texto_extraido = None
df = None

if uploaded_file:
    nome = uploaded_file.name.lower()
    try:
        if nome.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
            st.success("✅ Planilha carregada com sucesso!")
        elif nome.endswith(".pdf"):
            texto_extraido = extrair_texto_pdf(uploaded_file)
            st.success("✅ Texto extraído do PDF com sucesso!")
        elif nome.endswith((".png", ".jpg", ".jpeg")):
            texto_extraido = extrair_texto_imagem(uploaded_file)
            st.success("✅ Texto extraído da imagem com sucesso!")
    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo: {e}")
        st.stop()

# -----------------------------
# Tipo da planilha
# -----------------------------
tipo_planilha = st.text_input(
    "🗂 Qual o tipo de conteúdo (ex.: gastos, vendas, despesas...)?",
    st.session_state.get("tipo_planilha", "")
)
if tipo_planilha:
    st.session_state["tipo_planilha"] = tipo_planilha

# -----------------------------
# Se for planilha Excel
# -----------------------------
if df is not None:
    col_financeiras, col_quase_numericas, df = detectar_colunas_avancado(df)

    st.sidebar.subheader("💰 Colunas financeiras detectadas")
    st.sidebar.write(col_financeiras)

    col_financeiras_ajustadas = st.multiselect(
        "Selecione as colunas financeiras relevantes:",
        options=df.columns,
        default=col_financeiras
    )

# -----------------------------
# Pergunta
# -----------------------------
pergunta = st.text_input("💬 Faça sua pergunta:")
tipo_resposta = st.radio("Tipo de resposta:", ["Resumo simples", "Detalhes adicionais"], index=0)

if st.button("🔍 Perguntar") and pergunta and tipo_planilha:
    try:
        if df is not None:
            resumo = {
                "tipo_planilha": tipo_planilha,
                "colunas": df.dtypes.apply(lambda x: str(x)).to_dict(),
                "amostra": df.head(10).to_dict(orient="records"),
            }
            conteudo = f"Resumo da planilha:\n{resumo}\nPergunta: {pergunta}"
        else:
            conteudo = f"Texto detectado:\n{texto_extraido}\nPergunta: {pergunta}"

        prompt_system = (
            "Você é um assistente especialista em análise de dados e textos financeiros em português. "
            "Responda de forma clara, precisa e sem inventar informações. "
            "Se não houver dados suficientes, diga 'Não encontrado'. "
            "Organize em duas partes: 'Resumo simples' e 'Detalhes adicionais'."
        )

        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": conteudo}
            ]
        )
        texto_completo = resposta.choices[0].message.content.strip()

        # Divisão da resposta
        if "Resumo simples:" in texto_completo and "Detalhes adicionais:" in texto_completo:
            resumo_simples = texto_completo.split("Resumo simples:")[1].split("Detalhes adicionais:")[0].strip()
            detalhes = texto_completo.split("Detalhes adicionais:")[1].strip()
        else:
            resumo_simples = texto_completo
            detalhes = texto_completo

        resposta_final = resumo_simples if tipo_resposta == "Resumo simples" else detalhes
        st.subheader("✅ Resposta:")
        st.write(resposta_final)

        st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta_final})
    except Exception as e:
        st.error(f"Erro: {e}")

# -----------------------------
# Visualização básica (se Excel)
# -----------------------------
if df is not None:
    st.subheader("📊 Visualizações rápidas")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("📈 Soma por coluna numérica"):
            numeric_cols = df.select_dtypes(include="number").columns
            if len(numeric_cols) > 0:
                fig, ax = plt.subplots()
                df[numeric_cols].sum().sort_values().plot(kind="bar", ax=ax, color="skyblue")
                st.pyplot(fig)
            else:
                st.info("Nenhuma coluna numérica detectada.")

    with col2:
        if st.button("📉 Média por coluna numérica"):
            numeric_cols = df.select_dtypes(include="number").columns
            if len(numeric_cols) > 0:
                fig, ax = plt.subplots()
                df[numeric_cols].mean().sort_values().plot(kind="bar", ax=ax, color="lightgreen")
                st.pyplot(fig)
            else:
                st.info("Nenhuma coluna numérica detectada.")

# -----------------------------
# Histórico
# -----------------------------
if st.session_state.get("historico"):
    st.subheader("📜 Histórico de perguntas")
    for h in reversed(st.session_state["historico"][-5:]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
