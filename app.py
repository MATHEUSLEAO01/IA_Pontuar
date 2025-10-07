import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import pytesseract
import re
import pandas as pd
import numpy as np
import cv2
from fuzzywuzzy import fuzz, process

# ---------------------------------------------------------
# CONFIGURAÇÃO GOOGLE VISION
# ---------------------------------------------------------
@st.cache_resource
def load_google_vision_client():
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["google_vision"]
        )
        return vision.ImageAnnotatorClient(credentials=credentials)
    except Exception as e:
        st.warning("⚠️ Falha ao carregar Google Vision, usando fallback Tesseract.")
        return None

vision_client = load_google_vision_client()

# ---------------------------------------------------------
# PRÉ-PROCESSAMENTO DE IMAGEM
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# OCR GOOGLE VISION + TESSERACT
# ---------------------------------------------------------
def extrair_texto_google_vision(image_file):
    try:
        content = image_file.read()
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations
        if texts:
            return texts[0].description
        else:
            return ""
    except Exception as e:
        st.warning("⚠️ Google Vision falhou. Usando Tesseract como alternativa.")
        image_file.seek(0)
        img_cv = pre_processar_imagem(image_file)
        return pytesseract.image_to_string(img_cv, lang="por")

# ---------------------------------------------------------
# EXTRAIR VALORES MONETÁRIOS
# ---------------------------------------------------------
def extrair_valores(texto):
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"R\s*\$", "R$", texto)
    valores = re.findall(r'R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}|\d{1,3}(?:\.\d{3})*,\d{2}', texto)
    valores = [v.replace(" ", "").replace("R$", "R$ ") for v in valores]
    final = []
    for v in valores:
        if not final or v != final[-1]:
            final.append(v)
    return final

# ---------------------------------------------------------
# HISTÓRICO DE PERGUNTAS
# ---------------------------------------------------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []

def adicionar_historico(pergunta, resposta):
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})
    if len(st.session_state["historico"]) > 5:
        st.session_state["historico"] = st.session_state["historico"][-5:]

# ---------------------------------------------------------
# INTERFACE STREAMLIT
# ---------------------------------------------------------
st.set_page_config(page_title="IA Leitora Pontuar", page_icon="📊")
st.title("📊 IA Leitora de Planilhas e Imagens Avançada - Pontuar Tech")

uploaded_file = st.file_uploader(
    "📂 Envie planilha, PDF ou imagem",
    type=["xlsx", "csv", "png", "jpg", "jpeg", "pdf"]
)

pergunta = st.text_input("💬 Faça sua pergunta (ex: valor do frango inteiro em GO)")

if st.button("🔍 Consultar") and uploaded_file and pergunta:
    resposta = ""

    # -------------------- IMAGEM --------------------
    if uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
        texto = extrair_texto_google_vision(uploaded_file)
        valores = extrair_valores(texto)
        if valores:
            resposta = f"💰 Valores encontrados: {', '.join(valores)}"
        else:
            resposta = "❌ Nenhum valor encontrado para este item."

    # -------------------- PLANILHA --------------------
    elif uploaded_file.type in [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    ]:
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

# ---------------------------------------------------------
# HISTÓRICO
# ---------------------------------------------------------
st.subheader("📜 Histórico das últimas perguntas")
for item in reversed(st.session_state["historico"]):
    st.write(f"**Pergunta:** {item['pergunta']}")
    st.write(f"**Resposta:** {item['resposta']}")
    st.markdown("---")

if st.button("🧹 Limpar histórico"):
    st.session_state["historico"] = []
    st.success("✅ Histórico limpo!")
