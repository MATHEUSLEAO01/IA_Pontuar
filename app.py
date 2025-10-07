import streamlit as st
import pandas as pd
from openai import OpenAI
import pdfplumber
import camelot
from PyPDF2 import PdfReader
from PIL import Image
import io
import requests

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
st.markdown("1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

# OpenAI
client = OpenAI(api_key=st.secrets["general"]["OPENAI_API_KEY"])

# Sessão
if "historico" not in st.session_state:
    st.session_state["historico"] = []

# -----------------------------
# Upload de arquivo
# -----------------------------
uploaded_file = st.file_uploader("📂 Envie planilha (.xlsx), PDF ou imagem (.png, .jpg, .jpeg)", type=["xlsx","pdf","png","jpg","jpeg"])

# Funções auxiliares
def extrair_tabelas_pdf(file):
    try:
        tables = camelot.read_pdf(file, pages="all", flavor="stream")
        if tables and len(tables) > 0:
            df = tables[0].df
            df.columns = df.iloc[0]
            df = df[1:]
            return df
    except Exception:
        pass
    return None

def extrair_texto_pdf(file):
    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() or ""
    return texto

def extrair_texto_imagem(file):
    """Usa OpenAI para OCR (gratuito)"""
    # Converter imagem para bytes
    imagem = Image.open(file)
    buf = io.BytesIO()
    imagem.save(buf, format="PNG")
    buf.seek(0)
    
    # Fallback gratuito via OCR.Space API
    # OBS: pode usar qualquer serviço OCR gratuito se quiser
    payload = {"apikey": "helloworld", "language": "por"}
    files = {"file": buf}
    try:
        r = requests.post("https://api.ocr.space/parse/image", data=payload, files=files)
        result = r.json()
        texto = result.get("ParsedResults")[0]["ParsedText"]
        return texto
    except:
        return "Não foi possível extrair texto da imagem."

# -----------------------------
# Processamento
# -----------------------------
df = None
texto_extraido = None

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
        elif nome.endswith((".png","jpg","jpeg")):
            texto_extraido = extrair_texto_imagem(uploaded_file)
            st.success("✅ Texto extraído da imagem!")
    except Exception as e:
        st.error(f"❌ Erro ao processar: {e}")
        st.stop()

# Tipo de conteúdo
tipo_planilha = st.text_input("🗂 Qual o tipo de conteúdo? (ex.: vendas, gastos, notas fiscais...)")

# Pergunta
pergunta = st.text_input("💬 Sua pergunta:")

# -----------------------------
# Processamento da pergunta
# -----------------------------
def gerar_resposta_openai(conteudo):
    prompt = (
        "Você é um assistente especialista em análise de planilhas, PDFs e textos financeiros em português. "
        "Responda detalhadamente. Se não encontrar a informação, diga 'Não encontrado'."
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": conteudo}
            ]
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return None

def gerar_resposta_gratuita(conteudo):
    # Fallback gratuito usando API HuggingFace GPT2 simples
    try:
        r = requests.post(
            "https://api-inference.huggingface.co/models/tiiuae/falcon-7b-instruct",
            headers={"Authorization": "Bearer hf_demo"},
            json={"inputs": conteudo}
        )
        result = r.json()
        if isinstance(result, list):
            return result[0]["generated_text"]
        elif "error" in result:
            return "Não foi possível gerar resposta gratuita."
    except:
        return "Não foi possível gerar resposta gratuita."
    return "Não encontrado."

if st.button("🔍 Perguntar") and (df is not None or texto_extraido) and tipo_planilha and pergunta:
    if df is not None:
        resumo = {
            "tipo_planilha": tipo_planilha,
            "colunas": list(df.columns),
            "amostra": df.head(10).to_dict(orient="records"),
        }
        conteudo = f"Resumo da planilha:\n{resumo}\nPergunta: {pergunta}"
    else:
        conteudo = f"Texto detectado:\n{texto_extraido}\nPergunta: {pergunta}"
    
    resposta = gerar_resposta_openai(conteudo)
    if not resposta:
        resposta = gerar_resposta_gratuita(conteudo)
    
    st.subheader("✅ Resposta Detalhada:")
    st.write(resposta)
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})

# -----------------------------
# Histórico
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"][-5:]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
