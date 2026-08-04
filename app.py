import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_option_menu import option_menu
import io

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
    page_title="Natura 2026 - Control Estratégico",
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
        return float(val)
    
    s = str(val).replace('\xa0', '').replace('$', '').replace(' ', '').strip()
    if not s or s.lower() in ['nan', 'none', 'null']:
        return 0.0
    
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    elif '.' in s:
        parts = s.split('.')
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            s = s.replace('.', '')
            
    try:
        return float(s)
    except:
        return 0.0

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

def render_kpi_color(label, val, es_moneda=False):
    if val < 0:
        color = "#D32F2F"
    elif val > 0:
        color = "#1976D2"
    else:
        color = "#212121"
        
    formatted_val = fmt_moneda(val) if es_moneda else fmt_numero(val)
    
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

ORDEN_MESES = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 
               'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']

# ------------------------------------------------------------------------------
# 2. CARGA Y PREPROCESAMIENTO DE DATOS (CORREGIDO)
# ------------------------------------------------------------------------------
@st.cache_data
def load_data():
    archivo = "Ajustes de inventario Natura 2026.xlsx"
    df = pd.read_excel(archivo, sheet_name=0)
    
    # Normalización de encabezados
    df.columns = [str(c).replace('\xa0', ' ').strip() for c in df.columns]
    
    # Formato de Fechas y Semanas
    df['Fe.contabilización'] = pd.to_datetime(df['Fe.contabilización'], errors='coerce')
    df['Fecha_Día'] = df['Fe.contabilización'].dt.date
    df['Semana_Num'] = pd.to_numeric(df['Fe.contabilización'].dt.isocalendar().week, errors='coerce')
    
    if 'MES' in df.columns:
        df['MES'] = df['MES'].astype(str).str.upper().str.strip()
    else:
        df['MES'] = df['Fe.contabilización'].dt.strftime('%B').str.upper()
        
    df['MES'] = pd.Categorical(df['MES'], categories=ORDEN_MESES, ordered=True)
    
    # Detección de Columna AA (TIPO DE ALMACÉN 2)
    if len(df.columns) >= 27:
        df['TIPO DE ALMACÉN 2'] = df.iloc[:, 26].astype(str).str.replace('\xa0', ' ').str.strip()
    else:
        col_alm2 = [c for c in df.columns if 'ALMAC' in c.upper() and '2' in c]
        if col_alm2:
            df['TIPO DE ALMACÉN 2'] = df[col_alm2[0]].astype(str).str.replace('\xa0', ' ').str.strip()
        else:
            df['TIPO DE ALMACÉN 2'] = "Sin Especificar"

    df['TIPO DE ALMACÉN 2'] = df['TIPO DE ALMACÉN 2'].replace({'nan': 'Sin Especificar', 'None': 'Sin Especificar', '': 'Sin Especificar'})

    # Conversión numérica
    df['COSTO TOTAL'] = df['COSTO TOTAL'].apply(clean_num)
    df['Cantidad de diferencia'] = df['Cantidad de diferencia'].apply(clean_num)
    
    df['IRA'] = pd.to_numeric(df['IRA'], errors='coerce')
    df['IRA'] = df['IRA'].apply(lambda x: x/100 if x > 1 else x)
    
    df['ILA'] = pd.to_numeric(df['ILA'], errors='coerce')
    df['ILA'] = df['ILA'].apply(lambda x: x/100 if x > 1 else x)
    
    df['Efecto_Contable'] = df['Cantidad de diferencia'].apply(
        lambda x: 'Faltante (-)' if x < 0 else ('Sobrante (+)' if x > 0 else 'Sin Cambio')
    )
    
    # LIMPIEZA SEGURO DE COLUMNAS DE TEXTO (EVITA ERROR 'float' object has no attribute 'endswith')
    columnas_texto = ['MOTIVO', 'PROCESO', 'CATEGORIA', 'Producto', 'Descripción producto', 'CV', 'TIPO DE ALMACÉN 2']
    for col in columnas_texto:
        if col in df.columns:
            df[col] = df[col].fillna('Sin Especificar').astype(str).str.strip().str.replace('\xa0', ' ')
            df[col] = df[col].str.replace(r'\.0$', '', regex=True)
            df[col] = df[col].replace({'nan': 'Sin Especificar', 'None': 'Sin Especificar', '': 'Sin Especificar'})
            
    return df

