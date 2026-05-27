import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# Inicialização inteligente do Firebase (Nuvem + Local)
if not firebase_admin._apps:
    if "firebase" in st.secrets:
        # Se estiver no Streamlit Cloud, lê os Secrets que colámos acima
        firebase_secrets = dict(st.secrets["firebase"])
        # Corrige as quebras de linha da chave privada automaticamente
        firebase_secrets["private_key"] = firebase_secrets["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(firebase_secrets)
    else:
        # Se estiver no teu PC local, continua a ler o ficheirocredentials.json da pasta
        cred = credentials.Certificate("credentials.json")
        
    firebase_admin.initialize_app(cred)

# Ligação à Base de Dados
db = firestore.client()
# ==========================================
# INSTALAÇÃO FORÇADA E AUTOMÁTICA DO GERADOR DE PDF
# ==========================================
try:
    from fpdf import FPDF
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fpdf"])
    os.execl(sys.executable, sys.executable, *sys.argv)

import streamlit as st
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import re
from datetime import datetime

# 1. Configuração da Página
st.set_page_config(page_title="JDFix - Oficina", layout="wide")

# 2. Ligação ao Firebase
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate('credentials.json')
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://jdfix-oficina-default-rtdb.europe-west1.firebasedatabase.app/'
        })
    except Exception as e:
        st.error(f"Erro ao carregar as credenciais: {e}")

# 3. Inicializar Estados
if "pagina" not in st.session_state:
    st.session_state.pagina = "🏠 Dashboard"
if "folha_selecionada" not in st.session_state:
    st.session_state.folha_selecionada = None
if "temp_pecas" not in st.session_state:
    st.session_state.temp_pecas = []
if "temp_horas" not in st.session_state:
    st.session_state.temp_horas = []

# ==========================================
# FUNÇÃO PARA DESENHAR O NOVO PDF (DESIGN JD FIX AZUL)
# ==========================================
def criar_pdf_oficina(matricula, veiculo, kms, cliente, pecas, horas, valor_hora, data_str, notas):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho - JD FIX
    pdf.set_font("Arial", 'B', 22)
    pdf.set_text_color(20, 30, 60) # Azul Escuro
    pdf.cell(0, 10, "JD FIX", ln=True)
    
    # Data de Emissão
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(100, 100, 100) # Cinza
    data_emissao = data_str.split(' ')[0]
    pdf.cell(0, 6, f"Data de Emissao: {data_emissao}", ln=True)
    pdf.ln(4)
    
    # Barra Azul Escura - Matrícula
    pdf.set_fill_color(20, 30, 50) # Azul Noite
    pdf.set_text_color(255, 255, 255) # Branco
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, f" FOLHA DE SERVICO - MATRICULA: {matricula}", fill=True, ln=True)
    pdf.ln(5)
    
    # Info do Carro e Cliente
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Cliente:", 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, cliente, 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Viatura:", 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, veiculo, 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "Quilometros:", 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, f"{kms} km", 0, 1)
    pdf.ln(6)
    
    # Tabela 1: Peças
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "Pecas / Materiais Substituidos:", ln=True)
    
    # Cabeçalho da Tabela Peças
    pdf.set_fill_color(240, 240, 240) # Cinza Claro
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(15, 6, "Qtd", border=1, align='C', fill=True)
    pdf.cell(40, 6, "Referencia", border=1, align='C', fill=True)
    pdf.cell(100, 6, "Designacao", border=1, align='L', fill=True)
    pdf.cell(35, 6, "Preco Final", border=1, align='R', fill=True, ln=True)
    
    # Linhas da Tabela Peças
    pdf.set_font("Arial", '', 9)
    total_pecas = 0.0
    
    if not pecas:
        pdf.cell(190, 6, "Nenhuma peca discriminada.", border=1, align='C', ln=True)
    else:
        for p in pecas:
            # Limpar acentos
            nome_p = p['nome'].replace('ç','c').replace('ã','a').replace('õ','o').replace('á','a').replace('é','e').replace('í','i')
            ref_p = p['referencia']
            
            pdf.cell(15, 6, str(p['quantidade']), border=1, align='C')
            pdf.cell(40, 6, ref_p[:20], border=1, align='C')
            pdf.cell(100, 6, nome_p[:50], border=1, align='L')
            pdf.cell(35, 6, f"{p['total']:.2f} EUR", border=1, align='R', ln=True)
            total_pecas += p['total']
            
    pdf.ln(6)
    
    # Tabela 2: Mão de Obra
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "Mao de Obra / Servicos Efetuados:", ln=True)
    
    pdf.set_font("Arial", '', 9)
    total_h = sum(h['horas'] for h in horas)
    custo_mo = total_h * valor_hora
    
    pdf.cell(155, 6, f"Mao de Obra (Total: {total_h:.1f}h)", border=1, align='L')
    pdf.cell(35, 6, f"{custo_mo:.2f} EUR", border=1, align='R', ln=True)
    
    # Anotações (Detalhes adicionais)
    pdf.ln(3)
    pdf.set_font("Arial", 'I', 8)
    notas_limpas = notas.replace('ç','c').replace('ã','a').replace('õ','o').replace('á','a').replace('é','e').replace('í','i')
    if not notas_limpas.strip():
        notas_limpas = "Sem anotacoes adicionais."
    pdf.cell(0, 5, f"Detalhes adic.: {notas_limpas}", ln=True)
    
    # Bloco de Totais no Canto Inferior Direito
    pdf.ln(10)
    
    # Criar um recuo para empurrar o bloco para a direita
    indent = 120 
    
    pdf.set_font("Arial", '', 9)
    pdf.set_x(indent)
    pdf.cell(35, 6, "Total Pecas:", 0, 0, 'R')
    pdf.cell(35, 6, f"{total_pecas:.2f} EUR", 0, 1, 'R')
    
    pdf.set_x(indent)
    pdf.cell(35, 6, "Total Mao de Obra:", 0, 0, 'R')
    pdf.cell(35, 6, f"{custo_mo:.2f} EUR", 0, 1, 'R')
    
    pdf.set_x(indent)
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 8, "TOTAL GERAL:", 0, 0, 'R', fill=True)
    pdf.cell(35, 8, f"{(total_pecas + custo_mo):.2f} EUR", 0, 1, 'R', fill=True)
    
    return pdf.output(dest='S').encode('latin-1')


