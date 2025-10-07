import streamlit as st
import pandas as pd
from openai import OpenAI
from PyPDF2 import PdfReader
import base64
import time
import requests

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora Avançada", layout="wide")
st.title("📊 IA Leitora de Conteúdos com Fallback")
st.markdown(
    "1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta detalhada!"
)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "historico" not in st.session_state:
    st.session_state["historico"] = []

# -----------------------------
# Upload
# -----------------------------
uploaded_file = st.file_uploader(
    "📂 Envie planilha (.xlsx), PDF ou imagem (.png, .jpg)",
    type=["xlsx", "pdf", "png", "jpg", "jpeg"]
)

df = None
texto_extraido = None

# -----------------------------
# Funções auxiliares
# -----------------------------
def dividir_texto(texto, max_chars=3000):
    partes = []
    while len(texto) > max_chars:
        split_index = texto.rfind("\n", 0, max_chars)
        if split_index == -1:
            split_index = max_chars
        partes.append(texto[:split_index])
        texto = texto[split_index:]
    partes.append(texto)
    return partes

def extrair_conteudo(uploaded_file):
    nome = uploaded_file.name.lower()
    tipo = uploaded_file.type
    # Excel
    if nome.endswith(".xlsx"):
        return pd.read_excel(uploaded_file), None
    # PDF
    elif nome.endswith(".pdf"):
        try:
            reader = PdfReader(uploaded_file)
            texto = ""
            for page in reader.pages:
                texto += page.extract_text() or ""
            if texto.strip():
                return None, texto
            else:
                return None, "[PDF sem texto detectável]"
        except:
            return None, "[Erro ao ler PDF]"
    # Imagem
    elif any(ext in tipo for ext in ["image/png", "image/jpeg", "image/jpg"]):
        img_bytes = uploaded_file.read()
        base64_img = base64.b64encode(img_bytes).decode("utf-8")
        return None, f"[Imagem Base64 Preview] {base64_img[:500]}..."
    else:
        return None, None

if uploaded_file:
    df, texto_extraido = extrair_conteudo(uploaded_file)
    if df is not None:
        st.success("✅ Planilha Excel carregada!")
    elif texto_extraido:
        st.success("✅ Texto extraído (preview)!")
        st.text_area("🧾 Preview do texto:", texto_extraido[:2000])
    else:
        st.error("❌ Não foi possível processar o arquivo.")
        st.stop()

# -----------------------------
# Inputs do usuário
# -----------------------------
tipo_planilha = st.text_input("🗂 Tipo de conteúdo (ex.: vendas, gastos, notas fiscais...)")
pergunta = st.text_input("💬 Sua pergunta detalhada:")

# -----------------------------
# Função GPT OpenAI
# -----------------------------
def chamar_gpt_openai(conteudo, max_retries=3):
    for attempt in range(max_retries):
        try:
            resposta = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "Você é um assistente especialista em análise de planilhas, PDFs e textos financeiros em português. "
                        "Responda com clareza e detalhe todos os dados encontrados. "
                        "Se não encontrar algo, diga 'Não encontrado'."
                    )},
                    {"role": "user", "content": conteudo}
                ]
            )
            return resposta.choices[0].message.content.strip()
        except Exception as e:
            if any(x in str(e) for x in ["RateLimit", "quota", "insufficient_quota"]):
                if attempt < max_retries - 1:
                    st.warning("⚠️ Limite da API ou cota atingido. Tentando novamente em 5s...")
                    time.sleep(5)
                else:
                    raise e
            else:
                raise e

# -----------------------------
# Função GPT gratuita (Hugging Face)
# -----------------------------
def chamar_gpt_gratuito(conteudo):
    HF_TOKEN = st.secrets.get("HF_TOKEN")  # Hugging Face token no secrets
    API_URL = "https://api-inference.huggingface.co/models/bigscience/bloom-560m"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": conteudo, "parameters": {"max_new_tokens": 300}}
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        output = response.json()
        if isinstance(output, list) and "generated_text" in output[0]:
            return output[0]["generated_text"]
        else:
            return str(output)
    except Exception as e:
        return f"[Erro na IA gratuita]: {e}"

# -----------------------------
# Processamento da pergunta
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido) and tipo_planilha:
    try:
        if df is not None:
            conteudo = f"Planilha tipo: {tipo_planilha}\nColunas: {list(df.columns)}\nAmostra: {df.head(10).to_dict(orient='records')}\nPergunta: {pergunta}"
            try:
                resposta_final = chamar_gpt_openai(conteudo)
            except:
                st.warning("⚠️ OpenAI falhou, usando IA gratuita...")
                resposta_final = chamar_gpt_gratuito(conteudo)
        else:
            partes = dividir_texto(texto_extraido)
            respostas = []
            for p in partes:
                try:
                    respostas.append(chamar_gpt_openai(f"Texto:\n{p}\nPergunta: {pergunta}"))
                except:
                    st.warning("⚠️ OpenAI falhou, usando IA gratuita...")
                    respostas.append(chamar_gpt_gratuito(f"Texto:\n{p}\nPergunta: {pergunta}"))
            resposta_final = "\n\n".join(respostas)

        st.subheader("✅ Resposta detalhada:")
        st.write(resposta_final)
        st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta_final})

    except Exception as e:
        st.error(f"Erro geral: {e}")

# -----------------------------
# Histórico
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"][-5:]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
