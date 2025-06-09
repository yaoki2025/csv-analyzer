import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.font_manager as fm
import platform
import os
import io
from PIL import Image

# ===== フォント設定 =====
jp_font = None

def set_japanese_font():
    global jp_font
    system = platform.system()
    if system == "Darwin":
        font_path = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
    elif system == "Windows":
        font_path = "C:/Windows/Fonts/msgothic.ttc"
    else:
        font_path = "/usr/share/fonts/truetype/ipaexg/ipaexg.ttf"

    if os.path.exists(font_path):
        jp_font = fm.FontProperties(fname=font_path)
        plt.rcParams["font.family"] = jp_font.get_name()
    else:
        st.warning("日本語フォントが見つかりません。PDF出力で文字化けする可能性があります。")

set_japanese_font()

# ===== 図をPDFへ画像として保存 =====
def save_fig_as_image_to_pdf(fig, pdf):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    img = Image.open(buf)
    fig_img, ax_img = plt.subplots(figsize=(8, 6))
    ax_img.axis("off")
    ax_img.imshow(img)
    pdf.savefig(fig_img)
    plt.close(fig_img)
    buf.close()

# ===== 折れ線グラフ =====
def plot_line(x, y, title, xlabel, ylabel, pdf, color="blue", linewidth=0.8):
    fig, ax = plt.subplots()
    ax.plot(x, y, color=color, linewidth=linewidth, label="data")
    ax.set_title(title, fontproperties=jp_font)
    ax.set_xlabel(xlabel, fontproperties=jp_font)
    ax.set_ylabel(ylabel, fontproperties=jp_font)
    ax.legend()
    plt.setp(ax.get_xticklabels(), rotation=90)
    st.pyplot(fig)
    save_fig_as_image_to_pdf(fig, pdf)
    plt.close(fig)

# ===== 散布図 =====
def plot_scatter(x, y, title, xlabel, ylabel, pdf):
    fig, ax = plt.subplots()
    ax.scatter(x, y, alpha=0.5, label="scatter")
    ax.set_title(title, fontproperties=jp_font)
    ax.set_xlabel(xlabel, fontproperties=jp_font)
    ax.set_ylabel(ylabel, fontproperties=jp_font)
    ax.legend()
    plt.setp(ax.get_xticklabels(), rotation=90)
    st.pyplot(fig)
    save_fig_as_image_to_pdf(fig, pdf)
    plt.close(fig)

# ===== 2軸グラフ（温度と湿度） =====
def plot_dual_line(x, y1, y2, label1, label2, title, pdf):
    fig, ax1 = plt.subplots()

    ax1.plot(x, y1, color="red", label=label1, linewidth=0.8)
    ax1.set_xlabel("時刻", fontproperties=jp_font)
    ax1.set_ylabel(label1, color="red", fontproperties=jp_font)
    ax1.tick_params(axis='y', labelcolor="red")

    ax2 = ax1.twinx()
    ax2.plot(x, y2, color="green", label=label2, linewidth=0.8)
    ax2.set_ylabel(label2, color="green", fontproperties=jp_font)
    ax2.tick_params(axis='y', labelcolor="green")

    fig.suptitle(title, fontproperties=jp_font)
    plt.setp(ax1.get_xticklabels(), rotation=90)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    st.pyplot(fig)
    save_fig_as_image_to_pdf(fig, pdf)
    plt.close(fig)

# ===== メイン処理 =====
def analyze_and_plot(df, start_date, end_date):
    df["terminal_date"] = pd.to_datetime(df["terminal_date"])
    df_filtered = df[(df["terminal_date"] >= start_date) & (df["terminal_date"] <= end_date)].copy()

    if df_filtered.empty:
        st.warning("指定期間にデータがありませんでした。")
        return

    df_filtered["VPD"] = 0.6108 * np.exp((17.27 * df_filtered["temperature"]) / (df_filtered["temperature"] + 237.3))
    df_filtered["VPD"] -= df_filtered["VPD"] * df_filtered["humidity"] / 100

    stats = df_filtered[["temperature", "humidity", "co2", "rainfall", "VPD"]].describe().loc[["mean", "max", "min", "std"]]
    st.subheader("統計情報")
    st.dataframe(stats.round(2))

    pdf_path = "output_analysis.pdf"
    with PdfPages(pdf_path) as pdf:
        plot_line(df_filtered["terminal_date"], df_filtered["temperature"],
                  "温度の時間推移", "時刻", "温度 (°C)", pdf)
        plot_line(df_filtered["terminal_date"], df_filtered["humidity"],
                  "湿度の時間推移", "時刻", "湿度 (%)", pdf, color="green")
        plot_scatter(df_filtered["temperature"], df_filtered["humidity"],
                     "温度 vs 湿度", "温度 (°C)", "湿度 (%)", pdf)
        plot_line(df_filtered["terminal_date"], df_filtered["VPD"],
                  "飽差 (VPD) の時間推移", "時刻", "VPD (kPa)", pdf, color="purple")
        plot_dual_line(df_filtered["terminal_date"], df_filtered["temperature"], df_filtered["humidity"],
                       "温度 (°C)", "湿度 (%)", "温度と湿度の時間推移（重ね描き）", pdf)

    st.success("📄 PDFファイルを保存しました：`output_analysis.pdf`")
    with open(pdf_path, "rb") as f:
        st.download_button("📥 PDFをダウンロード", f, file_name="output_analysis.pdf", mime="application/pdf")

# ===== Streamlit UI =====
st.title("📈 CSVデータ分析ツール")

uploaded_file = st.file_uploader("CSVファイルを選んでください", type="csv")
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    if "terminal_date" not in df.columns:
        st.error("❌ terminal_date列が見つかりません。")
    else:
        df["terminal_date"] = pd.to_datetime(df["terminal_date"])
        min_date = df["terminal_date"].min().date()
        max_date = df["terminal_date"].max().date()

        start_date = st.date_input("📅 開始日", value=min_date, min_value=min_date, max_value=max_date)
        end_date = st.date_input("📅 終了日", value=max_date, min_value=min_date, max_value=max_date)

        if start_date > end_date:
            st.error("❌ 開始日は終了日より前にしてください。")
        else:
            if st.button("🚀 分析開始！"):
                analyze_and_plot(df, pd.to_datetime(start_date), pd.to_datetime(end_date))