# ==========================================
# DESCARREGAR DADOS DO FIREBASE
# ==========================================
dados_clientes = {}
dados_folhas = {}
dados_artigos = {}
try:
    dados_clientes = db.reference('clientes').get() or {}
    dados_folhas = db.reference('folhas_obra').get() or {}
    dados_artigos = db.reference('artigos').get() or {}
except Exception as e:
    st.error(f"Erro ao carregar dados do Firebase: {e}")

# ==========================================
# ALERTA DE DOWNLOAD
# ==========================================
if "pdf_pronto" in st.session_state and st.session_state.pdf_pronto:
    st.success("🎉 O teu Comprovativo PDF foi gerado com sucesso!")
    st.download_button(
        label="📥 Clica aqui para Descarregar o PDF (Pronto a Imprimir)",
        data=st.session_state.pdf_bytes,
        file_name=st.session_state.pdf_nome,
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )
    if st.button("❌ Fechar Aviso"):
        st.session_state.pdf_pronto = False
        st.rerun()
    st.write("---")

# ==========================================
# MENU LATERAL
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1995/1995470.png", width=70)
    st.title("JDFix Menu")
    st.write("---")
    escolha = st.radio(
        "Ir para:",
        ["🏠 Dashboard", "🚗 Clientes e Viaturas", "📋 Nova Folha de Obra", "📚 Histórico de Serviços", "📦 Artigos / Stock"],
        index=["🏠 Dashboard", "🚗 Clientes e Viaturas", "📋 Nova Folha de Obra", "📚 Histórico de Serviços", "📦 Artigos / Stock"].index(st.session_state.pagina)
    )
    st.session_state.pagina = escolha

