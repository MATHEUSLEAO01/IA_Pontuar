import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI
from PyPDF2 import PdfReader
import base64
import time

# -----------------------------
# Inicialização
# -----------------------------
st.set_page_config(page_title="IA Leitora Avançada", layout="wide")
st.title("📊 IA Leitora de Planilhas/Texto Otimizada")
st.markdown("1️⃣ Envie planilha, PDF ou imagem → 2️⃣ Informe o tipo → 3️⃣ Faça uma pergunta → 4️⃣ Veja a resposta!")

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
# Função para dividir texto grande
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

# -----------------------------
# Função para extrair conteúdo
# -----------------------------
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
pergunta = st.text_input("💬 Sua pergunta:")
tipo_resposta = st.radio("Tipo de resposta:", ["Resumo simples", "Detalhes adicionais"], index=0)

# -----------------------------
# Função para chamar GPT com retry
# -----------------------------
def chamar_gpt(conteudo, max_retries=3):
    for attempt in range(max_retries):
        try:
            resposta = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "Você é um assistente especialista em análise de planilhas, PDFs e textos financeiros em português. "
                        "Responda com clareza, organize em 'Resumo simples' e 'Detalhes adicionais'. "
                        "Se não encontrar algo, diga 'Não encontrado'."
                    )},
                    {"role": "user", "content": conteudo}
                ]
            )
            return resposta.choices[0].message.content.strip()
        except Exception as e:
            # Detecta RateLimit pelo texto da exceção
            if "RateLimit" in str(e):
                if attempt < max_retries - 1:
                    st.warning("⚠️ Limite da API atingido. Tentando novamente em 5s...")
                    time.sleep(5)
                else:
                    st.error("❌ Limite da API atingido. Tente mais tarde.")
                    st.stop()
            else:
                st.error(f"Erro na API: {e}")
                st.stop()

# -----------------------------
# Processamento da pergunta
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
            resposta_final = chamar_gpt(conteudo)
        else:
            partes = dividir_texto(texto_extraido)
            respostas = []
            for p in partes:
                respostas.append(chamar_gpt(f"Texto:\n{p}\nPergunta: {pergunta}"))
            resposta_final = "\n\n".join(respostas)

        # Separar resumo simples e detalhes
        if "Resumo simples:" in resposta_final and "Detalhes adicionais:" in resposta_final:
            resumo_simples = resposta_final.split("Resumo simples:")[1].split("Detalhes adicionais:")[0].strip()
            detalhes = resposta_final.split("Detalhes adicionais:")[1].strip()
        else:
            resumo_simples = resposta_final
            detalhes = resposta_final

        st.subheader("✅ Resposta:")
        st.write(resumo_simples if tipo_resposta=="Resumo simples" else detalhes)
        st.session_state["historico"].append({"pergunta": pergunta, "resposta": resposta_final})

    except Exception as e:
        st.error(f"Erro: {e}")

# -----------------------------
# Visualizações
# -----------------------------
if df is not None:
    st.subheader("📊 Visualizações básicas")
    numeric_cols = df.select_dtypes(include="number").columns
    if numeric_cols.any():
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
