import streamlit as st
from PIL import Image
import pytesseract
import re
import pandas as pd
import numpy as np
import cv2
from fuzzywuzzy import fuzz, process
from google.cloud import vision

# Inicializa cliente Google Vision
client = vision.ImageAnnotatorClient()

# ----------------------------
# Pré-processamento da imagem
# ----------------------------
def pre_processar_imagem(img_file):
    img = Image.open(img_file).convert("RGB")
    img_cv = np.array(img)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    gray = cv2.medianBlur(gray, 3)
    gray = cv2.convertScaleAbs(gray, alpha=2, beta=0)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return thresh

# ----------------------------
# OCR local
# ----------------------------
def extrair_texto_ocr_local(img_cv):
    texto = pytesseract.image_to_string(img_cv, lang="por")
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"R\s*\$", "R$", texto)
    return texto

# ----------------------------
# OCR Google Vision
# ----------------------------
def extrair_texto_google_vision(img_file):
    img = Image.open(img_file).convert("RGB")
    buffered = np.array(img)
    _, encoded_image = cv2.imencode('.png', buffered)
    content = encoded_image.tobytes()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texto = response.text_annotations[0].description if response.text_annotations else ""
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"R\s*\$", "R$", texto)
    return texto

# ----------------------------
# Extrair valores monetários
# ----------------------------
def extrair_valores(texto):
    valores = re.findall(r'R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}|\d{1,3}(?:\.\d{3})*,\d{2}', texto)
    valores = [v.replace(" ", "").replace("R$", "R$ ") for v in valores]
    final = []
    for v in valores:
        if not final or v != final[-1]:
            final.append(v)
    return final

# ----------------------------
# Histórico
# ----------------------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []

def adicionar_historico(pergunta, resposta):
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})
    if len(st.session_state["historico"]) > 5:
        st.session_state["historico"] = st.session_state["historico"][-5:]

# ----------------------------
# Layout Streamlit
# ----------------------------
st.title("📊 IA Leitora de Planilhas e Imagens Avançada (Híbrido)")
uploaded_file = st.file_uploader("📂 Envie planilha, PDF ou imagem", type=["xlsx", "csv", "png", "jpg", "jpeg", "pdf"])
pergunta = st.text_input("💬 Faça sua pergunta (ex: valor do frango inteiro)")

if st.button("🔍 Consultar") and uploaded_file and pergunta:
    resposta = ""

    # --- Se for imagem ---
    if uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
        try:
            # 1️⃣ OCR local
            img_cv = pre_processar_imagem(uploaded_file)
            texto = extrair_texto_ocr_local(img_cv)
            valores = extrair_valores(texto)

            # 2️⃣ Se OCR local não confiável, usa Google Vision
            if len(valores) < 2:  # critério de confiabilidade
                texto = extrair_texto_google_vision(uploaded_file)
                valores = extrair_valores(texto)

            if valores:
                resposta = f"💰 Valores encontrados: {', '.join(valores)}"
            else:
                resposta = "❌ Nenhum valor encontrado para este item."
        except Exception as e:
            resposta = f"❌ Erro ao processar imagem: {e}"

    # --- Se for planilha ---
    elif uploaded_file.type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/csv"]:
        try:
            if uploaded_file.type == "text/csv":
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

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

# ----------------------------
# Histórico
# ----------------------------
st.subheader("📜 Histórico das últimas perguntas")
for item in reversed(st.session_state["historico"]):
    st.write(f"**Pergunta:** {item['pergunta']}")
    st.write(f"**Resposta:** {item['resposta']}")
    st.markdown("---")

# ----------------------------
# Limpar histórico
# ----------------------------
if st.button("🧹 Limpar histórico"):
    st.session_state["historico"] = []
    st.success("✅ Histórico limpo!")