# ==========================================
# PÁGINA 1: DASHBOARD PRINCIPAL
# ==========================================
if st.session_state.pagina == "🏠 Dashboard":
    st.title("🔧 JDFix - Dashboard Inicial")
    st.write("---")
    
    st.markdown("### ⚡ Acesso Rápido")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🔍 Pesquisa / Clientes", use_container_width=True):
            st.session_state.pagina = "🚗 Clientes e Viaturas"; st.rerun()
    with c2:
        if st.button("➕ Nova Folha de Obra", use_container_width=True, type="primary"):
            st.session_state.pagina = "📋 Nova Folha de Obra"; st.rerun()
    with c3:
        if st.button("📦 Artigos / Peças", use_container_width=True):
            st.session_state.pagina = "📦 Artigos / Stock"; st.rerun()
            
    st.write("---")
    st.markdown("### ⏳ Viaturas em Curso")
    
    folhas_abertas = {id_f: info for id_f, info in dados_folhas.items() if info.get('estado') == 'Aberto'}
            
    if folhas_abertas:
        colunas_v = st.columns(4)
        for i, (id_folha, info) in enumerate(folhas_abertas.items()):
            col_atual = colunas_v[i % 4]
            matricula_botao = info.get('matricula', 'S/M')
            veiculo_b = info.get('veiculo', 'Desconhecido')
            
            with col_atual:
                if st.button(f"🚘 {matricula_botao}\n\n{veiculo_b}", key=f"btn_{id_folha}", use_container_width=True):
                    st.session_state.folha_selecionada = id_folha
                    
        if st.session_state.folha_selecionada and st.session_state.folha_selecionada in folhas_abertas:
            f_id = st.session_state.folha_selecionada
            f_info = folhas_abertas[f_id]
            st.write("---")
            st.markdown(f"### 📋 Detalhes do Trabalho - {f_info.get('matricula')}")
            
            det_c1, det_c2 = st.columns(2)
            with det_c1:
                st.write(f"**Cliente:** {f_info.get('cliente')}")
                st.write(f"**Viatura:** {f_info.get('veiculo')} ({f_info.get('kms', 0)} Kms)")
                st.write(f"**Data de Entrada:** {f_info.get('data_entrada')}")
                st.write(f"**Preço Mão de Obra:** {f_info.get('valor_hora', 0.0):.2f} € / Hora")
            with det_c2:
                pecas_f = f_info.get('pecas', [])
                horas_f = f_info.get('horas', [])
                st.write(f"Peças adicionadas: {len(pecas_f)}")
                st.write(f"Registos de horas: {len(horas_f)}")
                
                if st.button("Ir para Edição / Concluir desta Folha", use_container_width=True):
                    st.session_state.temp_pecas = pecas_f if isinstance(pecas_f, list) else list(pecas_f.values())
                    st.session_state.temp_horas = horas_f if isinstance(horas_f, list) else list(horas_f.values())
                    st.session_state.id_folha_editar = f_id
                    st.session_state.pagina = "📋 Nova Folha de Obra"
                    st.rerun()
    else:
        st.info("Excelente! Não há nenhuma viatura em curso neste momento. Oficina vazia! 🎉")

