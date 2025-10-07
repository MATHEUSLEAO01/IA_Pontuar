import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI
from PyPDF2 import PdfReader
import base64

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora de Planilhas Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas Avançada - Pontuar Tech")
st.markdown("1️⃣ Envie uma planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "historico" not in st.session_state:
    st.session_state["historico"] = []

# -----------------------------
# Função para extrair conteúdo
# -----------------------------
def extrair_conteudo(uploaded_file):
    nome = uploaded_file.name.lower()
    tipo = uploaded_file.type

    # Caso 1: Excel
    if nome.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
        return df, None

    # Caso 2: PDF
    elif nome.endswith(".pdf"):
        try:
            reader = PdfReader(uploaded_file)
            texto = ""
            for page in reader.pages:
                texto += page.extract_text() or ""
            return None, texto.strip()
        except Exception:
            # fallback com GPT-4o
            pdf_bytes = uploaded_file.read()
            base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": "Extraia todo o texto deste PDF:"},
                        {"type": "image_url", "image_url": f"data:application/pdf;base64,{base64_pdf}"}
                    ]}
                ]
            )
            return None, response.choices[0].message.content

    # Caso 3: Imagem
    elif any(ext in tipo for ext in ["image/png", "image/jpeg", "image/jpg"]):
        img_bytes = uploaded_file.read()
        base64_image = base64.b64encode(img_bytes).decode("utf-8")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "Extraia todo o texto visível desta imagem (OCR):"},
                    {"type": "image_url", "image_url": f"data:image/png;base64,{base64_image}"}
                ]}
            ]
        )
        return None, response.choices[0].message.content

    else:
        return None, None

# -----------------------------
# Upload
# -----------------------------
uploaded_file = st.file_uploader(
    "📂 Envie uma planilha (.xlsx), PDF ou imagem (.png, .jpg)",
    type=["xlsx", "pdf", "png", "jpg", "jpeg"]
)

df = None
texto_extraido = None

if uploaded_file:
    df, texto_extraido = extrair_conteudo(uploaded_file)
    if df is not None:
        st.success("✅ Planilha Excel carregada!")
    elif texto_extraido:
        st.success("✅ Texto extraído com sucesso!")
    else:
        st.error("❌ Não foi possível processar o arquivo.")
        st.stop()

# -----------------------------
# Entrada do usuário
# -----------------------------
tipo_planilha = st.text_input("🗂 Qual o tipo de conteúdo? (ex.: vendas, gastos, notas fiscais...)")
pergunta = st.text_input("💬 Sua pergunta:")
tipo_resposta = st.radio("Tipo de resposta:", ["Resumo simples", "Detalhes adicionais"], index=0)

# -----------------------------
# Processamento com GPT
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
            "Organize sua resposta em duas partes: 'Resumo simples' e 'Detalhes adicionais'. "
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
# Visualizações
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
# Histórico
# -----------------------------
if st.session_state["historico"]:
    st.subheader("📜 Histórico de perguntas recentes")
    for h in reversed(st.session_state["historico"][-5:]):
        st.markdown(f"**Pergunta:** {h['pergunta']}  \n**Resposta:** {h['resposta']}")
