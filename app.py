import pandas as pd
import streamlit as st
from openai import OpenAI
import matplotlib.pyplot as plt
import pdfplumber
import pytesseract
from PIL import Image
import io
import camelot

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar tech")
st.markdown("1️⃣ Envie uma planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -----------------------------
# Sessão
# -----------------------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []

# -----------------------------
# Upload
# -----------------------------
uploaded_file = st.file_uploader(
    "📂 Envie uma planilha (.xlsx), PDF ou imagem (.png, .jpg)",
    type=["xlsx", "pdf", "png", "jpg", "jpeg"]
)

# -----------------------------
# Funções auxiliares
# -----------------------------
def detectar_colunas_avancado(df):
    keywords = ["gasto", "valor", "custo", "preço", "despesa", "total"]
    colunas_financeiras = []
    for col in df.columns:
        texto = str(col).lower()
        if any(k in texto for k in keywords) or pd.api.types.is_numeric_dtype(df[col]):
            colunas_financeiras.append(col)
    return list(set(colunas_financeiras)), df


def extrair_texto_pdf(file):
    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() or ""
    return texto


def extrair_tabelas_pdf(file):
    """Extrai tabelas do PDF e retorna o primeiro DataFrame encontrado."""
    try:
        tables = camelot.read_pdf(file, pages="all", flavor="stream")
        if tables and len(tables) > 0:
            df = tables[0].df
            df.columns = df.iloc[0]
            df = df[1:]
            return df
    except Exception:
        pass
    return None


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
            st.success("✅ Planilha Excel carregada!")
        elif nome.endswith(".pdf"):
            # Primeiro tenta extrair tabela
            df = extrair_tabelas_pdf(uploaded_file)
            if df is not None:
                st.success("✅ Tabela detectada e carregada do PDF!")
            else:
                texto_extraido = extrair_texto_pdf(uploaded_file)
                st.info("📄 Nenhuma tabela detectada — texto extraído para análise.")
        elif nome.endswith((".png", ".jpg", ".jpeg")):
            texto_extraido = extrair_texto_imagem(uploaded_file)
            st.success("✅ Texto extraído da imagem!")
    except Exception as e:
        st.error(f"❌ Erro ao processar: {e}")
        st.stop()

# -----------------------------
# Tipo de conteúdo
# -----------------------------
tipo_planilha = st.text_input("🗂 Qual o tipo de conteúdo? (ex.: vendas, gastos, notas fiscais...)")

# -----------------------------
# Caixa de pergunta
# -----------------------------
pergunta = st.text_input("💬 Sua pergunta:")
tipo_resposta = st.radio("Tipo de resposta:", ["Resumo simples", "Detalhes adicionais"], index=0)

# -----------------------------
# Processamento
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido) and tipo_planilha:
    try:
        if df is not None:
            resumo = {
                "tipo_planilha": tipo_planilha,
                "colunas": list(df.columns),
                "amostra": df.head(10).to_dict(orient="records"),
            }
            conteudo = f"Resumo da planilha:\n{resumo}\nPergunta: {pergunta}"
        else:
            conteudo = f"Texto detectado:\n{texto_extraido}\nPergunta: {pergunta}"

        prompt_system = (
            "Você é um assistente especialista em análise de planilhas, PDFs e textos financeiros em português. "
            "Analise os dados e responda com clareza e precisão. "
            "Organize sua resposta em duas partes: 'Resumo simples' e 'Detalhes adicionais'. "
            "Se algo não for encontrado, diga 'Não encontrado'."
        )

        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": conteudo}
            ]
        )

        texto_completo = resposta.choices[0].message.content.strip()

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
# Visualizações
# -----------------------------
if df is not None:
    st.subheader("📊 Visualizações básicas")
    numeric_cols = df.select_dtypes(include="number").columns
    if len(numeric_cols) > 0:
        if st.button("📈 Gráfico de somas"):
            fig, ax = plt.subplots()
            df[numeric_cols].sum().plot(kind="bar", ax=ax, color="skyblue")
            st.pyplot(fig)
        if st.button("📉 Gráfico de médias"):
            fig, ax = plt.subplots()
            df[numeric_cols].mean().plot(kind="bar", ax=ax, color="lightgreen")
            st.pyplot(fig)
    else:
        st.info("Nenhuma coluna numérica detectada.")

# -----------------------------
# Histórico
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"][-5:]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
