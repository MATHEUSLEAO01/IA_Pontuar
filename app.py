import streamlit as st
from PIL import Image
import pytesseract
import re
import pandas as pd
import numpy as np
import cv2
from fuzzywuzzy import fuzz, process

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
# 🧾 OCR com Tesseract
# ============================================================
def extrair_texto(img_file):
    img_cv = pre_processar_imagem(img_file)
    # Usar --psm 6 para detectar blocos de texto
    texto = pytesseract.image_to_string(img_cv, lang="por", config="--psm 6")
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"R\s*\$", "R$", texto)
    return texto.strip()

# ============================================================
# 💰 Extrair valores próximos à palavra usando fuzzy matching
# ============================================================
def extrair_valor_por_item_fuzzy(texto, item):
    # Separar em palavras para comparação
    palavras = texto.split()
    valores_encontrados = []
    for i, palavra in enumerate(palavras):
        # Fuzzy match da palavra
        score = fuzz.partial_ratio(item.lower(), palavra.lower())
        if score >= 70:  # Ajuste de precisão
            # Procurar números próximos (antes ou depois)
            vizinhos = palavras[max(i-3,0): i+4]  # 3 palavras antes e 3 depois
            for v in vizinhos:
                match = re.search(r'R?\$?\s*\d+[.,]\d+', v)
                if match:
                    valor = match.group().replace(" ", "").replace("R$", "R$ ")
                    valores_encontrados.append(valor)
    # Remover duplicados
    return list(dict.fromkeys(valores_encontrados))

# ============================================================
# 📜 Histórico de perguntas e respostas
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
        valores = extrair_valor_por_item_fuzzy(texto, item)
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
