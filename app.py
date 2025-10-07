import streamlit as st
from PIL import Image
import cv2
import numpy as np
import pytesseract
import re
import pandas as pd

# --- Função de pré-processamento da imagem com OpenCV ---
def pre_processar_imagem(img_file):
    img = np.array(Image.open(img_file).convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)  # aumenta contraste
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY, 15, 10)
    kernel = np.ones((2,2), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)
    return Image.fromarray(dilated)

# --- Função para extrair valores do texto OCR ---
def extrair_valores(texto):
    # junta fragmentos quebrados tipo "2 ,57" → "2,57"
    texto = re.sub(r"(\d+)\s*,\s*(\d{2})", r"\1,\2", texto)
    # regex para capturar valores monetários
    valores = re.findall(r'R?\$?\d+,\d{2}', texto)
    # adiciona R$ e remove duplicados
    valores = [f"R$ {v.replace('R$', '')}" for v in set(valores)]
    return valores

# --- Histórico de perguntas (máx. 3) ---
if "historico" not in st.session_state:
    st.session_state["historico"] = []

def adicionar_historico(pergunta, resposta):
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})
    if len(st.session_state["historico"]) > 3:
        st.session_state["historico"] = st.session_state["historico"][-3:]

# --- Layout Streamlit ---
st.title("📊 IA Leitora de Planilhas e Imagens Avançada")
uploaded_file = st.file_uploader("📂 Envie planilha, PDF ou imagem", 
                                 type=["xlsx", "csv", "png", "jpg", "jpeg", "pdf"])
pergunta = st.text_input("💬 Faça sua pergunta (ex: valor do frango inteiro)")

if st.button("🔍 Consultar") and uploaded_file and pergunta:
    resposta = ""
    
    # --- Se for imagem ---
    if uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
        img = pre_processar_imagem(uploaded_file)
        # OCR com whitelist e PSM 6
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789,R$.,'
        texto = pytesseract.image_to_string(img, lang="por", config=custom_config)
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
                        if re.match(r"\d+([.,]\d+)?", val_str):
                            val_str = val_str.replace(".", ",")
                            valores.append(f"R$ {float(val_str.replace(',', '.')):.2f}".replace(".", ","))
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
