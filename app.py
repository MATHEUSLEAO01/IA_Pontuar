import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import pdfplumber
import camelot
from openai import OpenAI
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
st.markdown("1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

# OpenAI client
openai_key = st.secrets["general"]["OPENAI_API_KEY"]
client = OpenAI(api_key=openai_key)

# Hugging Face fallback (Flan-T5)
@st.cache_resource
def carregar_modelo_hf():
    tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-large")
    model = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-large")
    return pipeline("text2text-generation", model=model, tokenizer=tokenizer)

hf_pipeline = carregar_modelo_hf()

# -----------------------------
# Sessão
# -----------------------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []

# -----------------------------
# Upload
# -----------------------------
uploaded_file = st.file_uploader(
    "📂 Envie planilha (.xlsx), PDF ou imagem (.png, .jpg, .jpeg)",
    type=["xlsx", "pdf", "png", "jpg", "jpeg"]
)

df = None
texto_extraido = None

def extrair_texto_pdf(file):
    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() or ""
    return texto

def extrair_tabelas_pdf(file):
    try:
        tables = camelot.read_pdf(file, pages="all", flavor="stream")
        if tables and len(tables) > 0:
            df = tables[0].df
            df.columns = df.iloc[0]
            df = df[1:]
            return df
    except:
        return None
    return None

def extrair_texto_imagem(file):
    imagem = Image.open(file)
    return pytesseract.image_to_string(imagem, lang="por")

if uploaded_file:
    nome = uploaded_file.name.lower()
    try:
        if nome.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
            st.success("✅ Planilha Excel carregada!")
        elif nome.endswith(".pdf"):
            df = extrair_tabelas_pdf(uploaded_file)
            if df is not None:
                st.success("✅ Tabela detectada no PDF!")
            else:
                texto_extraido = extrair_texto_pdf(uploaded_file)
                st.info("📄 Nenhuma tabela detectada — texto extraído para análise.")
        elif nome.endswith((".png", ".jpg", ".jpeg")):
            texto_extraido = extrair_texto_imagem(uploaded_file)
            st.success("✅ Texto extraído da imagem!")
    except Exception as e:
        st.error(f"❌ Erro ao processar arquivo: {e}")
        st.stop()

# -----------------------------
# Tipo de conteúdo e pergunta
# -----------------------------
tipo_conteudo = st.text_input("🗂 Qual o tipo de conteúdo? (ex.: vendas, gastos, estoque...)")
pergunta = st.text_input("💬 Sua pergunta:")

# -----------------------------
# Função para gerar resposta detalhada
# -----------------------------
def gerar_resposta_openai(conteudo):
    try:
        prompt_system = (
            "Você é um assistente especialista em análise de planilhas, PDFs e textos financeiros em português. "
            "Forneça sempre uma resposta detalhada e precisa, sem resumo simples. "
            "Se não encontrar dados suficientes, diga 'Não encontrado'."
        )
        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": conteudo}
            ]
        )
        return resposta.choices[0].message.content.strip()
    except Exception as e:
        return None

def gerar_resposta_hf(texto):
    try:
        saida = hf_pipeline(f"Responda detalhadamente: {texto}", max_length=1024)
        return saida[0]["generated_text"]
    except:
        return None

# -----------------------------
# Processamento
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido) and tipo_conteudo and pergunta:
    conteudo = ""
    if df is not None:
        df_preview = df.head(10).to_dict(orient="records")
        conteudo = f"Tipo: {tipo_conteudo}\nDados:\n{df_preview}\nPergunta: {pergunta}"
    else:
        conteudo = f"Tipo: {tipo_conteudo}\nTexto extraído:\n{texto_extraido}\nPergunta: {pergunta}"

    # Tenta OpenAI
    resposta = gerar_resposta_openai(conteudo)
    if not resposta:
        # fallback HF gratuito
        resposta = gerar_resposta_hf(conteudo)
    
    if not resposta:
        resposta = "❌ Não foi possível gerar resposta gratuita."

    st.subheader("✅ Resposta Detalhada:")
    st.write(resposta)

    # Histórico
    st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta})

# -----------------------------
# Histórico
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"][-5:]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
