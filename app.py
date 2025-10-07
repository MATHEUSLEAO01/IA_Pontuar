import streamlit as st
from PIL import Image
import pytesseract
import re
import pandas as pd
import numpy as np
import cv2
from fuzzywuzzy import fuzz, process

# ----------------------------
# Função de pré-processamento da imagem
# ----------------------------
def pre_processar_imagem(img_file):
    img = Image.open(img_file).convert("RGB")
    img_cv = np.array(img)

    # Converte para grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    # Remove ruído
    gray = cv2.medianBlur(gray, 3)
    # Aumenta contraste
    gray = cv2.convertScaleAbs(gray, alpha=2, beta=0)
    # Binarização adaptativa (melhor que limiar fixo)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return thresh

# ----------------------------
# Função OCR para extrair texto
# ----------------------------
def extrair_texto(img_cv):
    texto = pytesseract.image_to_string(img_cv, lang="por")
    # Limpa quebras e múltiplos espaços
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = re.sub(r"\s+", " ", texto)
    # Junta R fragmentado
    texto = re.sub(r"R\s*\$", "R$", texto)
    return texto

# ----------------------------
# Função para extrair valores monetários
# ----------------------------
def extrair_valores(texto):
    # Regex para pegar valores: R$ 2,57 ou 2,57 ou R$ 1.234,56
    valores = re.findall(r'R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}|\d{1,3}(?:\.\d{3})*,\d{2}', texto)
    # Padroniza R$ XX,XX
    valores = [v.replace(" ", "").replace("R$", "R$ ") for v in valores]
    # Remove duplicatas consecutivas
    final = []
    for v in valores:
        if not final or v != final[-1]:
            final.append(v)
    return final

# ----------------------------
# Histórico de perguntas/respostas
# ----------------------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []

def adicionar_historico(pergunta, resposta):
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})
    # Mantém apenas últimos 5
    if len(st.session_state["historico"]) > 5:
        st.session_state["historico"] = st.session_state["historico"][-5:]

# ----------------------------
# Layout Streamlit
# ----------------------------
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

            # Fuzzy search entre colunas
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
