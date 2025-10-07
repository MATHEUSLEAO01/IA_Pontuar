import streamlit as st
import pandas as pd
from openai import OpenAI
import pdfplumber
import pytesseract
from PIL import Image
import camelot

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Conteúdos", layout="wide")
st.title("📊 IA Leitora de Planilhas, PDFs e Imagens")
st.markdown("1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

# Conexão OpenAI
client = OpenAI(api_key=st.secrets["general"]["OPENAI_API_KEY"])

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
        pass
    return None

def extrair_texto_imagem(file):
    imagem = Image.open(file)
    return pytesseract.image_to_string(imagem, lang="por")

# -----------------------------
# Processamento de arquivo
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
        elif nome.endswith((".png", ".jpg", ".jpeg")):
            texto_extraido = extrair_texto_imagem(uploaded_file)
            st.success("✅ Texto extraído da imagem!")
    except Exception as e:
        st.error(f"❌ Erro ao processar: {e}")
        st.stop()

# -----------------------------
# Tipo de conteúdo
# -----------------------------
tipo_conteudo = st.text_input("🗂 Qual o tipo de conteúdo? (ex.: vendas, gastos, notas fiscais...)")

# -----------------------------
# Pergunta
# -----------------------------
pergunta = st.text_input("💬 Sua pergunta:")

# -----------------------------
# Processamento e fallback gratuito
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido) and tipo_conteudo:
    try:
        # Preparar conteúdo para IA
        if df is not None:
            resumo = {
                "tipo_conteudo": tipo_conteudo,
                "colunas": list(df.columns),
                "amostra": df.head(10).to_dict(orient="records")
            }
            conteudo = f"Resumo da tabela:\n{resumo}\nPergunta: {pergunta}"
        else:
            conteudo = f"Texto detectado:\n{texto_extraido}\nPergunta: {pergunta}"

        prompt_system = (
            "Você é um assistente especialista em análise de dados financeiros, planilhas, PDFs e imagens em português. "
            "Responda com clareza, apenas 'Detalhes adicionais'. "
            "Se não souber, diga 'Não encontrado'."
        )

        # Tentar OpenAI
        try:
            resposta = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt_system},
                    {"role": "user", "content": conteudo}
                ]
            )
            resposta_final = resposta.choices[0].message.content.strip()
        except Exception as e:
            st.warning(f"⚠️ Falha na OpenAI: {e}\nUsando fallback gratuito.")
            # -----------------------------
            # Fallback gratuito usando modelo local ou GPT4Free
            # -----------------------------
            from transformers import pipeline
            generator = pipeline("text-generation", model="google/flan-t5-small")
            resposta_final = generator(f"{conteudo}", max_length=500)[0]["generated_text"]

        st.subheader("✅ Resposta detalhada:")
        st.write(resposta_final)
        st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta_final})

    except Exception as e:
        st.error(f"Erro: {e}")

# -----------------------------
# Histórico
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"][-5:]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
