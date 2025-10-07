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
        # Limpar quebras de linha e excesso de espaços
        texto_limpo = " ".join(texto_extraido.split())
        conteudo = limitar_texto(texto_limpo)
    
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
    
    # Botão para limpar histórico
    if st.button("🧹 Limpar histórico"):
        st.session_state["historico"] = []
        st.success("🗑 Histórico limpo com sucesso!")
