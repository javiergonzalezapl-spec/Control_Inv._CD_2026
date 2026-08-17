import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_option_menu import option_menu
import io
import re

# ------------------------------------------------------------------------------
# 0. CONTROL DE ACCESO POR CONTRASEÑA
# ------------------------------------------------------------------------------
def check_password():
    def password_entered():
        if st.session_state["password"] == "Natura2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔑 Ingrese la contraseña de acceso:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔑 Ingrese la contraseña de acceso:", type="password", on_change=password_entered, key="password")
        st.error("😕 Contraseña incorrecta")
        return False
    else:
        return True

if not check_password():
    st.stop()

# ------------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Control de Inventario CD Natura 2026",
    page_icon="🟧",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main .block-container {padding-top: 1rem; padding-bottom: 1.5rem;}
    
    .kpi-card {
        background-color: #FFFFFF;
        padding: 12px 16px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    
    [data-testid="stSidebar"] [data-baseweb="tag"] {
        font-size: 0.70rem !important;
        background-color: #E63946 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# FUNCIONES DE FORMATO Y LIMPIEZA NUMÉRICA
# ------------------------------------------------------------------------------
def clean_num(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val) if not pd.isna(val) else 0.0
    
    s = str(val).replace('\xa0', '').replace('$', '').replace(' ', '').strip()
    if not s or s.lower() in ['nan', 'none', 'null', '-', '--', '']:
        return 0.0

    is_negative = False
    if (s.startswith('(') and s.endswith(')')) or s.endswith('-'):
        is_negative = True
        s = s.replace('(', '').replace(')', '').replace('-', '').strip()
    elif s.startswith('-'):
        is_negative = True
        s = s[1:].strip()

    s = re.sub(r'[^\d.,]', '', s)
    if not s:
        return 0.0

    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        parts = s.split(',')
        if len(parts[-1]) == 3 and len(parts) > 1:
            s = s.replace(',', '')
        else:
            s = s.replace(',', '.')
    elif '.' in s:
        parts = s.split('.')
        if len(parts) > 2 or (len(parts[-1]) == 3 and len(parts) > 1):
            s = s.replace('.', '')

    try:
        num = float(s)
        return -num if is_negative else num
    except:
        return 0.0

def parse_dates_robust(series):
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    s_num = pd.to_numeric(series, errors='coerce')
    is_excel_serial = s_num.notna() & (s_num > 30000) & (s_num < 60000)
    
    res = pd.Series(index=series.index, dtype='datetime64[ns]')
    if is_excel_serial.any():
        res[is_excel_serial] = pd.to_datetime(s_num[is_excel_serial], unit='D', origin='1899-12-30', errors='coerce')
    if (~is_excel_serial).any():
        res[~is_excel_serial] = pd.to_datetime(series[~is_excel_serial], errors='coerce')
    return res

def clean_pct_raw(val):
    if pd.isna(val):
        return None
    num = clean_num(val)
    if num > 1.0:
        return num / 100.0
    return num

def calc_efecto(val):
    if val < 0:
        return 'Faltante (-)'
    elif val > 0:
        return 'Sobrante (+)'
    else:
        return 'Sin Cambio'

def fmt_moneda(valor, con_signo_suma=False):
    if pd.isna(valor):
        return "$0"
    es_negativo = valor < 0
    val_abs = abs(valor)
    formatted = f"{val_abs:,.0f}".replace(",", ".")
    if es_negativo:
        return f"-${formatted}"
    elif con_signo_suma and valor > 0:
        return f"+${formatted}"
    else:
        return f"${formatted}"

def fmt_numero(valor):
    if pd.isna(valor):
        return "0"
    es_negativo = valor < 0
    val_abs = abs(valor)
    formatted = f"{val_abs:,.0f}".replace(",", ".")
    return f"-{formatted}" if es_negativo else formatted

def render_kpi_color(label, val, es_moneda=False, es_porcentaje=False, color_override=None):
    if color_override:
        color = color_override
    elif val < 0:
        color = "#D32F2F"
    elif val > 0:
        color = "#1976D2"
    else:
        color = "#212121"
        
    if es_porcentaje:
        formatted_val = f"{val:.1%}" if pd.notna(val) else "0.0%"
    elif es_moneda:
        formatted_val = fmt_moneda(val)
    else:
        formatted_val = fmt_numero(val)
    
    html = f"""
    <div class="kpi-card" style="border-left: 5px solid {color};">
        <div style="font-size: 0.80rem; color: #666; font-weight: 600;">{label}</div>
        <div style="font-size: 1.5rem; font-weight: bold; color: {color}; margin-top: 2px;">{formatted_val}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def color_celda(val):
    try:
        if isinstance(val, (int, float)):
            num = val
        else:
            clean_str = str(val).replace('$', '').replace('.', '').replace(',', '.').strip()
            num = float(clean_str)
        
        if num < 0:
            return 'color: #D32F2F; font-weight: bold;'
        elif num > 0:
            return 'color: #1976D2; font-weight: bold;'
        else:
            return 'color: #212121;'
    except:
        return 'color: #212121;'

def aplicar_estilos_styler(styler, subset):
    try:
        return styler.map(color_celda, subset=subset)
    except AttributeError:
        return styler.applymap(color_celda, subset=subset)

@st.cache_data
def generar_excel_descarga(df_sub):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_sub[['Fe.contabilización', 'Producto', 'Descripción producto', 'MOTIVO', 'PROCESO', 'TIPO DE ALMACÉN 2', 'Cantidad de diferencia', 'COSTO TOTAL']].to_excel(writer, sheet_name='Reporte_Filtrado', index=False)
    return buffer.getvalue()

ORDEN_MESES = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 
               'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']

# ------------------------------------------------------------------------------
# 2. CARGA Y PREPROCESAMIENTO DE DATOS CON MAPEO POSICIONAL
# ------------------------------------------------------------------------------
@st.cache_data
def load_data():
    archivo = "Ajustes de inventario Natura 2026.xlsb"
    df = pd.read_excel(archivo, sheet_name=0, engine='pyxlsb')
    
    cols = list(df.columns)
    
    col_mapping = {}
    if len(cols) > 0:  col_mapping[cols[0]]  = 'Fe.contabilización'
    if len(cols) > 5:  col_mapping[cols[5]]  = 'Producto'
    if len(cols) > 6:  col_mapping[cols[6]]  = 'Descripción producto'
    if len(cols) > 10: col_mapping[cols[10]] = 'Cantidad de diferencia'
    if len(cols) > 22: col_mapping[cols[22]] = 'MOTIVO'
    if len(cols) > 23: col_mapping[cols[23]] = 'PROCESO'
    if len(cols) > 26: col_mapping[cols[26]] = 'TIPO DE ALMACÉN 2'
    if len(cols) > 28: col_mapping[cols[28]] = 'COSTO TOTAL'
    if len(cols) > 29: col_mapping[cols[29]] = 'CV'
    if len(cols) > 31: col_mapping[cols[31]] = 'IRA'
    if len(cols) > 32: col_mapping[cols[32]] = 'ILA'
    if len(cols) > 33: col_mapping[cols[33]] = 'MES'
    if len(cols) > 34: col_mapping[cols[34]] = 'TARGET IRA'
    if len(cols) > 35: col_mapping[cols[35]] = 'TARGET ILA'

    df = df.rename(columns=col_mapping)
    
    for c in df.columns:
        if 'TARGET' in str(c).upper() and 'IRA' in str(c).upper():
            df = df.rename(columns={c: 'TARGET IRA'})
        elif 'TARGET' in str(c).upper() and 'ILA' in str(c).upper():
            df = df.rename(columns={c: 'TARGET ILA'})

    df = df.loc[:, ~df.columns.duplicated(keep='first')].copy()

    df['Fe.contabilización'] = parse_dates_robust(df['Fe.contabilización'])
    df['Fecha_Día'] = df['Fe.contabilización'].dt.date
    df['Semana_Num'] = pd.to_numeric(df['Fe.contabilización'].dt.isocalendar().week, errors='coerce')
    
    if 'MES' in df.columns:
        df['MES'] = df['MES'].astype(str).str.upper().str.strip()
    else:
        df['MES'] = df['Fe.contabilización'].dt.strftime('%B').str.upper()
        
    df['MES'] = pd.Categorical(df['MES'], categories=ORDEN_MESES, ordered=True)

    df['Cantidad de diferencia'] = df['Cantidad de diferencia'].apply(clean_num)
    df['COSTO TOTAL'] = df['COSTO TOTAL'].apply(clean_num)
    
    if 'IRA' in df.columns:
        df['IRA'] = df['IRA'].apply(clean_pct_raw)
    else:
        df['IRA'] = None

    if 'ILA' in df.columns:
        df['ILA'] = df['ILA'].apply(clean_pct_raw)
    else:
        df['ILA'] = None

    if 'TARGET IRA' in df.columns:
        df['TARGET IRA'] = df['TARGET IRA'].apply(clean_pct_raw)
    else:
        df['TARGET IRA'] = 0.985

    if 'TARGET ILA' in df.columns:
        df['TARGET ILA'] = df['TARGET ILA'].apply(clean_pct_raw)
    else:
        df['TARGET ILA'] = 0.975

    df['Efecto_Contable'] = df['Cantidad de diferencia'].apply(calc_efecto)
    
    columnas_texto = ['MOTIVO', 'PROCESO', 'CATEGORIA', 'Producto', 'Descripción producto', 'CV', 'TIPO DE ALMACÉN 2']
    for col in columnas_texto:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.replace('\xa0', ' ')
            df[col] = df[col].str.replace(r'\.0$', '', regex=True)
            df[col] = df[col].replace({'nan': 'Sin Especificar', 'None': 'Sin Especificar', '': 'Sin Especificar'})
            
    return df

try:
    df = load_data()
    
    st.title("🟧 Control de Inventario CD Natura 2026")
    
    # --------------------------------------------------------------------------
    # 3. FILTROS GLOBALES
    # --------------------------------------------------------------------------
    st.sidebar.header("🎛️ Filtros de Análisis")
    
    valid_dates = df['Fe.contabilización'].dropna()
    min_date = valid_dates.min().date() if not valid_dates.empty else None
    max_date = valid_dates.max().date() if not valid_dates.empty else None
    
    if min_date and max_date:
        rango_fechas = st.sidebar.date_input("Rango de Fechas 2026", [min_date, max_date])
        if len(rango_fechas) == 2:
            f_inicio, f_fin = rango_fechas[0], rango_fechas[1]
        else:
            f_inicio, f_fin = min_date, max_date
    else:
        f_inicio, f_fin = None, None

    meses_presentes = [m for m in df['MES'].cat.categories if m in df['MES'].dropna().unique()]
    mes_sel = st.sidebar.multiselect("Mes", meses_presentes, default=meses_presentes)
    
    almacenes = sorted([x for x in df['TIPO DE ALMACÉN 2'].unique() if x not in ['Sin Especificar', 'nan', 'None']])
    almacen_sel = st.sidebar.multiselect("TIPO DE ALMACÉN 2", almacenes, default=almacenes)
    
    procesos = sorted([x for x in df['PROCESO'].unique() if x not in ['Sin Especificar', 'nan', 'None']])
    
    default_proc = [p for p in procesos if 'CICLICO' in p.upper() or 'CÍCLICO' in p.upper()]
    if not default_proc:
        default_proc = procesos
        
    proceso_sel = st.sidebar.multiselect("Proceso (Col. X)", procesos, default=default_proc)
    
    mask = (df['MES'].isin(mes_sel)) & (df['TIPO DE ALMACÉN 2'].isin(almacen_sel)) & (df['PROCESO'].isin(proceso_sel))
    if f_inicio is not None and f_fin is not None:
        mask = mask & (df['Fe.contabilización'].dt.date >= f_inicio) & (df['Fe.contabilización'].dt.date <= f_fin)
    
    df_f = df[mask]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### 📥 Exportar Reporte Filtrado")
    
    excel_bytes = generar_excel_descarga(df_f)
    
    st.sidebar.download_button(
        label="📄 Descargar Excel",
        data=excel_bytes,
        file_name="Reporte_Ajustes_Natura_2026.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --------------------------------------------------------------------------
    # 4. BARRA DE NAVEGACIÓN
    # --------------------------------------------------------------------------
    selected_tab = option_menu(
        menu_title=None,
        options=["Imputación Contable", "Indicadores IRA/ILA", "Drill-Down SKU", "Drill-Down CV"],
        icons=["calculator", "graph-up-arrow", "box-seam", "tag"],
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "#FAFAFA"},
            "icon": {"color": "#E63946", "font-size": "16px"},
            "nav-link": {"font-size": "14px", "text-align": "center", "margin": "0px", "--hover-color": "#EEE"},
            "nav-link-selected": {"background-color": "#E63946", "color": "white"},
        }
    )

    # ==========================================================================
    # PESTAÑA 1: IMPUTACIÓN CONTABLE
    # ==========================================================================
    if selected_tab == "Imputación Contable":
        st.subheader("📊 Resumen de Imputación Contable")
        
        df_faltantes = df_f[df_f['Efecto_Contable'] == 'Faltante (-)']
        df_sobrantes = df_f[df_f['Efecto_Contable'] == 'Sobrante (+)']
        
        monto_faltantes = abs(df_faltantes['COSTO TOTAL'].sum())
        monto_sobrantes = abs(df_sobrantes['COSTO TOTAL'].sum())
        valor_neto = monto_sobrantes - monto_faltantes
        
        c1, c2, c3 = st.columns(3)
        with c1:
            render_kpi_color("Total Faltantes (Pérdida)", -monto_faltantes, es_moneda=True)
        with c2:
            render_kpi_color("Total Sobrantes (Excedente)", monto_sobrantes, es_moneda=True)
        with c3:
            render_kpi_color("Valor Neto Contable", valor_neto, es_moneda=True)
            
        st.divider()
        
        st.markdown("#### 🌊 Reconciliación Contable Dinámica (Cascada)")
        fig_waterfall = go.Figure(go.Waterfall(
            name="Contabilidad", orientation="v",
            measure=["relative", "relative", "total"],
            x=["Faltantes (-)", "Sobrantes (+)", "Resultado Neto"],
            textposition="outside",
            text=[fmt_moneda(-monto_faltantes), fmt_moneda(monto_sobrantes), fmt_moneda(valor_neto)],
            y=[-monto_faltantes, monto_sobrantes, valor_neto],
            connector={"line": {"color": "#888"}},
            decreasing={"marker": {"color": "#E63946"}},
            increasing={"marker": {"color": "#2A9D8F"}},
            totals={"marker": {"color": "#264653"}}
        ))
        fig_waterfall.update_layout(title="Flujo de Ajustes Financieros ($)", yaxis_tickformat="$,.0f")
        st.plotly_chart(fig_waterfall, use_container_width=True)

        st.divider()
        
        col_m, col_p = st.columns(2)
        with col_m:
            st.markdown("#### Imputación por Mes (Acumulado)")
            df_mes_bar = df_f.groupby(['MES', 'Efecto_Contable'], observed=False)['COSTO TOTAL'].apply(lambda x: x.abs().sum()).reset_index()
            fig_bar_mes = px.bar(
                df_mes_bar, x='MES', y='COSTO TOTAL', color='Efecto_Contable',
                barmode='stack',
                color_discrete_map={'Faltante (-)': '#E63946', 'Sobrante (+)': '#2A9D8F'},
                title="Monto Acumulado por Mes"
            )
            fig_bar_mes.update_xaxes(type='category', title_text="Mes", tickangle=-45)
            fig_bar_mes.update_yaxes(tickformat="$,.0f", title_text="Impacto Financiero ($)")
            st.plotly_chart(fig_bar_mes, use_container_width=True)

        with col_p:
            st.markdown("#### Impacto por Proceso (Acumulado)")
            df_proc_bar = df_f.groupby(['PROCESO', 'Efecto_Contable'])['COSTO TOTAL'].apply(lambda x: x.abs().sum()).reset_index()
            fig_bar_proc = px.bar(
                df_proc_bar, x='PROCESO', y='COSTO TOTAL', color='Efecto_Contable',
                barmode='stack',
                color_discrete_map={'Faltante (-)': '#E63946', 'Sobrante (+)': '#2A9D8F'},
                title="Monto Acumulado por Proceso"
            )
            fig_bar_proc.update_xaxes(type='category', title_text="Proceso", tickangle=-45)
            fig_bar_proc.update_yaxes(tickformat="$,.0f", title_text="Impacto Financiero ($)")
            st.plotly_chart(fig_bar_proc, use_container_width=True)

        st.divider()

        st.markdown("#### Importes de Ajuste por TIPO DE ALMACÉN 2")
        df_alm2_bar = df_f.groupby(['TIPO DE ALMACÉN 2', 'Efecto_Contable'])['COSTO TOTAL'].apply(lambda x: x.abs().sum()).reset_index()
        fig_bar_alm2 = px.bar(
            df_alm2_bar, x='TIPO DE ALMACÉN 2', y='COSTO TOTAL', color='Efecto_Contable',
            barmode='stack',
            color_discrete_map={'Faltante (-)': '#E63946', 'Sobrante (+)': '#2A9D8F'},
            title="Monto Acumulado por Tipo de Almacén 2"
        )
        fig_bar_alm2.update_xaxes(type='category', title_text="Tipo de Almacén 2", tickangle=-45)
        fig_bar_alm2.update_yaxes(tickformat="$,.0f", title_text="Impacto Financiero ($)")
        st.plotly_chart(fig_bar_alm2, use_container_width=True)

    # ==========================================================================
    # PESTAÑA 2: IRA E ILA SEPARADOS CON SUS PROPIAS METRICAS Y TARGETS
    # ==========================================================================
    elif selected_tab == "Indicadores IRA/ILA":
        st.subheader("🎯 Indicadores de Exactitud y Localización de Inventarios")
        
        granularidad = st.radio("Ver tendencia por:", ["Mes", "Semana", "Día"], horizontal=True)
        st.markdown("---")

        cols_groupby = ['IRA', 'ILA']
        if 'TARGET IRA' in df_f.columns: cols_groupby.append('TARGET IRA')
        if 'TARGET ILA' in df_f.columns: cols_groupby.append('TARGET ILA')

        if granularidad == "Mes":
            col_tiempo = 'MES'
            df_ira_ila = df_f.groupby(col_tiempo, observed=False)[cols_groupby].mean().reset_index()
            df_ira_ila = df_ira_ila.dropna(subset=['IRA', 'ILA'], how='all').sort_values('MES')
            eje_x_labels = df_ira_ila['MES'].astype(str)
            
        elif granularidad == "Semana":
            col_tiempo = 'Semana_Num'
            df_ira_ila = df_f.groupby(col_tiempo, observed=False)[cols_groupby].mean().reset_index()
            df_ira_ila = df_ira_ila.dropna(subset=['IRA', 'ILA'], how='all').sort_values('Semana_Num')
            eje_x_labels = "Sem " + df_ira_ila['Semana_Num'].astype(int).astype(str)
            
        else:
            col_tiempo = 'Fecha_Día'
            df_ira_ila = df_f.groupby(col_tiempo, observed=False)[cols_groupby].mean().reset_index()
            df_ira_ila = df_ira_ila.dropna(subset=['IRA', 'ILA'], how='all').sort_values('Fecha_Día')
            eje_x_labels = df_ira_ila['Fecha_Día'].astype(str)

        # Asignar metas predeterminadas si no vienen en la planilla (IRA: 98.5%, ILA: 97.5%)
        if 'TARGET IRA' not in df_ira_ila.columns or df_ira_ila['TARGET IRA'].isna().all():
            df_ira_ila['TARGET IRA'] = 0.985
        if 'TARGET ILA' not in df_ira_ila.columns or df_ira_ila['TARGET ILA'].isna().all():
            df_ira_ila['TARGET ILA'] = 0.975

        # ----------------------------------------------------------------------
        # BLOQUE 1: EXACTITUD DE INVENTARIO (IRA)
        # ----------------------------------------------------------------------
        st.markdown("### 🎯 EXACTITUD DE INVENTARIO (IRA)")
        
        ira_series = df_f['IRA'].dropna()
        ira_acum = float(ira_series.mean()) if not ira_series.empty else 0.0
        
        target_ira_series = df_f['TARGET IRA'].dropna() if 'TARGET IRA' in df_f.columns else pd.Series()
        target_ira_acum = float(target_ira_series.mean()) if not target_ira_series.empty else 0.985

        c_ira1, c_ira2 = st.columns(2)
        with c_ira1:
            render_kpi_color("IRA Acumulado", ira_acum, es_porcentaje=True, color_override="#1976D2")
        with c_ira2:
            render_kpi_color("TARGET IRA", target_ira_acum, es_porcentaje=True, color_override="#FF8F00")

        ira_labels = [f"{v:.1%}" if pd.notna(v) else "" for v in df_ira_ila['IRA']]
        target_ira_labels = [f"{v:.1%}" if pd.notna(v) else "" for v in df_ira_ila['TARGET IRA']]

        fig_ira = go.Figure()
        
        fig_ira.add_trace(go.Scatter(
            x=eje_x_labels, 
            y=df_ira_ila['IRA'], 
            mode='lines+markers+text', 
            name='IRA Real (%)', 
            text=ira_labels,
            textposition="top center",
            textfont=dict(size=11, color='#1976D2', family="sans-serif"),
            line=dict(color='#1976D2', width=4),
            marker=dict(size=8, color='#1976D2')
        ))
        
        fig_ira.add_trace(go.Scatter(
            x=eje_x_labels, 
            y=df_ira_ila['TARGET IRA'], 
            mode='lines+markers+text', 
            name='Target IRA (%)', 
            text=target_ira_labels,
            textposition="bottom center",
            textfont=dict(size=10, color='#FF8F00', family="sans-serif"),
            line=dict(color='#FF8F00', width=2.5, dash='dash'),
            marker=dict(size=6, color='#FF8F00')
        ))
            
        fig_ira.update_layout(
            title=f"Evolución Cronológica IRA vs Target (98.5%) por {granularidad}", 
            yaxis_title="Porcentaje (%)", 
            hovermode="x unified",
            height=380,
            margin=dict(t=50, b=50, l=40, r=40)
        )
        fig_ira.update_yaxes(tickformat=".1%", automargin=True)
        fig_ira.update_xaxes(tickangle=-45)

        st.plotly_chart(fig_ira, use_container_width=True)

        st.divider()

        # ----------------------------------------------------------------------
        # BLOQUE 2: LOCALIZACIÓN DE INVENTARIO (ILA)
        # ----------------------------------------------------------------------
        st.markdown("### 📍 LOCALIZACIÓN DE INVENTARIO (ILA)")
        
        ila_series = df_f['ILA'].dropna()
        ila_acum = float(ila_series.mean()) if not ila_series.empty else 0.0
        
        target_ila_series = df_f['TARGET ILA'].dropna() if 'TARGET ILA' in df_f.columns else pd.Series()
        target_ila_acum = float(target_ila_series.mean()) if not target_ila_series.empty else 0.975

        c_ila1, c_ila2 = st.columns(2)
        with c_ila1:
            render_kpi_color("ILA Acumulado", ila_acum, es_porcentaje=True, color_override="#1976D2")
        with c_ila2:
            render_kpi_color("TARGET ILA", target_ila_acum, es_porcentaje=True, color_override="#FF8F00")

        ila_labels = [f"{v:.1%}" if pd.notna(v) else "" for v in df_ira_ila['ILA']]
        target_ila_labels = [f"{v:.1%}" if pd.notna(v) else "" for v in df_ira_ila['TARGET ILA']]

        fig_ila = go.Figure()
        
        fig_ila.add_trace(go.Scatter(
            x=eje_x_labels, 
            y=df_ira_ila['ILA'], 
            mode='lines+markers+text', 
            name='ILA Real (%)', 
            text=ila_labels,
            textposition="top center",
            textfont=dict(size=11, color='#1976D2', family="sans-serif"),
            line=dict(color='#1976D2', width=4),
            marker=dict(size=8, color='#1976D2')
        ))
        
        fig_ila.add_trace(go.Scatter(
            x=eje_x_labels, 
            y=df_ira_ila['TARGET ILA'], 
            mode='lines+markers+text', 
            name='Target ILA (%)', 
            text=target_ila_labels,
            textposition="bottom center",
            textfont=dict(size=10, color='#FF8F00', family="sans-serif"),
            line=dict(color='#FF8F00', width=2.5, dash='dash'),
            marker=dict(size=6, color='#FF8F00')
        ))
            
        fig_ila.update_layout(
            title=f"Evolución Cronológica ILA vs Target (97.5%) por {granularidad}", 
            yaxis_title="Porcentaje (%)", 
            hovermode="x unified",
            height=380,
            margin=dict(t=50, b=50, l=40, r=40)
        )
        fig_ila.update_yaxes(tickformat=".1%", automargin=True)
        fig_ila.update_xaxes(tickangle=-45)

        st.plotly_chart(fig_ila, use_container_width=True)
        
        with st.expander("📄 Ver detalle numérico de IRA e ILA"):
            fmt_map = {'IRA': '{:.2%}', 'ILA': '{:.2%}'}
            if 'TARGET IRA' in df_ira_ila.columns: fmt_map['TARGET IRA'] = '{:.2%}'
            if 'TARGET ILA' in df_ira_ila.columns: fmt_map['TARGET ILA'] = '{:.2%}'
            st.dataframe(df_ira_ila.style.format(fmt_map), hide_index=True)

    # ==========================================================================
    # PESTAÑA 3: DRILL-DOWN SKU (PRODUCTO)
    # ==========================================================================
    elif selected_tab == "Drill-Down SKU":
        st.subheader("🔍 Drill-Down por SKU (Producto)")
        
        df_f_ajustes = df_f[df_f['Cantidad de diferencia'] != 0]
        sku_lista = sorted([x for x in df_f_ajustes['Producto'].unique() if str(x) not in ['Sin Especificar', 'nan', 'None']])
        if not sku_lista:
            sku_lista = sorted([x for x in df_f['Producto'].unique() if str(x) not in ['Sin Especificar', 'nan', 'None']])

        sku_seleccionado = st.selectbox("Seleccione el Producto / SKU:", sku_lista)
        
        df_sku = df_f[df_f['Producto'] == sku_seleccionado]
        df_sku_adj = df_sku[df_sku['Cantidad de diferencia'] != 0]
        if df_sku_adj.empty:
            df_sku_adj = df_sku

        if not df_sku.empty:
            desc_val = df_sku_adj['Descripción producto'].iloc[0] if not df_sku_adj.empty else df_sku['Descripción producto'].iloc[0]
            st.info(f"**Descripción producto:** {desc_val}")
            
            unidades_sku = float(df_sku_adj['Cantidad de diferencia'].sum())
            costo_sku = float(df_sku_adj['COSTO TOTAL'].sum())
            registros_sku = int(len(df_sku_adj))
            
            k1, k2, k3 = st.columns(3)
            with k1:
                render_kpi_color("Imputación Contable Total (Col. AC)", costo_sku, es_moneda=True)
            with k2:
                render_kpi_color("Unidades Ajustadas (Col. K)", unidades_sku, es_moneda=False)
            with k3:
                render_kpi_color("Ajustes de Inventario (Hitos)", registros_sku, es_moneda=False)
            
            st.markdown("---")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                df_sku_mot = df_sku_adj.groupby(['MOTIVO', 'Efecto_Contable'])['Cantidad de diferencia'].sum().reset_index()
                fig_mot = px.bar(df_sku_mot, x='MOTIVO', y='Cantidad de diferencia', color='Efecto_Contable', barmode='stack', color_discrete_map={'Faltante (-)': '#E63946', 'Sobrante (+)': '#2A9D8F'}, title="Ajuste por Motivo (Col. W)")
                fig_mot.update_xaxes(type='category', tickangle=-45)
                st.plotly_chart(fig_mot, use_container_width=True)
                
            with col_s2:
                df_sku_pr = df_sku_adj.groupby(['PROCESO', 'Efecto_Contable'])['Cantidad de diferencia'].sum().reset_index()
                fig_pr = px.bar(df_sku_pr, x='PROCESO', y='Cantidad de diferencia', color='Efecto_Contable', barmode='stack', color_discrete_map={'Faltante (-)': '#E63946', 'Sobrante (+)': '#2A9D8F'}, title="Ajuste por Proceso (Col. X)")
                fig_pr.update_xaxes(type='category', tickangle=-45)
                st.plotly_chart(fig_pr, use_container_width=True)
                
            st.markdown("#### Detalle de Imputación Contable (Columna AC)")
            df_sku_display = df_sku_adj[['Fe.contabilización', 'MOTIVO', 'PROCESO', 'TIPO DE ALMACÉN 2', 'Cantidad de diferencia', 'COSTO TOTAL']].copy()
            styled_df_sku = df_sku_display.style.format({'Cantidad de diferencia': fmt_numero, 'COSTO TOTAL': fmt_moneda})
            styled_df_sku = aplicar_estilos_styler(styled_df_sku, ['Cantidad de diferencia', 'COSTO TOTAL'])
            st.dataframe(styled_df_sku, use_container_width=True, hide_index=True)

    # ==========================================================================
    # PESTAÑA 4: DRILL-DOWN CÓDIGO DE VENTA (CV)
    # ==========================================================================
    elif selected_tab == "Drill-Down CV":
        st.subheader("🏷️ Drill-Down por Código de Venta (CV - Columna AD)")
        
        df_f_ajustes_cv = df_f[df_f['Cantidad de diferencia'] != 0]
        cv_lista = sorted([x for x in df_f_ajustes_cv['CV'].unique() if str(x) not in ['Sin Especificar', 'nan', 'None']])
        if not cv_lista:
            cv_lista = sorted([x for x in df_f['CV'].unique() if str(x) not in ['Sin Especificar', 'nan', 'None']])

        cv_seleccionado = st.selectbox("Seleccione el Código de Venta (CV):", cv_lista)
        
        df_cv = df_f[df_f['CV'] == cv_seleccionado]
        df_cv_adj = df_cv[df_cv['Cantidad de diferencia'] != 0]
        if df_cv_adj.empty:
            df_cv_adj = df_cv
        
        if not df_cv.empty:
            descs_validas = df_cv_adj[df_cv_adj['Descripción producto'].notna() & (~df_cv_adj['Descripción producto'].isin(['Sin Especificar', 'nan', 'None', '']))]['Descripción producto']
            if not descs_validas.empty:
                desc_principal = descs_validas.value_counts().index[0]
            else:
                desc_principal = df_cv['Descripción producto'].iloc[0]
                
            st.info(f"**Descripción producto:** {desc_principal}")

            costo_cv = float(df_cv_adj['COSTO TOTAL'].sum())
            unidades_cv = float(df_cv_adj['Cantidad de diferencia'].sum())
            registros_cv = int(len(df_cv_adj))
            
            kc1, kc2, kc3 = st.columns(3)
            with kc1:
                render_kpi_color("Imputación Contable Total (Col. AC)", costo_cv, es_moneda=True)
            with kc2:
                render_kpi_color("Unidades Ajustadas (Col. K)", unidades_cv, es_moneda=False)
            with kc3:
                render_kpi_color("Ajustes de Inventario (Hitos)", registros_cv, es_moneda=False)
            
            st.markdown("---")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                fig_cv_w = px.pie(df_cv_adj.groupby('MOTIVO')['COSTO TOTAL'].apply(lambda x: x.abs().sum()).reset_index(), values='COSTO TOTAL', names='MOTIVO', title="Costo por Motivo (Col W)")
                st.plotly_chart(fig_cv_w, use_container_width=True)
                
            with col_c2:
                fig_cv_x = px.pie(df_cv_adj.groupby('PROCESO')['COSTO TOTAL'].apply(lambda x: x.abs().sum()).reset_index(), values='COSTO TOTAL', names='PROCESO', title="Costo por Proceso (Col X)")
                st.plotly_chart(fig_cv_x, use_container_width=True)
                
            st.markdown("#### Detalle Contable del CV Seleccionado")
            df_cv_display = df_cv_adj[['Fe.contabilización', 'Producto', 'Descripción producto', 'MOTIVO', 'PROCESO', 'TIPO DE ALMACÉN 2', 'Cantidad de diferencia', 'COSTO TOTAL']].copy()
            styled_df_cv = df_cv_display.style.format({'Cantidad de diferencia': fmt_numero, 'COSTO TOTAL': fmt_moneda})
            styled_df_cv = aplicar_estilos_styler(styled_df_cv, ['Cantidad de diferencia', 'COSTO TOTAL'])
            st.dataframe(styled_df_cv, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error procesando el archivo. Detalles: {e}")
