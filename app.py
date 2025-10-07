import streamlit as st
import pandas as pd
from openai import OpenAI
import matplotlib.pyplot as plt
from PyPDF2 import PdfReader
from PIL import Image
import base64
import io

# -----------------------------
# CONFIGURAÇÃO INICIAL
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
st.markdown("1️⃣ Envie uma planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -----------------------------
# SESSÃO
# -----------------------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []

# -----------------------------
# UPLOAD
# -----------------------------
uploaded_file = st.file_uploader(
    "📂 Envie uma planilha (.xlsx), PDF ou imagem (.png, .jpg)",
    type=["xlsx", "pdf", "png", "jpg", "jpeg"]
)

# -----------------------------
# FUNÇÕES AUXILIARES
# -----------------------------
def detectar_colunas_avancado(df):
    keywords = ["gasto", "valor", "custo", "preço", "despesa", "total"]
    colunas_financeiras = []
    for col in df.columns:
        texto = str(col).lower()
        if any(k in texto for k in keywords) or pd.api.types.is_numeric_dtype(df[col]):
            colunas_financeiras.append(col)
    return list(set(colunas_financeiras)), df


def extrair_texto_arquivo(file, client):
    """Extrai texto de PDFs e imagens via GPT-4o (sem Tesseract)."""
    nome = file.name.lower()
    tipo = file.type

    # Caso Excel
    if nome.endswith(".xlsx"):
        return pd.read_excel(file)

    # Caso PDF (tentativa com PyPDF2, depois GPT)
    elif "pdf" in tipo or nome.endswith(".pdf"):
        try:
            reader = PdfReader(file)
            texto_pdf = ""
            for page in reader.pages:
                texto_pdf += page.extract_text() or ""
            if texto_pdf.strip():
                return texto_pdf
        except Exception:
            pass  # Vai tentar OCR via GPT

        file.seek(0)
        pdf_bytes = file.read()
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "Extraia todo o texto legível deste PDF em português:"},
                    {"type": "image_url", "image_url": f"data:application/pdf;base64,{base64_pdf}"}
                ]}
            ]
        )
        return response.choices[0].message.content

    # Caso imagem (OCR direto com GPT-4o)
    elif any(ext in tipo for ext in ["image/png", "image/jpeg", "image/jpg"]):
        img_bytes = file.read()
        base64_image = base64.b64encode(img_bytes).decode("utf-8")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "Extraia todo o texto desta imagem em português:"},
                    {"type": "image_url", "image_url": f"data:image/png;base64,{base64_image}"}
                ]}
            ]
        )
        return response.choices[0].message.content

    else:
        return None


# -----------------------------
# PROCESSAMENTO DE ARQUIVO
# -----------------------------
texto_extraido = None
df = None

if uploaded_file:
    resultado = extrair_texto_arquivo(uploaded_file, client)
    if isinstance(resultado, pd.DataFrame):
        df = resultado
        st.success("✅ Planilha Excel carregada!")
    elif isinstance(resultado, str):
        texto_extraido = resultado
        st.success("✅ Texto extraído com sucesso!")
        st.text_area("🧾 Texto detectado:", texto_extraido[:5000])
    else:
        st.error("❌ Tipo de arquivo não reconhecido ou vazio.")
        st.stop()

# -----------------------------
# TIPO DE CONTEÚDO
# -----------------------------
tipo_planilha = st.text_input("🗂 Qual o tipo de conteúdo? (ex.: vendas, gastos, notas fiscais...)")

# -----------------------------
# CAIXA DE PERGUNTA
# -----------------------------
pergunta = st.text_input("💬 Sua pergunta:")
tipo_resposta = st.radio("Tipo de resposta:", ["Resumo simples", "Detalhes adicionais"], index=0)

# -----------------------------
# PROCESSAMENTO DE PERGUNTA
# -----------------------------
if st.button("🔍 Perguntar") and (df is not None or texto_extraido) and tipo_planilha:
    try:
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
            "Analise os dados e responda com clareza e precisão. "
            "Organize a resposta em duas partes: 'Resumo simples' e 'Detalhes adicionais'. "
            "Se algo não for encontrado, diga 'Não encontrado'."
        )

        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": conteudo}
            ]
        )

        texto_completo = resposta.choices[0].message.content.strip()

        if "Resumo simples:" in texto_completo and "Detalhes adicionais:" in texto_completo:
            resumo_simples = texto_completo.split("Resumo simples:")[1].split("Detalhes adicionais:")[0].strip()
            detalhes = texto_completo.split("Detalhes adicionais:")[1].strip()
        else:
            resumo_simples = texto_completo
            detalhes = texto_completo

        resposta_final = resumo_simples if tipo_resposta == "Resumo simples" else detalhes

        st.subheader("✅ Resposta:")
        st.write(resposta_final)

        st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta_final})

    except Exception as e:
        st.error(f"Erro: {e}")

# -----------------------------
# VISUALIZAÇÕES
# -----------------------------
if df is not None:
    st.subheader("📊 Visualizações básicas")
    numeric_cols = df.select_dtypes(include="number").columns
    if len(numeric_cols) > 0:
        if st.button("📈 Gráfico de somas"):
            fig, ax = plt.subplots()
            df[numeric_cols].sum().plot(kind="bar", ax=ax, color="skyblue")
            st.pyplot(fig)
        if st.button("📉 Gráfico de médias"):
            fig, ax = plt.subplots()
            df[numeric_cols].mean().plot(kind="bar", ax=ax, color="lightgreen")
            st.pyplot(fig)
    else:
        st.info("Nenhuma coluna numérica detectada.")

# -----------------------------
# HISTÓRICO
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"][-5:]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
