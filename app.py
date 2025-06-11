import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.font_manager as fm
import os
import io
from PIL import Image

# ===== フォント設定 =====
jp_font = None

def set_japanese_font():
    global jp_font
    font_path = os.path.join(os.path.dirname(__file__), "ipaexg.ttf")
    if os.path.exists(font_path):
        jp_font = fm.FontProperties(fname=font_path)
        plt.rcParams["font.family"] = jp_font.get_name()
    else:
        st.warning("日本語フォントが見つかりません。PDF出力で文字化けする可能性があります。")

set_japanese_font()

# ===== ユーザー入力で理想範囲を定義 =====
st.sidebar.header("理想値の設定")
IDEAL_RANGES = {
    "temperature": (
        st.sidebar.number_input("温度 最低 (°C)", value=20),
        st.sidebar.number_input("温度 最高 (°C)", value=28)
    ),
    "humidity": (
        st.sidebar.number_input("湿度 最低 (%)", value=60),
        st.sidebar.number_input("湿度 最高 (%)", value=80)
    ),
    "VPD": (
        st.sidebar.number_input("VPD 最低 (kPa)", value=0.6),
        st.sidebar.number_input("VPD 最高 (kPa)", value=1.2)
    ),
    "underground_temperature": (
        st.sidebar.number_input("土壌温度 最低 (°C)", value=18),
        st.sidebar.number_input("土壌温度 最高 (°C)", value=25)
    ),
    "underground_water_content": (
        st.sidebar.number_input("土壌水分 最低 (%)", value=30),
        st.sidebar.number_input("土壌水分 最高 (%)", value=60)
    )
}

# ===== PDF保存用関数 =====
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

# ===== 共通描画関数 =====
def plot_line(x, y, title, xlabel, ylabel, pdf, color="blue", linewidth=0.8, ideal_range=None):
    fig, ax = plt.subplots()
    ax.plot(x, y, color=color, linewidth=linewidth, label="data")
    if ideal_range:
        ax.axhspan(ideal_range[0], ideal_range[1], color=color, alpha=0.1, label="ideal_range")
    ax.set_title(title, fontproperties=jp_font)
    ax.set_xlabel(xlabel, fontproperties=jp_font)
    ax.set_ylabel(ylabel, fontproperties=jp_font)
    ax.legend()
    plt.setp(ax.get_xticklabels(), rotation=90)
    st.pyplot(fig)
    save_fig_as_image_to_pdf(fig, pdf)
    plt.close(fig)

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