try:
    df = load_data()
    
    st.title("🟧 Control Estratégico de Inventario Natura 2026")
    
    # --------------------------------------------------------------------------
    # 3. FILTROS GLOBALES
    # --------------------------------------------------------------------------
    st.sidebar.header("🎛️ Filtros de Análisis")
    
    min_date = df['Fe.contabilización'].min().date() if pd.notnull(df['Fe.contabilización'].min()) else None
    max_date = df['Fe.contabilización'].max().date() if pd.notnull(df['Fe.contabilización'].max()) else None
    
    if min_date and max_date:
        rango_fechas = st.sidebar.date_input("Rango de Fechas 2026", [min_date, max_date])
        if len(rango_fechas) == 2:
            f_inicio, f_fin = rango_fechas
        else:
            f_inicio, f_fin = min_date, max_date
    else:
        f_inicio, f_fin = None, None

    meses_presentes = [m for m in df['MES'].cat.categories if m in df['MES'].dropna().unique()]
    mes_sel = st.sidebar.multiselect("Mes", meses_presentes, default=meses_presentes)
    
    almacenes = sorted([x for x in df['TIPO DE ALMACÉN 2'].unique() if x not in ['Sin Especificar', 'nan', 'None']])
    almacen_sel = st.sidebar.multiselect("TIPO DE ALMACÉN 2", almacenes, default=almacenes)
    
    procesos = sorted([x for x in df['PROCESO'].unique() if x not in ['Sin Especificar', 'nan', 'None']])
    proceso_sel = st.sidebar.multiselect("Proceso (Col. X)", procesos, default=procesos)
    
    mask = (df['MES'].isin(mes_sel)) & (df['TIPO DE ALMACÉN 2'].isin(almacen_sel)) & (df['PROCESO'].isin(proceso_sel))
    if f_inicio and f_fin:
        mask = mask & (df['Fe.contabilización'].dt.date >= f_inicio) & (df['Fe.contabilización'].dt.date <= f_fin)
    
    df_f = df[mask]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### 📥 Exportar Reporte Filtrado")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_f[['Fe.contabilización', 'Producto', 'Descripción producto', 'MOTIVO', 'PROCESO', 'TIPO DE ALMACÉN 2', 'Cantidad de diferencia', 'COSTO TOTAL']].to_excel(writer, sheet_name='Reporte_Filtrado', index=False)
    
    st.sidebar.download_button(
        label="📄 Descargar Excel",
        data=buffer.getvalue(),
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

    # ==========================================================================
    # PESTAÑA 2: IRA E ILA
    # ==========================================================================
    elif selected_tab == "Indicadores IRA/ILA":
        st.subheader("🎯 Exactitud de Inventario (IRA) y Localización (ILA)")
        
        granularidad = st.radio("Ver tendencia por:", ["Mes", "Semana", "Día"], horizontal=True)
        
        if granularidad == "Mes":
            col_tiempo = 'MES'
            df_ira_ila = df_f.groupby(col_tiempo, observed=False)[['IRA', 'ILA']].mean().reset_index()
            df_ira_ila = df_ira_ila.dropna(subset=['IRA', 'ILA']).sort_values('MES')
            eje_x_labels = df_ira_ila['MES'].astype(str)
            
        elif granularidad == "Semana":
            col_tiempo = 'Semana_Num'
            df_ira_ila = df_f.groupby(col_tiempo, observed=False)[['IRA', 'ILA']].mean().reset_index()
            df_ira_ila = df_ira_ila.dropna(subset=['IRA', 'ILA']).sort_values('Semana_Num')
            eje_x_labels = "Sem " + df_ira_ila['Semana_Num'].astype(int).astype(str)
            
        else:
            col_tiempo = 'Fecha_Día'
            df_ira_ila = df_f.groupby(col_tiempo, observed=False)[['IRA', 'ILA']].mean().reset_index()
            df_ira_ila = df_ira_ila.dropna(subset=['IRA', 'ILA']).sort_values('Fecha_Día')
            eje_x_labels = df_ira_ila['Fecha_Día'].astype(str)
        
        fig_time = go.Figure()
        fig_time.add_trace(go.Scatter(x=eje_x_labels, y=df_ira_ila['IRA'], mode='lines+markers', name='IRA (%)', line=dict(color='#E25822', width=3)))
        fig_time.add_trace(go.Scatter(x=eje_x_labels, y=df_ira_ila['ILA'], mode='lines+markers', name='ILA (%)', line=dict(color='#264653', width=3)))
        
        fig_time.update_layout(title=f"Evolución Cronológica por {granularidad}", yaxis_title="Porcentaje (%)", hovermode="x unified")
        fig_time.update_yaxes(tickformat=".0%")
        fig_time.update_xaxes(tickangle=-45)
        st.plotly_chart(fig_time, use_container_width=True)
        
        with st.expander("📄 Ver detalle numérico de IRA e ILA"):
            st.dataframe(df_ira_ila.style.format({'IRA': '{:.2%}', 'ILA': '{:.2%}'}), hide_index=True)

    # ==========================================================================
    # PESTAÑA 3: DRILL-DOWN SKU
    # ==========================================================================
    elif selected_tab == "Drill-Down SKU":
        st.subheader("🔍 Drill-Down por SKU (Producto)")
        sku_lista = sorted([x for x in df_f['Producto'].unique() if x not in ['Sin Especificar', 'nan', 'None']])
        sku_seleccionado = st.selectbox("Seleccione el Producto / SKU:", sku_lista)
        
        df_sku = df_f[df_f['Producto'] == sku_seleccionado]
        
        if not df_sku.empty:
            st.info(f"**Descripción:** {df_sku['Descripción producto'].iloc[0]}")
            
            unidades_sku = df_sku['Cantidad de diferencia'].sum()
            costo_sku = df_sku['COSTO TOTAL'].sum()
            registros_sku = len(df_sku)
            
            k1, k2, k3 = st.columns(3)
            with k1:
                render_kpi_color("Unidades Ajustadas", unidades_sku, es_moneda=False)
            with k2:
                render_kpi_color("Imputación Contable Total", costo_sku, es_moneda=True)
            with k3:
                render_kpi_color("Registros de Ajuste", registros_sku, es_moneda=False)
            
            st.markdown("---")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                df_sku_mot = df_sku.groupby(['MOTIVO', 'Efecto_Contable'])['Cantidad de diferencia'].sum().reset_index()
                fig_mot = px.bar(df_sku_mot, x='MOTIVO', y='Cantidad de diferencia', color='Efecto_Contable', barmode='stack', color_discrete_map={'Faltante (-)': '#E63946', 'Sobrante (+)': '#2A9D8F'}, title="Ajuste por Motivo (Col. W)")
                fig_mot.update_xaxes(type='category', tickangle=-45)
                st.plotly_chart(fig_mot, use_container_width=True)
                
            with col_s2:
                df_sku_pr = df_sku.groupby(['PROCESO', 'Efecto_Contable'])['Cantidad de diferencia'].sum().reset_index()
                fig_pr = px.bar(df_sku_pr, x='PROCESO', y='Cantidad de diferencia', color='Efecto_Contable', barmode='stack', color_discrete_map={'Faltante (-)': '#E63946', 'Sobrante (+)': '#2A9D8F'}, title="Ajuste por Proceso (Col. X)")
                fig_pr.update_xaxes(type='category', tickangle=-45)
                st.plotly_chart(fig_pr, use_container_width=True)
                
            st.markdown("#### Detalle de Imputación Contable (Columna AB)")
            df_sku_display = df_sku[['Fe.contabilización', 'MOTIVO', 'PROCESO', 'TIPO DE ALMACÉN 2', 'Cantidad de diferencia', 'COSTO TOTAL']].copy()
            styled_df_sku = df_sku_display.style.format({'Cantidad de diferencia': fmt_numero, 'COSTO TOTAL': fmt_moneda})
            styled_df_sku = aplicar_estilos_styler(styled_df_sku, ['Cantidad de diferencia', 'COSTO TOTAL'])
            st.dataframe(styled_df_sku, use_container_width=True, hide_index=True)

    # ==========================================================================
    # PESTAÑA 4: DRILL-DOWN CV
    # ==========================================================================
    elif selected_tab == "Drill-Down CV":
        st.subheader("🏷️ Drill-Down por Código de Venta (CV - Columna AC)")
        cv_lista = sorted([x for x in df_f['CV'].unique() if x not in ['Sin Especificar', 'nan', 'None']])
        cv_seleccionado = st.selectbox("Seleccione el Código de Venta (CV):", cv_lista)
        
        df_cv = df_f[df_f['CV'] == cv_seleccionado]
        
        if not df_cv.empty:
            costo_cv = df_cv['COSTO TOTAL'].sum()
            unidades_cv = df_cv['Cantidad de diferencia'].sum()
            prods_cv = df_cv['Producto'].nunique()
            
            kc1, kc2, kc3 = st.columns(3)
            with kc1:
                render_kpi_color("Imputación Contable Total", costo_cv, es_moneda=True)
            with kc2:
                render_kpi_color("Unidades Diferencia", unidades_cv, es_moneda=False)
            with kc3:
                render_kpi_color("Productos Afectados", prods_cv, es_moneda=False)
            
            st.markdown("---")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                fig_cv_w = px.pie(df_cv.groupby('MOTIVO')['COSTO TOTAL'].apply(lambda x: x.abs().sum()).reset_index(), values='COSTO TOTAL', names='MOTIVO', title="Costo por Motivo (Col W)")
                st.plotly_chart(fig_cv_w, use_container_width=True)
                
            with col_c2:
                fig_cv_x = px.pie(df_cv.groupby('PROCESO')['COSTO TOTAL'].apply(lambda x: x.abs().sum()).reset_index(), values='COSTO TOTAL', names='PROCESO', title="Costo por Proceso (Col X)")
                st.plotly_chart(fig_cv_x, use_container_width=True)
                
            st.markdown("#### Detalle Contable del CV Seleccionado")
            df_cv_display = df_cv[['Fe.contabilización', 'Producto', 'Descripción producto', 'MOTIVO', 'PROCESO', 'TIPO DE ALMACÉN 2', 'Cantidad de diferencia', 'COSTO TOTAL']].copy()
            styled_df_cv = df_cv_display.style.format({'Cantidad de diferencia': fmt_numero, 'COSTO TOTAL': fmt_moneda})
            styled_df_cv = aplicar_estilos_styler(styled_df_cv, ['Cantidad de diferencia', 'COSTO TOTAL'])
            st.dataframe(styled_df_cv, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error procesando el archivo. Detalles: {e}")
