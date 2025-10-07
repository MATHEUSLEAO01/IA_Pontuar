import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import re
from io import BytesIO
import pandas as pd
import cv2
import numpy as np

# --- Função de pré-processamento da imagem ---
def pre_processar_imagem(img_file):
    # abre imagem PIL
    img = Image.open(img_file).convert("RGB")
    # converte para array OpenCV
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    # converte para grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    # aplica CLAHE (melhora contraste local)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    # suavização leve
    blur = cv2.GaussianBlur(gray, (3,3), 0)
    # binarização Otsu
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # converte de volta para PIL
    pil_img = Image.fromarray(binary)
    return pil_img

# --- Função para extrair valores do texto OCR ---
def extrair_valores(texto):
    texto = re.sub(r"\s+", "", texto)
    # regex para capturar valores monetários (R$ 12,34 ou 12,34)
    valores = re.findall(r"R?\$?\s?(\d{1,3}(?:\.\d{3})*,\d{2})|(\d+,\d{2})", texto)
    # normaliza
    lista_valores = []
    for v in valores:
        v_str = v[0] if v[0] else v[1]
        v_str = v_str.replace(".", "")
        lista_valores.append(f"R$ {v_str}")
    return lista_valores

# --- Histórico de perguntas (máx. 3) ---
if "historico" not in st.session_state:
    st.session_state["historico"] = []

def adicionar_historico(pergunta, resposta):
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})
    if len(st.session_state["historico"]) > 3:
        st.session_state["historico"] = st.session_state["historico"][-3:]

# --- Layout Streamlit ---
st.title("📊 IA Leitora de Planilhas e Imagens Avançada")

uploaded_file = st.file_uploader("📂 Envie planilha, PDF ou imagem", type=["xlsx", "csv", "png", "jpg", "jpeg", "pdf"])
pergunta = st.text_input("💬 Faça sua pergunta (ex: valor do frango inteiro)")

if st.button("🔍 Consultar") and uploaded_file and pergunta:
    resposta = ""
    
    # --- Se for imagem ---
    if uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
        img = pre_processar_imagem(uploaded_file)
        texto = pytesseract.image_to_string(img, lang="por")
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
            
            # busca valores relacionados à pergunta
            mask = df.apply(lambda row: row.astype(str).str.contains(pergunta, case=False).any(), axis=1)
            df_filtrado = df[mask]
            
            if not df_filtrado.empty:
                valores = []
                for col in df_filtrado.columns:
                    for val in df_filtrado[col]:
                        val_str = str(val)
                        # pega números
                        match = re.match(r"\d+([.,]\d+)?", val_str)
                        if match:
                            val_str = val_str.replace(".", "").replace(",", ".")
                            valores.append(f"R$ {float(val_str):.2f}".replace(".", ","))
                resposta = f"💰 Valores encontrados: {', '.join(valores)}"
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
