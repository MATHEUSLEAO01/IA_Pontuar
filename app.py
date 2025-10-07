import streamlit as st
from PIL import Image
import pytesseract
import re
import pandas as pd
import numpy as np
import cv2
from fuzzywuzzy import fuzz, process
import pdfplumber

# ============================================================
# 🧹 Pré-processamento de imagem para OCR
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
# OCR com Tesseract
# ============================================================
def extrair_texto_imagem(img_file):
    img_cv = pre_processar_imagem(img_file)
    texto = pytesseract.image_to_string(img_cv, lang="por", config="--psm 6")
    linhas = [linha.strip() for linha in texto.split("\n") if linha.strip()]
    return linhas

# ============================================================
# OCR de PDF (textos ou imagens dentro do PDF)
# ============================================================
def extrair_texto_pdf(pdf_file):
    linhas = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    for linha in texto.split("\n"):
                        linha = linha.strip()
                        if linha:
                            linhas.append(linha)
    except Exception as e:
        st.warning(f"Erro ao processar PDF: {e}")
    return linhas

# ============================================================
# Extrair valores monetários próximos de uma palavra em linhas
# ============================================================
def extrair_valor_por_item(linhas, item):
    resultados = []
    for linha in linhas:
        palavras = linha.split()
        match_item, score = process.extractOne(item, palavras, scorer=fuzz.partial_ratio)
        if score >= 70:
            # pegar valor mais próximo
            valores = re.findall(r'R?\$?\s*\d+[.,]\d+', linha)
            if valores:
                # assumir primeira palavra como categoria/estado
                categoria = palavras[0]
                resultados.append({"Categoria": categoria, "Valor": valores[0].replace(" ", "").replace("R$", "R$ ")})
    return resultados

# ============================================================
# Extrair valores de planilhas
# ============================================================
def extrair_valor_planilha(df, item):
    colunas = df.columns.tolist()
    melhor_coluna, score_item = process.extractOne(item, colunas, scorer=fuzz.partial_ratio)
    if score_item < 60:
        return None, None

    # tentar encontrar coluna de Estado
    estado_colunas = [c for c in colunas if "estado" in c.lower() or "uf" in c.lower()]
    estado_coluna = estado_colunas[0] if estado_colunas else None

    resultados = []
    for _, row in df.iterrows():
        estado = row[estado_coluna] if estado_coluna else f"Linha {_+1}"
        valor = str(row[melhor_coluna])
        match = re.search(r'\d+[.,]\d+', valor)
        if match:
            v = match.group().replace(".", ",")
            resultados.append({"Categoria": estado, "Valor": f"R$ {v}"})
    return resultados, melhor_coluna

# ============================================================
# 📜 Histórico
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
st.title("📊 IA Leitora Avançada - Pontuar Tech")
uploaded_file = st.file_uploader(
    "📂 Envie planilha, PDF ou imagem",
    type=["xlsx", "csv", "png", "jpg", "jpeg", "pdf"]
)
item = st.text_input("💬 Digite o item que deseja consultar (ex: Fígado)")

if st.button("🔍 Consultar") and uploaded_file and item:
    resposta = ""
    resultados = []

    # ===== Planilha =====
    if uploaded_file.type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/csv"]:
        try:
            df = pd.read_excel(uploaded_file) if uploaded_file.type.endswith("sheet") else pd.read_csv(uploaded_file)
            resultados, coluna = extrair_valor_planilha(df, item)
            if resultados:
                st.dataframe(pd.DataFrame(resultados))
                resposta = f"💰 Valores encontrados para '{item}' por categoria/estado."
            else:
                resposta = f"❌ Nenhum valor encontrado para '{item}' na planilha."
        except Exception as e:
            resposta = f"❌ Erro ao processar planilha: {e}"

    # ===== Imagem =====
    elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
        linhas = extrair_texto_imagem(uploaded_file)
        resultados = extrair_valor_por_item(linhas, item)
        if resultados:
            st.dataframe(pd.DataFrame(resultados))
            resposta = f"💰 Valores encontrados para '{item}' na imagem."
        else:
            resposta = f"❌ Nenhum valor encontrado para '{item}' na imagem."

    # ===== PDF =====
    elif uploaded_file.type == "application/pdf":
        linhas = extrair_texto_pdf(uploaded_file)
        resultados = extrair_valor_por_item(linhas, item)
        if resultados:
            st.dataframe(pd.DataFrame(resultados))
            resposta = f"💰 Valores encontrados para '{item}' no PDF."
        else:
            resposta = f"❌ Nenhum valor encontrado para '{item}' no PDF."

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
