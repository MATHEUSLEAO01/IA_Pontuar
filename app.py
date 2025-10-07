import streamlit as st
import pandas as pd
from openai import OpenAI
import pdfplumber
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import camelot
import re
from transformers import pipeline

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
st.markdown("1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

# OpenAI
client = OpenAI(api_key=st.secrets["general"]["OPENAI_API_KEY"])

# Hugging Face como fallback gratuito
hf_pipeline = pipeline("text-generation", model="bigscience/bloom-560m", device=-1)  # CPU

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

def pre_processar_imagem(imagem):
    # Converter para cinza
    imagem = imagem.convert("L")
    # Aumentar contraste
    imagem = ImageEnhance.Contrast(imagem).enhance(2)
    # Filtro de nitidez
    imagem = imagem.filter(ImageFilter.SHARPEN)
    return imagem

def extrair_texto_imagem(file):
    imagem = Image.open(file)
    imagem = pre_processar_imagem(imagem)
    texto = pytesseract.image_to_string(imagem, lang="por")
    # Limpeza básica
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto

def extrair_valores(texto):
    # Regex robusta para capturar R$ e números com vírgula
    valores = re.findall(r"(?:R\$?\s*)?(\d{1,3},\d{2})", texto)
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
# Função para gerar resposta HF
# -----------------------------
def gerar_resposta_hf(conteudo):
    try:
        if len(conteudo) > 1000:  # limitar para não travar o modelo
            conteudo = conteudo[-1000:]
        saida = hf_pipeline(f"Responda detalhadamente: {conteudo}", max_new_tokens=256)
        return saida[0]["generated_text"]
    except:
        return "Não foi possível gerar resposta gratuita."

# -----------------------------
# Processamento
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido):
    try:
        if df is not None:
            conteudo = df.to_string()
        else:
            conteudo = texto_extraido
        
        # Extrair valores limpos
        valores_encontrados = extrair_valores(conteudo)
        if valores_encontrados:
            resposta = f"💰 Valores encontrados: {', '.join(valores_encontrados)}"
        else:
            resposta = "Nenhum valor encontrado para este item."

        st.subheader("✅ Resposta Detalhada:")
        st.write(resposta)

        # Histórico limitado a 3
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

# -----------------------------
# Botão para limpar histórico
# -----------------------------
if st.button("🧹 Limpar Histórico"):
    st.session_state["historico"] = []
    st.success("Histórico limpo!")
