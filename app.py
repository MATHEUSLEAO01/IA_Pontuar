import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import re
import pandas as pd
from io import BytesIO
import cv2
import numpy as np
from fuzzywuzzy import fuzz, process

# --- Função de pré-processamento da imagem ---
def pre_processar_imagem(img_file):
    img = Image.open(img_file).convert("RGB")
    img_cv = np.array(img)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    gray = cv2.medianBlur(gray, 3)
    # aumentar contraste
    gray = cv2.convertScaleAbs(gray, alpha=2, beta=0)
    # binarização
    _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
    return thresh

# --- Função OCR para extrair texto ---
def extrair_texto(img_cv):
    texto = pytesseract.image_to_string(img_cv, lang="por")
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"R\s?,\s?", "R$", texto)  # junta R fragmentado
    return texto

# --- Função para extrair valores ---
def extrair_valores(texto):
    # regex robusta: R$ 2,57 ou 2,57
    valores = re.findall(r'(?:R\$?\s*)?\d+\s*,\s*\d{2}', texto)
    valores = [v.replace(" ", "").replace("R$", "R$ ") for v in valores]
    return valores

# --- Histórico ---
if "historico" not in st.session_state:
    st.session_state["historico"] = []

def adicionar_historico(pergunta, resposta):
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})
    if len(st.session_state["historico"]) > 5:
        st.session_state["historico"] = st.session_state["historico"][-5:]

# --- Layout ---
st.title("📊 IA Leitora de Planilhas e Imagens Avançada")
uploaded_file = st.file_uploader("📂 Envie planilha, PDF ou imagem", type=["xlsx", "csv", "png", "jpg", "jpeg", "pdf"])
pergunta = st.text_input("💬 Faça sua pergunta (ex: valor do frango inteiro)")

if st.button("🔍 Consultar") and uploaded_file and pergunta:
    resposta = ""
    
    # --- Se for imagem ---
    if uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
        img_cv = pre_processar_imagem(uploaded_file)
        texto = extrair_texto(img_cv)
        valores = extrair_valores(texto)
        if valores:
            resposta = f"💰 Valores encontrados: {', '.join(valores)}"
        else:
            resposta = "❌ Nenhum valor encontrado para este item."
    
    # --- Se for planilha ---
    elif uploaded_file.type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/csv"]:
        try:
            if uploaded_file.type == "text/csv":
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Fuzzy search por coluna
            colunas = df.columns.tolist()
            melhor_coluna, score = process.extractOne(pergunta, colunas, scorer=fuzz.partial_ratio)
            if score >= 60:
                df_filtrado = df[[melhor_coluna]]
                valores = []
                for val in df_filtrado[melhor_coluna]:
                    val_str = str(val)
                    match = re.search(r"\d+([.,]\d+)?", val_str)
                    if match:
                        v = match.group().replace(".", ",")
                        valores.append(f"R$ {v}")
                if valores:
                    resposta = f"💰 Valores encontrados: {', '.join(valores)}"
                else:
                    resposta = "❌ Nenhum valor encontrado para este item."
            else:
                resposta = "❌ Nenhum valor encontrado para este item."
        except Exception as e:
            resposta = f"❌ Erro ao processar planilha: {e}"
    
    adicionar_historico(pergunta, resposta)
    st.success(resposta)

# --- Histórico ---
st.subheader("📜 Histórico das últimas perguntas")
for item in reversed(st.session_state["historico"]):
    st.write(f"**Pergunta:** {item['pergunta']}")
    st.write(f"**Resposta:** {item['resposta']}")
    st.markdown("---")

# --- Botão limpar histórico ---
if st.button("🧹 Limpar histórico"):
    st.session_state["historico"] = []
    st.success("✅ Histórico limpo!")
