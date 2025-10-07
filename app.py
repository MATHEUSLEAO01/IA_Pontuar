import streamlit as st
import pandas as pd
from openai import OpenAI
import pdfplumber
from PIL import Image
import pytesseract
import camelot
from transformers import pipeline
import re

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
st.markdown("1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

# OpenAI
client = OpenAI(api_key=st.secrets["general"]["OPENAI_API_KEY"])

# Hugging Face como fallback gratuito
hf_pipeline = pipeline("text-generation", model="bigscience/bloom-560m", device=-1)  # CPU

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

# -----------------------------
# Funções auxiliares
# -----------------------------
def extrair_texto_pdf(file):
    texto = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                texto += page.extract_text() or ""
    except:
        pass
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

def formatar_valores_resposta(texto):
    # Remove múltiplos espaços e quebras de linha
    texto = re.sub(r'\s+', ' ', texto)
    # Normaliza valores monetários
    texto = re.sub(r'R?\s?([\d]+,[\d]{2})', r'R$ \1', texto)
    return texto.strip()

# -----------------------------
# Processamento de arquivo
# -----------------------------
texto_extraido = None
df = None

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
        elif nome.endswith((".png", ".jpg", ".jpeg")):
            texto_extraido = extrair_texto_imagem(uploaded_file)
            st.success("✅ Texto extraído da imagem!")
    except Exception as e:
        st.error(f"❌ Erro ao processar: {e}")
        st.stop()

# -----------------------------
# Tipo de conteúdo
# -----------------------------
tipo_planilha = st.text_input("🗂 Qual o tipo de conteúdo? (ex.: vendas, gastos, notas fiscais...)")

# -----------------------------
# Caixa de pergunta
# -----------------------------
pergunta = st.text_input("💬 Sua pergunta:")

# -----------------------------
# Função para gerar resposta HF
# -----------------------------
def gerar_resposta_hf(conteudo):
    try:
        if len(conteudo) > 1000:  # limitar para não travar o modelo
            conteudo = conteudo[-1000:]
        saida = hf_pipeline(f"Responda detalhadamente: {conteudo}", max_new_tokens=256)
        return saida[0]["generated_text"]
    except:
        return "Não foi possível gerar resposta gratuita."

# -----------------------------
# Botão para limpar histórico
# -----------------------------
if st.button("🗑 Limpar histórico"):
    st.session_state["historico"] = []
    st.success("Histórico limpo!")

# -----------------------------
# Processamento
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido) and tipo_planilha:
    try:
        # Se for planilha, analisar colunas
        if df is not None:
            resumo = {
                "tipo_planilha": tipo_planilha,
                "colunas": list(df.columns),
                "amostra": df.head(10).to_dict(orient="records"),
            }
            conteudo = f"Resumo da planilha:\n{resumo}\nPergunta: {pergunta}"
        else:
            conteudo = f"Texto detectado:\n{texto_extraido}\nPergunta: {pergunta}"

        prompt_system = (
            "Você é um assistente especialista em análise de planilhas, PDFs e textos financeiros em português. "
            "Responda detalhadamente. Se não houver informação, diga 'Não encontrado'."
        )

        # Tenta OpenAI GPT-4o-mini
        try:
            resposta = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt_system},
                    {"role": "user", "content": conteudo}
                ]
            )
            texto_completo = resposta.choices[0].message.content.strip()
        except Exception:
            # Se falhar, usa Hugging Face
            texto_completo = gerar_resposta_hf(conteudo)

        # Formata valores para exibição legível
        texto_completo = formatar_valores_resposta(texto_completo)

        st.subheader("✅ Resposta Detalhada:")
        st.write(texto_completo)

        # Limita histórico a 3 perguntas recentes
        st.session_state["historico"].append({"pergunta": pergunta, "resposta": texto_completo})
        if len(st.session_state["historico"]) > 3:
            st.session_state["historico"] = st.session_state["historico"][-3:]

    except Exception as e:
        st.error(f"Erro: {e}")

# -----------------------------
# Histórico
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
