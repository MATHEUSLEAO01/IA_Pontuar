import streamlit as st
import pandas as pd
from openai import OpenAI
import pdfplumber
from PIL import Image
import pytesseract
import camelot
import re

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
st.markdown("1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

# OpenAI
client = OpenAI(api_key=st.secrets["general"]["OPENAI_API_KEY"])

# -----------------------------
# Sessão
# -----------------------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []

# -----------------------------
# Upload
# -----------------------------
uploaded_file = st.file_uploader(
    "📂 Envie planilha (.xlsx), PDF ou imagem (.png, .jpg, .jpeg)",
    type=["xlsx", "pdf", "png", "jpg", "jpeg"]
)

# -----------------------------
# Funções auxiliares
# -----------------------------
def extrair_texto_pdf(file):
    texto = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                texto += page.extract_text() or ""
    except:
        pass
    return texto

def extrair_tabelas_pdf(file):
    try:
        tables = camelot.read_pdf(file, pages="all", flavor="stream")
        if tables and len(tables) > 0:
            df = tables[0].df
            df.columns = df.iloc[0]
            df = df[1:]
            return df
    except:
        return None
    return None

def extrair_texto_imagem(file):
    imagem = Image.open(file)
    return pytesseract.image_to_string(imagem, lang="por")

def extrair_valores_legiveis(texto):
    """Encontra valores no texto e retorna como lista legível"""
    # Regex para valores R$ ou apenas números com vírgula
    valores = re.findall(r"R?\$?\s*\d{1,3}(?:,\d{2})?", texto)
    # Remove duplicados e espaços
    valores = [v.replace("R$", "").strip() for v in valores]
    return ", ".join(valores) if valores else "Nenhum valor encontrado"

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
# Caixa de pergunta
# -----------------------------
pergunta = st.text_input("💬 Sua pergunta:")

# -----------------------------
# Botão limpar histórico
# -----------------------------
if st.button("🧹 Limpar histórico"):
    st.session_state["historico"] = []
    st.success("Histórico limpo!")

# -----------------------------
# Processamento
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido):
    try:
        # Cria conteúdo resumido
        if df is not None:
            # pega apenas primeiras 5 linhas e colunas para não sobrecarregar
            conteudo = f"Colunas: {list(df.columns)}\nAmostra: {df.head(5).to_dict(orient='records')}\nPergunta: {pergunta}"
            texto_para_extrair_valores = df.to_string()
        else:
            # pega só os primeiros 1000 caracteres do texto
            conteudo = f"Texto detectado:\n{texto_extraido[:1000]}\nPergunta: {pergunta}"
            texto_para_extrair_valores = texto_extraido

        # Extrai valores de forma legível
        valores_legiveis = extrair_valores_legiveis(texto_para_extrair_valores)

        # Monta resposta clara
        resposta = f"💰 Valores encontrados relacionados à sua pergunta:\n{valores_legiveis}"

        st.subheader("✅ Resposta Detalhada:")
        st.write(resposta)

        # Mantém histórico limitado a 3
        st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})
        if len(st.session_state["historico"]) > 3:
            st.session_state["historico"] = st.session_state["historico"][-3:]

    except Exception as e:
        st.error(f"Erro: {e}")

# -----------------------------
# Histórico
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
