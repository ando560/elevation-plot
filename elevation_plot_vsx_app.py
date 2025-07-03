import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
from astropy.time import Time
import astropy.units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from astropy import units as u

st.set_page_config(page_title="天体高度プロット（VSX版）", layout="wide")

# --- VSXから座標を取得 ---
def get_coordinates(target_name):
    try:
        # 通常の名前解決を試みる
        coord = SkyCoord.from_name(target_name)
        return coord
    except Exception:
        # VSX API を使って解決を試みる
        try:
            url = f"https://www.aavso.org/vsx/index.php?view=api.delim&ident={target_name}&delimiter=;"
            response = requests.get(url)
            if response.status_code == 200 and "RA;" in response.text:
                lines = response.text.splitlines()
                ra = dec = None
                for line in lines:
                    if line.startswith("RA;"):
                        _, ra_str = line.split(";", 1)
                        ra = float(ra_str)
                    elif line.startswith("DEC;"):
                        _, dec_str = line.split(";", 1)
                        dec = float(dec_str)
                if ra is not None and dec is not None:
                    coord = SkyCoord(ra=ra * u.hourangle, dec=dec * u.deg, frame='icrs')
                    return coord
        except Exception as vsx_error:
            print(f"VSX 解決エラー: {vsx_error}")
        raise ValueError(f"{target_name} の座標が見つかりませんでした。")


# --- 既定の天体 ---
default_targets = {
    "AG Peg": ("21 51 01.9", "+12 37 32"),
    "AX Per": ("01 36 22.7", "+54 15 02"),
    "SS Lep": ("06 04 59.28", "-16 29 04"),
    "V694 Mon": ("07 25 51", "-07 44 08.1")
}
# --- カスタム天体の状態保持 ---
if "custom_targets" not in st.session_state:
    st.session_state["custom_targets"] = {}
custom_targets = st.session_state["custom_targets"]

# --- UI: カスタム天体追加 ---
st.sidebar.subheader("🌟 カスタム天体を追加（VSXから検索）")
with st.sidebar.form("custom_star_form"):
    custom_name = st.text_input("天体名（例: T CrB）", value="My Star")
    fetch_btn = st.form_submit_button("🔍 VSXから座標を取得")

    if fetch_btn and custom_name:
        try:
            coord = get_coordinates(custom_name)
            ra_str = coord.ra.to_string(unit=u.hour, sep=':', precision=2)
            dec_str = coord.dec.to_string(unit=u.deg, sep=':', precision=1, alwayssign=True)
            st.session_state["custom_ra"] = ra_str
            st.session_state["custom_dec"] = dec_str
            st.success(f"{custom_name} の座標を取得しました")
        except Exception as e:
            st.error(f"座標の取得に失敗しました: {e}")
            st.warning(f"⚠️ VSXで {custom_name} が見つかりませんでした。RA/Dec を手動で入力してください。")

    ra_input = st.text_input("RA（時 分 秒）", value=st.session_state.get("custom_ra", "12 34 56.7"))
    dec_input = st.text_input("Dec（度 分 秒）", value=st.session_state.get("custom_dec", "+12 34 56"))
    submit_btn = st.form_submit_button("➕ この天体を追加")

    if submit_btn:
        if custom_name and ra_input and dec_input:
            custom_targets[custom_name] = (ra_input, dec_input)
            st.success(f"{custom_name} をリストに追加しました")
        else:
            st.warning("⚠️ 名前・RA・Decをすべて入力してください")

# --- 観測天体選択 ---
all_targets = {**default_targets, **custom_targets}
selected_targets = st.multiselect(
    "観測天体を選択",
    list(all_targets.keys()),
    default=list(default_targets.keys())
)

# --- 観測設定 ---
dates = st.text_input("観測日（カンマ区切り）", "2025-09-26,2025-10-03")
lat = st.number_input("緯度", value=34.655)
lon = st.number_input("経度", value=133.583)
height = st.number_input("標高 [m]", value=500)
start_hour = st.number_input("開始時刻（JST）", value=23)
end_hour = st.number_input("終了時刻（JST）", value=28)

# --- プロット ---
if st.button("📈 プロット表示"):
    try:
        coord = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=height * u.m)
        delta_minutes = np.arange(start_hour * 60, end_hour * 60)
        delta_time = delta_minutes * u.minute

        for date in [d.strip() for d in dates.split(",") if d.strip()]:
            time_utc = Time(date + " 00:00:00") + delta_time - 9 * u.hour
            frame = AltAz(obstime=time_utc, location=coord)

            fig, ax = plt.subplots(figsize=(10, 6))
            for name in selected_targets:
                ra, dec = all_targets[name]
                sc = SkyCoord(ra=ra, dec=dec, unit=(u.hourangle, u.deg))
                altaz = sc.transform_to(frame)
                el = altaz.alt.deg
                time_label = delta_minutes / 60
                ax.plot(time_label, el, label=name)

            ax.set_title(f"Elevation on {date} [JST]")
            ax.set_xlabel("Time [hour]")
            ax.set_ylabel("Elevation [deg]")
            ax.set_xlim(start_hour, end_hour)
            ax.set_ylim(0, 90)
            ax.legend()
            ax.grid(True)
            plt.tight_layout()
            st.pyplot(fig)

    except Exception as e:
        st.error(f"エラー: {e}")