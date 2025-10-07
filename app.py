import streamlit as st
from PIL import Image
import pytesseract
import re
import pandas as pd
import numpy as np
import cv2
from fuzzywuzzy import fuzz, process
from google.cloud import vision
from google.oauth2 import service_account
import io

# ============================================================
# 🔐 Autenticação com Google Vision
# ============================================================
client = None
try:
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["google_vision"]
    )
    client = vision.ImageAnnotatorClient(credentials=credentials)
    st.info("✅ Google Vision autenticado com sucesso!")
except Exception:
    st.warning("⚠️ Falha ao carregar Google Vision, usando fallback Tesseract.")
    client = None

# ============================================================
# 🧹 Função de pré-processamento da imagem
# ============================================================
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

# ============================================================
# 🧾 OCR - Usando Google Vision ou Tesseract
# ============================================================
def extrair_texto(img_file):
    try:
        if client:
            image_bytes = img_file.read()
            image = vision.Image(content=image_bytes)
            response = client.text_detection(image=image)
            texts = response.text_annotations
            texto = texts[0].description if texts else ""
        else:
            img_cv = pre_processar_imagem(img_file)
            texto = pytesseract.image_to_string(img_cv, lang="por")

        texto = texto.replace("\n", " ").replace("\r", " ")
        texto = re.sub(r"\s+", " ", texto)
        texto = re.sub(r"R\s*\$", "R$", texto)
        return texto.strip()
    except Exception as e:
        st.error(f"Erro ao processar OCR: {e}")
        return ""

# ============================================================
# 💰 Função para extrair valores monetários próximos de uma palavra
# ============================================================
def extrair_valor_por_item(texto, item):
    linhas = re.split(r'\.|\n', texto)
    valores_encontrados = []
    for linha in linhas:
        if item.lower() in linha.lower():
            valores = re.findall(r'R?\$?\s*\d+[.,]\d+', linha)
            valores_encontrados.extend([v.replace(" ", "").replace("R$", "R$ ") for v in valores])
    # Remover duplicados
    return list(dict.fromkeys(valores_encontrados))

# ============================================================
# 📜 Histórico de perguntas e respostas (máx. 3)
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
st.title("📊 IA Leitora de Planilhas e Imagens Avançada - Pontuar Tech")
uploaded_file = st.file_uploader(
    "📂 Envie planilha, PDF ou imagem",
    type=["xlsx", "csv", "png", "jpg", "jpeg", "pdf"]
)
item = st.text_input("💬 Digite o item que deseja consultar (ex: Fígado)")

if st.button("🔍 Consultar") and uploaded_file and item:
    resposta = ""

    # === Se for imagem ===
    if uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
        texto = extrair_texto(uploaded_file)
        valores = extrair_valor_por_item(texto, item)
        if valores:
            resposta = f"💰 Valores encontrados para '{item}': {', '.join(valores)}"
        else:
            resposta = f"❌ Nenhum valor encontrado para '{item}'."

    # === Se for planilha ===
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
            melhor_coluna, score = process.extractOne(item, colunas, scorer=fuzz.partial_ratio)
            if score >= 60:
                df_filtrado = df[[melhor_coluna]]
                valores = []
                for val in df_filtrado[melhor_coluna]:
                    val_str = str(val)
                    match = re.search(r'\d+[.,]\d+', val_str)
                    if match:
                        v = match.group().replace(".", ",")
                        valores.append(f"R$ {v}")
                if valores:
                    resposta = f"💰 Valores encontrados para '{item}': {', '.join(valores)}"
                else:
                    resposta = f"❌ Nenhum valor encontrado para '{item}'."
            else:
                resposta = f"❌ Nenhuma coluna próxima de '{item}' encontrada."
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
