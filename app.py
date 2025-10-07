import streamlit as st
import pandas as pd
from openai import OpenAI
import pdfplumber
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import camelot
import re

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
st.markdown("1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Faça uma pergunta → 3️⃣ Veja a resposta!")

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

def preprocess_image(file):
    imagem = Image.open(file).convert("L")  # cinza
    imagem = ImageEnhance.Contrast(imagem).enhance(2)  # aumenta contraste
    imagem = imagem.filter(ImageFilter.SHARPEN)  # nitidez
    return imagem

def extrair_texto_imagem(file):
    imagem = preprocess_image(file)
    texto = pytesseract.image_to_string(imagem, lang="por")
    # Normalizar texto
    texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto

def extrair_valores(texto):
    # Regex para valores R$ ou apenas números com vírgula
    valores = re.findall(r"R?\$?\s*\d{1,3},\d{2}", texto)
    valores = [v.replace("R$", "").replace("R", "").strip() for v in valores]
    valores = [f"R$ {v}" for v in valores]
    return valores

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
if st.button("🗑 Limpar Histórico"):
    st.session_state["historico"] = []

# -----------------------------
# Processamento
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido) and pergunta:
    try:
        conteudo = ""
        if df is not None:
            conteudo = df.to_csv(index=False)
        elif texto_extraido:
            conteudo = texto_extraido

        # Extrair valores
        valores = extrair_valores(conteudo)

        # Tentar achar valor exato da pergunta
        resposta = "Nenhum valor encontrado para este item."
        for v in valores:
            if pergunta.lower() in conteudo.lower():
                resposta = f"💰 Valores relacionados: {', '.join(valores)}"
                break
        if valores and "Nenhum valor" in resposta:
            resposta = f"💰 Valores encontrados: {', '.join(valores)}"

        st.subheader("✅ Resposta Detalhada:")
        st.write(resposta)

        # Salvar histórico (máx 3 últimos)
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
