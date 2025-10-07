import pandas as pd
import streamlit as st
from openai import OpenAI
from PIL import Image
import pytesseract
import pdfplumber
import io

# Hugging Face para fallback gratuito
from transformers import pipeline, set_seed
import warnings
warnings.filterwarnings("ignore")

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
st.markdown("1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

# -----------------------------
# API Key OpenAI
# -----------------------------
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    openai_disponivel = True
except Exception:
    st.warning("⚠️ OpenAI não configurado. Fallback gratuito será usado.")
    openai_disponivel = False

# -----------------------------
# Sessão
# -----------------------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []

# -----------------------------
# Upload
# -----------------------------
uploaded_file = st.file_uploader(
    "📂 Envie planilha (.xlsx, PDF ou imagem)", 
    type=["xlsx", "pdf", "png", "jpg", "jpeg"]
)

# Limite de arquivo
if uploaded_file is not None and uploaded_file.size > 5*1024*1024:
    st.error("Arquivo muito grande! Limite de 5MB.")
    st.stop()

# -----------------------------
# Funções auxiliares
# -----------------------------
def extrair_excel(file):
    try:
        df = pd.read_excel(file)
        return df
    except:
        return None

def extrair_tabelas_pdf(file):
    try:
        import camelot
        tables = camelot.read_pdf(file, pages="all", flavor="stream")
        if tables and len(tables) > 0:
            df = tables[0].df
            df.columns = df.iloc[0]
            df = df[1:]
            return df
    except:
        return None

def extrair_texto_pdf(file):
    texto = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                texto += page.extract_text() or ""
    except:
        pass
    return texto

def extrair_texto_imagem(file):
    try:
        imagem = Image.open(file)
        return pytesseract.image_to_string(imagem, lang="por")
    except:
        return ""

# Limita tamanho do texto para economizar memória
def limitar_texto(texto, max_chars=2000):
    return texto[-max_chars:]

# -----------------------------
# Processar arquivo
# -----------------------------
df = None
texto_extraido = None

if uploaded_file:
    nome = uploaded_file.name.lower()
    if nome.endswith(".xlsx"):
        df = extrair_excel(uploaded_file)
        if df is not None:
            st.success("✅ Planilha Excel carregada!")
    elif nome.endswith(".pdf"):
        df = extrair_tabelas_pdf(uploaded_file)
        if df is not None:
            st.success("✅ Tabela detectada no PDF!")
        else:
            texto_extraido = extrair_texto_pdf(uploaded_file)
            st.info("📄 Texto extraído do PDF para análise.")
    elif nome.endswith((".png", ".jpg", ".jpeg")):
        texto_extraido = extrair_texto_imagem(uploaded_file)
        if texto_extraido:
            st.success("✅ Texto extraído da imagem!")

# -----------------------------
# Tipo de conteúdo
# -----------------------------
tipo_conteudo = st.text_input("🗂 Qual o tipo de conteúdo? (ex.: vendas, gastos, notas fiscais...)")

# -----------------------------
# Caixa de pergunta
# -----------------------------
pergunta = st.text_input("💬 Sua pergunta:")

# -----------------------------
# Função para gerar resposta
# -----------------------------
def gerar_resposta(conteudo, pergunta):
    prompt = f"Analise os dados abaixo e responda com clareza e precisão apenas em português.\nConteúdo:\n{conteudo}\nPergunta: {pergunta}\nResposta detalhada:"
    
    # Tenta OpenAI GPT
    if openai_disponivel:
        try:
            resposta = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Você é um assistente especialista em análise de dados financeiros e textos em português."},
                    {"role": "user", "content": prompt}
                ]
            )
            return resposta.choices[0].message.content.strip()
        except Exception:
            pass
    
    # Fallback gratuito Hugging Face
    try:
        generator = pipeline("text-generation", model="distilgpt2", device=-1)
        set_seed(42)
        result = generator(prompt, max_length=256, do_sample=True)
        return result[0]["generated_text"]
    except:
        return "Não foi possível gerar resposta gratuita."

# -----------------------------
# Botão Perguntar
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido) and tipo_conteudo and pergunta:
    if df is not None:
        resumo = {
            "tipo_conteudo": tipo_conteudo,
            "colunas": list(df.columns),
            "amostra": df.head(10).to_dict(orient="records")
        }
        conteudo = limitar_texto(str(resumo))
    else:
        conteudo = limitar_texto(texto_extraido)
    
    resposta_final = gerar_resposta(conteudo, pergunta)
    st.subheader("✅ Resposta Detalhada:")
    st.write(resposta_final)
    
    # Histórico limitado
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta_final})
    if len(st.session_state["historico"]) > 5:
        st.session_state["historico"] = st.session_state["historico"][-5:]

# -----------------------------
# Histórico
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
