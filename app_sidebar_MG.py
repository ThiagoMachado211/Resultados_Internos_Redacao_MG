# app.py — lê dados.xlsx na MESMA pasta e usa menu lateral (abas verticais)
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from pandas.api.types import is_numeric_dtype

# ====== CONFIG ======
EXCEL_PATH = "Comparativo_MG.xlsx"
PAGE_TITLE = "Notas por Regional: Minas Gerais"
FONT_SIZE = 24
MARKER_SIZE = 12
# ====================

st.set_page_config(page_title=PAGE_TITLE, layout="wide")
st.title(PAGE_TITLE)
st.caption("")

# CSS — fonte 24px nos principais widgets, inclusive no menu lateral (radio)
st.markdown("""
<style>
/* Títulos e textos base */
html, body, [class*="css"] { font-size: 24px !important; }

/* Label e opções do selectbox */
.stSelectbox label { font-size: 24px !important; }
.stSelectbox div[data-baseweb="select"] div { font-size: 24px !important; }

/* Radio (menu lateral) — cobre diferentes versões de Streamlit */
div[role="radiogroup"] label { font-size: 24px !important; }
div[role="radiogroup"] p { font-size: 24px !important; }
</style>
""", unsafe_allow_html=True)

# ---------- utils ----------
def parse_br_number(x):
    if pd.isna(x): return np.nan
    if isinstance(x, (int, float, np.integer, np.floating)): return float(x)
    s = str(x).strip().replace("\xa0", "").replace(" ", "")
    for sym in ["R$", "%"]: s = s.replace(sym, "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # 1.234,56 -> 1234.56
        else:
            s = s.replace(",", "")                    # 1,234.56 -> 1234.56
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")      # 452,74 -> 452.74
    else:
        s = s.replace(",", "")
    return pd.to_numeric(s, errors="coerce")


def ler_abas_local(caminho: Path):
    return pd.read_excel(caminho, sheet_name=None, engine="openpyxl")


def preparar_df(df):
    # Garante nome da primeira coluna
    if df.columns[0] != "Regional":
        df = df.rename(columns={df.columns[0]: "Regional"})

    # Se a ÚLTIMA linha for de presença (coluna A contém "presen"), descarta
    ultima_rotulo = str(df.iloc[-1, 0]).lower()
    if "presen" in ultima_rotulo:
        df = df.iloc[:-1].copy()

    # Normaliza números nas colunas de avaliações
    aval_cols = list(df.columns[1:])
    for c in aval_cols:
        if not is_numeric_dtype(df[c]):
            df[c] = df[c].map(parse_br_number)

    # Longo
    df_long = df.melt(id_vars="Regional", value_vars=aval_cols,
                      var_name="Avaliação", value_name="Nota")
    df_long["Avaliação"] = pd.Categorical(df_long["Avaliação"],
                                          categories=aval_cols, ordered=True)
    return df_long


def montar_base(df_long, regional):
    base = df_long[df_long["Regional"] == regional].sort_values("Avaliação").copy()

    # Variações da nota
    base["Nota_anterior"] = base["Nota"].shift(1)
    base["Delta"] = base["Nota"] - base["Nota_anterior"]
    base["Delta_pct"] = (base["Delta"] / base["Nota_anterior"]) * 100

    def fsgn(x): return "—" if pd.isna(x) else f"{x:+.2f}"
    def fnum(x): return "—" if pd.isna(x) else f"{x:.2f}"

    # Rótulo VISÍVEL
    base["label_text"] = np.where(
        base["Nota_anterior"].isna(),
        base["Nota"].map(fnum).radd("Nota "),
        base.apply(lambda r: f"Nota {fnum(r['Nota'])} (Δ {fsgn(r['Delta'])}; {fsgn(r['Delta_pct'])}%)", axis=1)
    )

    # Tooltip
    base["hover_text"] = (
        "<b>" + base["Avaliação"].astype(str) + "</b>"
        + "<br>Nota: " + base["Nota"].map(fnum)
        + "<br>Variação Absoluta: " + base["Delta"].map(fsgn)
        + "<br>Variação Percentual: " + base["Delta_pct"].map(fsgn) + "%"
    )
    return base


def grafico(base, titulo):
    fig = px.line(base, x="Avaliação", y="Nota", markers=True, title=titulo)
    fig.update_traces(
        marker=dict(size=MARKER_SIZE),
        text=base["label_text"],
        textposition="top center",
        textfont=dict(size=FONT_SIZE),
        hovertext=base["hover_text"],
        hovertemplate="%{hovertext}<extra></extra>"
    )
    fig.update_layout(
        font=dict(size=FONT_SIZE),
        xaxis_title="Avaliação", yaxis_title="Nota",
        xaxis=dict(tickfont=dict(size=FONT_SIZE), title_font=dict(size=FONT_SIZE)),
        yaxis=dict(tickfont=dict(size=FONT_SIZE), title_font=dict(size=FONT_SIZE)),
        legend=dict(font=dict(size=FONT_SIZE)),
        hovermode="x unified",
        hoverlabel=dict(font_size=FONT_SIZE)  # só para garantir 24 no tooltip
    )
    return fig


# ---------- main ----------
if not EXCEL_PATH.exists():
    st.error(f"Arquivo não encontrado: {EXCEL_PATH.name}.")
    st.stop()

abas = ler_abas_local(EXCEL_PATH)
tab_names = list(abas.keys())

# Layout: coluna esquerda = navegação; direita = conteúdo
col_nav, col_main = st.columns([1, 4], gap="large")


with col_nav:
    st.markdown("")
    aba_sel = st.radio(
        label="Abas",               # sem label
        options=tab_names,
        index=0,
        key="aba_radio",
        label_visibility="collapsed"  # <— oculta o texto do rótulo
    )

with col_main:
    st.subheader(aba_sel)
    df_sheet = abas[aba_sel].copy()
    df_long = preparar_df(df_sheet)

    regionais = df_long["Regional"].dropna().unique()
    regional = st.selectbox(
        "Regional", 
        sorted(regionais), 
        key=f"reg_{aba_sel}",
        label_visibility="collapsed"       # ou "collapsed"/"hidden" se quiser ocultar
    )

    base = montar_base(df_long, regional)
    fig = grafico(base, f"")
    st.plotly_chart(fig, use_container_width=True)

#    with st.expander("Dados (somente notas)"):
#        mostrar = base[["Regional","Avaliação","Nota","Delta","Delta_pct"]].rename(
#            columns={"Delta_pct": "Delta_%"}
#        ).reset_index(drop=True)
#        st.dataframe(mostrar, use_container_width=True)