# ===== 分析処理 =====
def analyze_and_plot(df, start_date, end_date):
    df["terminal_date"] = pd.to_datetime(df["terminal_date"])
    df = df[(df["terminal_date"] >= start_date) & (df["terminal_date"] <= end_date)].copy()
    if df.empty:
        st.warning("指定期間にデータがありません。")
        return

    df["VPD"] = 0.6108 * np.exp((17.27 * df["temperature"]) / (df["temperature"] + 237.3))
    df["VPD"] -= df["VPD"] * df["humidity"] / 100
    df["temp_diff"] = df["temperature"] - df["underground_temperature"]
    df["temp_sum"] = df["temperature"] + df["underground_temperature"]
    df["soil_moisture_diff"] = df["underground_water_content"].diff()
    df["soil_moisture_diff_abs"] = df["soil_moisture_diff"].abs()
    df["soil_moisture_1st_deriv"] = df["underground_water_content"].diff()
    threshold = IDEAL_RANGES["underground_water_content"][0]
    df["dry_count"] = (df["underground_water_content"] < threshold).astype(int)
    df["dry_streak"] = df["dry_count"].groupby((df["dry_count"] != df["dry_count"].shift()).cumsum()).cumsum()
    df["soil_temp_range"] = df["underground_temperature"].rolling("1D", on="terminal_date").apply(lambda x: x.max() - x.min())
    df["all_ok"] = True
    for col, (low, high) in IDEAL_RANGES.items():
        df["all_ok"] &= (df[col] >= low) & (df[col] <= high)

    st.subheader("統計情報")
    cols = list(IDEAL_RANGES.keys())
    stats = df[cols].describe().loc[["mean", "max", "min", "std"]]
    st.dataframe(stats.round(2))

    st.subheader("理想範囲に入っている割合")
    col1, col2 = st.columns(2)
    for i, col in enumerate(cols):
        low, high = IDEAL_RANGES[col]
        total = df[col].notnull().sum()
        in_range = df[(df[col] >= low) & (df[col] <= high)][col].count()
        percent = round(in_range / total * 100, 1) if total else 0
        (col1 if i % 2 == 0 else col2).metric(label=col, value=f"{percent} %")

    st.subheader("総合スコア")
    percent = round(df["all_ok"].sum() / len(df) * 100, 1)
    st.metric("全項目が理想範囲内の割合", f"{percent} %")

    with PdfPages("output_analysis.pdf") as pdf:
        plot_line(df["terminal_date"], df["temp_diff"], "温度と地温の乖離", "時刻", "気温 - 地温 (°C)", pdf, color="red")
        plot_line(df["terminal_date"], df["temp_sum"], "気温と地温の合計", "時刻", "気温 + 地温 (°C)", pdf, color="purple")
        plot_line(df["terminal_date"], df["soil_moisture_diff_abs"], "潅水後の保水持続性（絶対変化量）", "時刻", "水分変化 (%)", pdf, color="brown")
        plot_line(df["terminal_date"], df["soil_moisture_1st_deriv"], "水分減少速度（一次微分）", "時刻", "水分微分値", pdf, color="blue")
        plot_line(df["terminal_date"], df["dry_streak"], "連続乾燥時間カウント", "時刻", "連続乾燥時間 (回)", pdf, color="orange")
        plot_line(df["terminal_date"], df["soil_temp_range"], "地温の日内変動幅", "時刻", "日内変動幅 (°C)", pdf, color="green")
        for col in IDEAL_RANGES:
            plot_line(df["terminal_date"], df[col], f"{col} の時間推移", "時刻", col, pdf, color="gray", ideal_range=IDEAL_RANGES[col])
        plot_scatter(df["temperature"], df["humidity"], "温度 vs 湿度", "温度", "湿度", pdf)
        plot_scatter(df["underground_water_content"], df["underground_temperature"], "土壌水分 vs 地温", "水分", "地温", pdf)
        for x, y in [("temperature", "humidity"), ("underground_water_content", "underground_temperature")]:
            corr = df[[x, y]].corr().iloc[0, 1].round(3)
            st.write(f"{x} と {y} の相関係数: {corr}")

    st.success("PDFファイルを保存しました: output_analysis.pdf")
    with open("output_analysis.pdf", "rb") as f:
        st.download_button("PDFをダウンロード", f, file_name="output_analysis.pdf", mime="application/pdf")

# ===== Streamlit UI =====
st.title("CSVデータ分析ツールv1.1")

uploaded_file = st.file_uploader("CSVファイルを選んでください", type="csv")
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    if "terminal_date" not in df.columns:
        st.error("terminal_date列が見つかりません。CSVを確認してください。")
    else:
        df["terminal_date"] = pd.to_datetime(df["terminal_date"])
        min_date = df["terminal_date"].min().date()
        max_date = df["terminal_date"].max().date()
        start_date = st.date_input("開始日", value=min_date, min_value=min_date, max_value=max_date)
        end_date = st.date_input("終了日", value=max_date, min_value=min_date, max_value=max_date)
        if start_date > end_date:
            st.error("開始日は終了日より前にしてください。")
        else:
            if st.button("分析開始！"):
                analyze_and_plot(df, pd.to_datetime(start_date), pd.to_datetime(end_date))