# ==========================================
# PÁGINA 2: CLIENTES E VIATURAS
# ==========================================
elif st.session_state.pagina == "🚗 Clientes e Viaturas":
    st.title("🚗 Gestão de Clientes e Viaturas")
    st.write("---")
    clientes_existentes = {info.get('nome','').strip(): info.get('telemovel','') for info in dados_clientes.values() if info.get('nome')}
    col1, col2 = st.columns([1, 1.8])
    with col1:
        st.markdown("### 📝 Novo Registo")
        lista_nomes_completos = ["-- Novo Cliente --"] + sorted(list(clientes_existentes.keys()))
        cliente_selecionado = st.selectbox("Cliente Já Existe?", lista_nomes_completos)
        nome = cliente_selecionado if cliente_selecionado != "-- Novo Cliente --" else st.text_input("Nome do Novo Cliente")
        telemovel = clientes_existentes[cliente_selecionado] if cliente_selecionado != "-- Novo Cliente --" else st.text_input("Contacto Telefónico")
        matricula = st.text_input("Matrícula").upper().strip()
        marca_modelo = st.text_input("Marca / Modelo")
        if st.button("Gravar Cliente", use_container_width=True):
            if nome and matricula and marca_modelo:
                mat_l = re.sub(r'[^A-Z0-9]', '', matricula)
                db.reference(f'clientes/{mat_l}').set({'nome': nome, 'telemovel': telemovel, 'matricula_original': matricula, 'veiculo': marca_modelo})
                st.success("Gravado!"); st.rerun()
    with col2:
        st.markdown("### 🔍 Lista")
        termo = st.text_input("Pesquisar...").lower().strip()
        if dados_clientes:
            lt = [{"ID_Chave": k, "Matrícula": v.get('matricula_original', k), "Cliente": v.get('nome',''), "Telemóvel": v.get('telemovel',''), "Veículo": v.get('veiculo','')} for k,v in dados_clientes.items() if not termo or termo in v.get('nome','').lower() or termo in v.get('matricula_original','').lower()]
            if lt:
                ev = st.dataframe(lt, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
                sel = ev.get("selection", {}).get("rows", [])
                if sel and st.button("🗑️ Apagar Registo", use_container_width=True):
                    db.reference(f"clientes/{lt[sel[0]]['ID_Chave']}").delete()
                    st.success("Apagado!"); st.rerun()

# ==========================================
# PÁGINA 3: NOVA FOLHA DE OBRA
# ==========================================
elif st.session_state.pagina == "📋 Nova Folha de Obra":
    modo_edicao = "id_folha_editar" in st.session_state and st.session_state.id_folha_editar is not None
    
    if modo_edicao:
        st.title("📋 Editar / Concluir Folha de Obra")
        f_id = st.session_state.id_folha_editar
        info_f = dados_folhas.get(f_id, {})
        matricula_escolhida = info_f.get('matricula')
        cliente_nome = info_f.get('cliente')
        veiculo_nome = info_f.get('veiculo')
    else:
        st.title("📋 Abertura de Folha de Obra")
        f_id = None
        info_f = {}
        
    st.write("---")
    
    if not dados_clientes and not modo_edicao:
        st.warning("⚠️ Precisas de registar pelo menos uma viatura antes de abrir uma Folha de Obra!")
    else:
        if not modo_edicao:
            lista_matriculas = sorted([info.get('matricula_original') for info in dados_clientes.values() if info.get('matricula_original')])
            matricula_escolhida = st.selectbox("Escolha a Matrícula do Veículo:", lista_matriculas)
            cliente_nome, veiculo_nome = "", ""
            for info in dados_clientes.values():
                if info.get('matricula_original') == matricula_escolhida:
                    cliente_nome = info.get('nome')
                    veiculo_nome = info.get('veiculo')
                    break
                    
        st.warning(f"🚘 **Viatura:** {matricula_escolhida}  |  **Cliente:** {cliente_nome}  |  **Modelo:** {veiculo_nome}")
        
        st.markdown("### 💶 Regras e Info do Carro")
        rh1, rh2 = st.columns(2)
        with rh1:
            kms_viatura = st.number_input("Quilómetros (Kms) da Viatura", min_value=0, value=info_f.get('kms', 0), step=1000)
        with rh2:
            valor_hora_aplicado = st.number_input("Preço da Mão de Obra por Hora (€):", min_value=0.0, value=float(info_f.get('valor_hora', 30.0)), step=1.0, format="%.2f")
            
        # 🆕 CAIXA DE ANOTAÇÕES
        st.markdown("### 📝 Anotações do Veículo / Serviço")
        notas_pdf = st.text_area("Escreva aqui os detalhes adicionais que quer que apareçam no PDF (Opcional):", value=info_f.get('notas', ''))
        st.write("---")
        
        # 📦 GESTÃO DE PEÇAS ADICIONADAS
        st.markdown("### 🛠️ Adicionar Peças")
        col_p1, col_p2, col_p3, col_p4 = st.columns([1.5, 2, 0.8, 1])
        with col_p1: ref_pesquisa_stock = st.text_input("Digitar Referência (Stock)").upper().strip()
            
        nome_auto = ""; preco_auto = 0.0
        if ref_pesquisa_stock:
            ref_limpa = re.sub(r'[^A-Z0-9-]', '', ref_pesquisa_stock)
            artigo_encontrado = dados_artigos.get(ref_limpa)
            if not artigo_encontrado:
                for info_art in dados_artigos.values():
                    if ref_pesquisa_stock in info_art.get('equivalentes', '').upper():
                        artigo_encontrado = info_art; break
            if artigo_encontrado:
                nome_auto = artigo_encontrado.get('nome', '')
                preco_auto = float(artigo_encontrado.get('preco', 0.0))
                st.caption(f"✨ Encontrado no Stock! (Qtd: {artigo_encontrado.get('quantidade')})")
        
        with col_p2: nome_peca_input = st.text_input("Descrição da Peça", value=nome_auto)
        with col_p3: qtd_peca_input = st.number_input("Qtd", min_value=1, value=1, step=1)
        with col_p4: preco_peca_input = st.number_input("Preço Unit. (€)", min_value=0.0, value=preco_auto, step=0.50, format="%.2f")
            
        if st.button("➕ Adicionar Peça", use_container_width=True):
            if not nome_peca_input: st.error("Escreve o nome da peça!")
            else:
                st.session_state.temp_pecas.append({"referencia": ref_pesquisa_stock if ref_pesquisa_stock else "S/REF", "nome": nome_peca_input, "quantidade": int(qtd_peca_input), "preco": float(preco_peca_input), "total": int(qtd_peca_input) * float(preco_peca_input)})
                st.rerun()
                
        if st.session_state.temp_pecas:
            tabela_pecas_visivel = [{"Referência": p["referencia"], "Descrição": p["nome"], "Qtd": p["quantidade"], "Preço (€)": f"{p['preco']:.2f} €", "Total (€)": f"{p['total']:.2f} €"} for p in st.session_state.temp_pecas]
            evt_sel_p = st.dataframe(tabela_pecas_visivel, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun", key="tab_pecas_obra")
            sel_p_rows = evt_sel_p.get("selection", {}).get("rows", [])
            if sel_p_rows:
                idx_p = sel_p_rows[0]; peca_sel = st.session_state.temp_pecas[idx_p]
                st.warning(f"A editar: **{peca_sel['nome']}**")
                ec1, ec2, ec3, ec4 = st.columns([2, 1, 1, 1])
                with ec1: novo_nome = st.text_input("Novo Nome", peca_sel['nome'], key=f"ed_n_{idx_p}")
                with ec2: nova_qtd = st.number_input("Nova Qtd", min_value=1, value=peca_sel['quantidade'], key=f"ed_q_{idx_p}")
                with ec3: novo_preco = st.number_input("Novo Preço", min_value=0.0, value=float(peca_sel['preco']), step=0.50, key=f"ed_p_{idx_p}")
                with ec4:
                    st.write("")
                    if st.button("💾 Guardar", use_container_width=True, key=f"sv_{idx_p}"):
                        st.session_state.temp_pecas[idx_p].update({"nome": novo_nome, "quantidade": int(nova_qtd), "preco": float(novo_preco), "total": int(nova_qtd) * float(novo_preco)})
                        st.rerun()
                if st.button(f"🗑️ Remover '{peca_sel['nome']}'", type="primary", use_container_width=True):
                    st.session_state.temp_pecas.pop(idx_p); st.rerun()
                
        st.write("---")
        
        # ⏱️ GESTÃO DE HORAS DE MÃO DE OBRA
        st.markdown("### ⏱️ Registo de Mão de Obra")
        col_h1, col_h2 = st.columns(2)
        with col_h1: data_horas = st.date_input("Dia do Trabalho", datetime.now())
        with col_h2: qtd_horas = st.number_input("Número de Horas Gastas", min_value=0.5, value=1.0, step=0.5)
            
        if st.button("➕ Adicionar Horas", use_container_width=True):
            st.session_state.temp_horas.append({"data": data_horas.strftime("%d/%m/%Y"), "horas": float(qtd_horas)})
            st.rerun()
            
        if st.session_state.temp_horas:
            tabela_horas_visivel = [{"Data do Trabalho": h["data"], "Horas Gastas": f"{h['horas']} Horas"} for h in st.session_state.temp_horas]
            evt_sel_h = st.dataframe(tabela_horas_visivel, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun", key="tab_horas_obra")
            sel_h_rows = evt_sel_h.get("selection", {}).get("rows", [])
            if sel_h_rows:
                idx_h = sel_h_rows[0]; hora_sel = st.session_state.temp_horas[idx_h]
                st.warning(f"A editar registo do dia: **{hora_sel['data']}**")
                eh1, eh2, eh3 = st.columns([1.5, 1.5, 1])
                with eh1:
                    try: data_atual_parse = datetime.strptime(hora_sel['data'], "%d/%m/%Y").date()
                    except: data_atual_parse = datetime.now().date()
                    nova_data_ed = st.date_input("Corrigir Data", data_atual_parse, key=f"ed_hd_{idx_h}")
                with eh2: novas_horas_ed = st.number_input("Corrigir Horas", min_value=0.5, value=float(hora_sel['horas']), step=0.5, key=f"ed_hh_{idx_h}")
                with eh3:
                    st.write("")
                    if st.button("💾 Guardar", use_container_width=True, key=f"sv_h_{idx_h}"):
                        st.session_state.temp_horas[idx_h].update({"data": nova_data_ed.strftime("%d/%m/%Y"), "horas": float(novas_horas_ed)})
                        st.rerun()
                if st.button(f"🗑️ Remover", type="primary", use_container_width=True):
                    st.session_state.temp_horas.pop(idx_h); st.rerun()
                
        st.write("---")
        
        # 💾 PAINEL DE BOTÕES DE FINALIZAÇÃO (AGORA COM 4 REGRAS)
        st.markdown("### 💾 Finalizar Operação")
        
        # Criamos 4 colunas em vez de 3
        b1, b2, b3, b4 = st.columns(4)
        
        dados_salvar = {
            'matricula': matricula_escolhida,
            'cliente': cliente_nome,
            'veiculo': veiculo_nome,
            'kms': int(kms_viatura),
            'notas': notas_pdf,
            'pecas': st.session_state.temp_pecas,
            'horas': st.session_state.temp_horas,
            'valor_hora': float(valor_hora_aplicado),
            'data_entrada': info_f.get('data_entrada', datetime.now().strftime("%d/%m/%Y %H:%M")) if modo_edicao else datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        # Botão 1: Apenas Gravar e Manter Aberta
        with b1:
            if st.button("💾 Guardar", use_container_width=True):
                try:
                    dados_salvar['estado'] = 'Aberto'
                    ref_f = db.reference('folhas_obra')
                    if modo_edicao: ref_f.child(f_id).set(dados_salvar)
                    else: ref_f.push().set(dados_salvar)
                    
                    st.success("Guardado na Oficina!")
                    st.session_state.temp_pecas = []; st.session_state.temp_horas = []
                    if "id_folha_editar" in st.session_state: st.session_state.id_folha_editar = None
                    st.session_state.pagina = "🏠 Dashboard"; st.rerun()
                except Exception as e: st.error(f"Erro: {e}")
                
        # Botão 2: Gravar, Manter Aberta E SACAR PDF (Orçamento)
        with b2:
            if st.button("🖨️ Guardar + PDF", use_container_width=True):
                try:
                    dados_salvar['estado'] = 'Aberto'
                    ref_f = db.reference('folhas_obra')
                    if modo_edicao: ref_f.child(f_id).set(dados_salvar)
                    else: ref_f.push().set(dados_salvar)
                    
                    pdf_final = criar_pdf_oficina(
                        matricula=matricula_escolhida,
                        veiculo=veiculo_nome,
                        kms=int(kms_viatura),
                        cliente=cliente_nome,
                        pecas=st.session_state.temp_pecas,
                        horas=st.session_state.temp_horas,
                        valor_hora=float(valor_hora_aplicado),
                        data_str=datetime.now().strftime("%d/%m/%Y %H:%M"),
                        notas=notas_pdf
                    )
                    
                    st.session_state.pdf_bytes = pdf_final
                    st.session_state.pdf_nome = f"Orcamento_{matricula_escolhida.replace('-','')}.pdf"
                    st.session_state.pdf_pronto = True
                    
                    st.session_state.temp_pecas = []; st.session_state.temp_horas = []
                    if "id_folha_editar" in st.session_state: st.session_state.id_folha_editar = None
                    st.session_state.pagina = "🏠 Dashboard"
                    st.rerun()
                except Exception as e: st.error(f"Erro a gerar o PDF: {e}")

        # Botão 3: Fechar Obra Sem PDF
        with b3:
            if st.button("✅ Fechar Obra", use_container_width=True, type="primary"):
                try:
                    dados_salvar['estado'] = 'Concluído'
                    dados_salvar['data_conclusao'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    ref_f = db.reference('folhas_obra')
                    if modo_edicao: ref_f.child(f_id).set(dados_salvar)
                    else: ref_f.push().set(dados_salvar)
                    
                    st.success("Enviado para o histórico!")
                    st.session_state.temp_pecas = []; st.session_state.temp_horas = []
                    if "id_folha_editar" in st.session_state: st.session_state.id_folha_editar = None
                    st.session_state.pagina = "🏠 Dashboard"; st.rerun()
                except Exception as e: st.error(f"Erro: {e}")
                
        # Botão 4: Fechar Obra e Gerar Fatura PDF
        with b4:
            if st.button("🖨️ Fechar Obra + PDF", use_container_width=True, type="primary"):
                try:
                    dados_salvar['estado'] = 'Concluído'
                    dados_salvar['data_conclusao'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    ref_f = db.reference('folhas_obra')
                    if modo_edicao: ref_f.child(f_id).set(dados_salvar)
                    else: ref_f.push().set(dados_salvar)
                    
                    pdf_final = criar_pdf_oficina(
                        matricula=matricula_escolhida,
                        veiculo=veiculo_nome,
                        kms=int(kms_viatura),
                        cliente=cliente_nome,
                        pecas=st.session_state.temp_pecas,
                        horas=st.session_state.temp_horas,
                        valor_hora=float(valor_hora_aplicado),
                        data_str=dados_salvar['data_conclusao'],
                        notas=notas_pdf
                    )
                    
                    st.session_state.pdf_bytes = pdf_final
                    st.session_state.pdf_nome = f"Fatura_{matricula_escolhida.replace('-','')}.pdf"
                    st.session_state.pdf_pronto = True
                    
                    st.session_state.temp_pecas = []; st.session_state.temp_horas = []
                    if "id_folha_editar" in st.session_state: st.session_state.id_folha_editar = None
                    st.session_state.pagina = "🏠 Dashboard"
                    st.rerun()
                except Exception as e: st.error(f"Erro a gerar o PDF: {e}")

# ==========================================
# PÁGINA 4: HISTÓRICO DE SERVIÇOS
# ==========================================
elif st.session_state.pagina == "📚 Histórico de Serviços":
    st.title("📚 Histórico de Serviços Concluídos")
    st.write("---")
    
    folhas_concluidas = []
    for id_f, info in dados_folhas.items():
        if info.get('estado') == 'Concluído':
            info['id_sistema'] = id_f
            folhas_concluidas.append(info)
            
    folhas_concluidas.reverse()
    
    pesquisa_mat = st.text_input("Insira a matrícula...").upper().strip()
    if pesquisa_mat:
        pesquisa_limpa = re.sub(r'[^A-Z0-9]', '', pesquisa_mat)
        historico_carro = [f for f in folhas_concluidas if re.sub(r'[^A-Z0-9]', '', f.get('matricula', '')) == pesquisa_limpa]
        if historico_carro:
            for f in historico_carro:
                with st.expander(f"🗓️ {f.get('data_conclusao', 'S/D')} | {f.get('veiculo')} - {f.get('cliente')}"):
                    st.write(f"**Entrada:** {f.get('data_entrada')} | **Saída:** {f.get('data_conclusao')}")
                    st.write(f"**Mão de Obra:** {f.get('valor_hora', 0.0)} €/Hora | **Kms:** {f.get('kms', 0)}")
                    st.write(f"**Anotações:** {f.get('notas', 'Nenhuma')}")
                    st.write("**Peças Utilizadas:**")
                    st.write(f.get('pecas', []))
                    st.write("**Horas Gastas:**")
                    st.write(f.get('horas', []))
                    
                    st.write("---")
                    c_exp1, c_exp2 = st.columns(2)
                    with c_exp1:
                        if st.button("✏️ Reabrir Folha", key=f"re_{f['id_sistema']}", use_container_width=True):
                            st.session_state.temp_pecas = f.get('pecas', []) if isinstance(f.get('pecas', []), list) else list(f.get('pecas', {}).values())
                            st.session_state.temp_horas = f.get('horas', []) if isinstance(f.get('horas', []), list) else list(f.get('horas', {}).values())
                            st.session_state.id_folha_editar = f['id_sistema']
                            st.session_state.pagina = "📋 Nova Folha de Obra"
                            st.rerun()
                    with c_exp2:
                        if st.button("🗑️ Apagar Registo", key=f"del_{f['id_sistema']}", type="primary", use_container_width=True):
                            db.reference(f"folhas_obra/{f['id_sistema']}").delete()
                            st.rerun()
        else: st.warning("Nenhum serviço concluído encontrado para esta matrícula.")

    st.write("---")
    st.markdown("### ⏱️ Últimas Folhas Concluídas na Oficina")
    
    if folhas_concluidas:
        # Duas listas para podermos mostrar uma sem ID e usar a outra para saber qual ID foi clicado!
        lista_ultimas_visivel = []
        lista_ids_escondidos = []
        
        for f in folhas_concluidas[:15]:
            qtd_pecas = len(f.get('pecas', []))
            total_h = sum(h.get('horas', 0) for h in f.get('horas', []))
            
            lista_ids_escondidos.append(f.get('id_sistema'))
            
            # Repara que não há "ID_Chave" nesta lista visível!
            lista_ultimas_visivel.append({
                "Conclusão": f.get('data_conclusao', ''),
                "Matrícula": f.get('matricula', ''),
                "Veículo": f.get('veiculo', ''),
                "Resumo": f"{qtd_pecas} peças | {total_h}h mão obra"
            })
            
        st.write("📝 **Selecione uma linha na tabela para Reabrir ou Apagar o registo:**")
        evt_sel_hist = st.dataframe(lista_ultimas_visivel, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun", key="tab_historico")
        
        sel_hist_rows = evt_sel_hist.get("selection", {}).get("rows", [])
        if sel_hist_rows:
            idx_h = sel_hist_rows[0]
            hist_sel = lista_ultimas_visivel[idx_h]
            id_f_hist = lista_ids_escondidos[idx_h] # Magia! Vamos buscar o ID secreto à outra lista
            info_f_hist = dados_folhas[id_f_hist]
            
            st.warning(f"Selecionado: **{hist_sel['Matrícula']}** - {hist_sel['Veículo']} (Fechado a {hist_sel['Conclusão']})")
            
            col_abrir, col_apagar = st.columns(2)
            with col_abrir:
                if st.button("✏️ Reabrir na Nova Folha de Obra", use_container_width=True):
                    st.session_state.temp_pecas = info_f_hist.get('pecas', []) if isinstance(info_f_hist.get('pecas', []), list) else list(info_f_hist.get('pecas', {}).values())
                    st.session_state.temp_horas = info_f_hist.get('horas', []) if isinstance(info_f_hist.get('horas', []), list) else list(info_f_hist.get('horas', {}).values())
                    st.session_state.id_folha_editar = id_f_hist
                    st.session_state.pagina = "📋 Nova Folha de Obra"
                    st.rerun()
            with col_apagar:
                if st.button(f"🗑️ Apagar Histórico de {hist_sel['Matrícula']}", type="primary", use_container_width=True):
                    db.reference(f"folhas_obra/{id_f_hist}").delete()
                    st.success("Registo apagado!")
                    st.rerun()
    else:
        st.info("Ainda não existem folhas concluídas no histórico.")

# ==========================================
# PÁGINA 5: ARTIGOS / STOCK
# ==========================================
elif st.session_state.pagina == "📦 Artigos / Stock":
    st.title("📦 Gestão de Artigos e Inventário")
    st.write("---")
    col_art1, col_art2 = st.columns([1, 1.8])
    with col_art1:
        st.markdown("### 📥 Dar Entrada de Artigo")
        ref_artigo = st.text_input("Referência / Código Principal").upper().strip()
        nome_artigo = st.text_input("Nome / Descrição da Peça")
        ref_equivs = st.text_area("Referências Equivalentes (Separe por vírgulas ou espaços)").upper().strip()
        c_qtd, c_preco = st.columns(2)
        with c_qtd: qtd_artigo = st.number_input("Qtd Inicial", min_value=0, value=1, step=1)
        with c_preco: preco_artigo = st.number_input("Preço Unitário (€)", min_value=0.0, value=0.0, step=0.50, format="%.2f")
        if st.button("Registar no Stock", type="primary", use_container_width=True):
            if ref_artigo and nome_artigo:
                ref_l = re.sub(r'[^A-Z0-9-]', '', ref_artigo)
                db.reference(f'artigos/{ref_l}').set({'referencia_original': ref_artigo, 'nome': nome_artigo, 'equivalentes': ref_equivs, 'quantidade': int(qtd_artigo), 'preco': float(preco_artigo)})
                st.success("Artigo guardado!"); st.rerun()
    with col_art2:
        st.markdown("### 📋 Inventário Atual")
        pesquisa_art = st.text_input("Pesquisar por REF, Equivalente ou Descrição...").lower().strip()
        if dados_artigos:
            lista_artigos_tab = [{"REF_Chave": k, "Referência": v.get('referencia_original', k), "Descrição / Peça": v.get('nome', ''), "Equivalentes": v.get('equivalentes',''), "Stock": v.get('quantidade', 0), "Preço (€)": f"{v.get('preco', 0.0):.2f} €"} for k,v in dados_artigos.items() if not pesquisa_art or re.sub(r'[^a-z0-9]', '', pesquisa_art) in re.sub(r'[^a-z0-9]', '', v.get('referencia_original','').lower()) or pesquisa_art in v.get('nome','').lower() or re.sub(r'[^a-z0-9]', '', pesquisa_art) in re.sub(r'[^a-z0-9]', '', v.get('equivalentes','').lower())]
            if lista_artigos_tab:
                evt_selecao_art = st.dataframe(lista_artigos_tab, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
                sel_art = evt_selecao_art.get("selection", {}).get("rows", [])
                if sel_art:
                    ref_sistema = lista_artigos_tab[sel_art[0]]["REF_Chave"]
                    info_real = dados_artigos[ref_sistema]
                    st.warning(f"Selecionado: {info_real.get('nome')}")
                    ca1, ca2 = st.columns(2)
                    with ca1:
                        if st.button("➕ Adicionar 1"): db.reference(f'artigos/{ref_sistema}/quantidade').set(info_real.get('quantidade',0)+1); st.rerun()
                        if st.button("➖ Retirar 1", disabled=(info_real.get('quantidade',0)<=0)): db.reference(f'artigos/{ref_sistema}/quantidade').set(info_real.get('quantidade',0)-1); st.rerun()
                    with ca2:
                        np = st.number_input("Novo Preço", value=float(info_real.get('preco',0.0)))
                        if st.button("💾 Atualizar Preço"): db.reference(f'artigos/{ref_sistema}/preco').set(float(np)); st.rerun()
