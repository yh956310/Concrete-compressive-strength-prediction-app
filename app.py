import streamlit as st
import numpy as np
import pandas as pd
import pickle
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'DejaVu Sans'

# ── 페이지 설정 ──────────────────────────────────────────
st.set_page_config(page_title="콘크리트 압축강도 예측", page_icon="🏗️", layout="wide")

st.title("🏗️ 콘크리트 압축강도 예측 시스템")
st.markdown("배합비와 양생 온도이력을 입력하면 **재령별 압축강도**와 **90% 신뢰구간**을 예측합니다.")

# ── 모델 로드 ─────────────────────────────────────────────
@st.cache_resource
def load_models():
    model_Su   = pickle.load(open('model/model_Su.pkl','rb'))
    t0_by_temp = pickle.load(open('model/t0_by_temp.pkl','rb'))
    df_params  = pd.read_csv('model/params_fitted.csv')
    return model_Su, t0_by_temp, df_params

model_Su, t0_by_temp, df_params = load_models()

# T-TaAE 상수
R_GAS   = 8.3144
A_CONST = 1e7
E0_FIXED    = 42466.0   # J/mol (평균값)
ALPHA_FIXED = 0.0076    # (평균값)
SU_RMSE     = 5.2       # MPa (학습 RMSE)

# ── T-TaAE 모델 함수 ──────────────────────────────────────
def calc_equivalent_age(temp_history, E0=E0_FIXED, Tr=20.0):
    """Arrhenius 등가재령 계산 (일 단위, 일별 온도 입력)"""
    te = 0.0
    for T in temp_history:
        dt = 1.0  # 1일 간격
        factor = np.exp(-E0 / R_GAS * (1/(T+273.15) - 1/(Tr+273.15)))
        te += factor * dt
    return te

def t_taae_strength(te, Su, E0, alpha, t0, T_avg):
    """T-TaAE 강도 예측"""
    T_K = T_avg + 273.15
    inner = A_CONST * (
        np.exp(-E0 * np.exp(-alpha * te) / (R_GAS * T_K)) +
        np.exp(-E0 * np.exp(-alpha * t0) / (R_GAS * T_K))
    ) * max(te - t0, 0)
    if inner < 0: inner = 0
    return Su * (1 - 1 / np.sqrt(1 + inner))

def get_t0_from_temp(avg_temp, t0_by_temp):
    """온도에 따른 t0 보간"""
    temps = sorted(t0_by_temp.keys())
    t0s   = [t0_by_temp[t] for t in temps]
    return float(np.interp(avg_temp, temps, t0s))

# ── 사이드바: 배합비 입력 ─────────────────────────────────
st.sidebar.header("📐 배합비 입력")

w_b   = st.sidebar.slider("물-결합재비 (W/B)", 0.30, 0.65, 0.45, 0.01)
fa_b  = st.sidebar.slider("플라이애시비 (FA/B)", 0.00, 0.40, 0.10, 0.01)
bfs_b = st.sidebar.slider("고로슬래그비 (BFS/B)", 0.00, 0.60, 0.15, 0.01)

# 유효성 검사
if fa_b + bfs_b >= 1.0:
    st.sidebar.error("⚠️ FA/B + BFS/B 합이 1.0 미만이어야 합니다.")
    st.stop()

# 단위량 추정 (binder 추정: 평균 수준)
binder_est = 350.0   # kg/m³ 기준 (평균)
water_est  = w_b * binder_est

# Su 예측
features_su = np.array([[w_b, fa_b, bfs_b, water_est, binder_est]])
Su_pred = float(model_Su.predict(features_su)[0])
Su_pred = max(Su_pred, 10.0)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**예측 극한강도 (Su):** `{Su_pred:.1f} MPa`")
st.sidebar.markdown(f"**90% 구간:** `{Su_pred-1.645*SU_RMSE:.1f} ~ {Su_pred+1.645*SU_RMSE:.1f} MPa`")

# ── 메인: 온도이력 입력 ───────────────────────────────────
st.header("🌡️ 양생 온도 이력 설정")
st.markdown("구간별 기간과 온도를 설정하세요. (전체 예측 범위: **0 ~ 91일**)")

# ── 구간 기간 설정 ────────────────────────────────────────
st.markdown("**① 구간 기간 설정**")
col_p1, col_p2, col_p3 = st.columns(3)

with col_p1:
    st.markdown("**초기 (Early)**")
    st.markdown("시작: `Day 0` (고정)")
    early_end = st.number_input("종료일 (day)", min_value=1, max_value=89, value=7, step=1, key="early_end")

with col_p2:
    st.markdown("**중기 (Mid)**")
    st.markdown(f"시작: `Day {early_end}` (자동)")
    mid_end = st.number_input("종료일 (day)", min_value=early_end+1, max_value=90, value=min(28, early_end+1), step=1, key="mid_end")
    mid_end = max(mid_end, early_end + 1)

with col_p3:
    st.markdown("**후기 (Late)**")
    st.markdown(f"시작: `Day {mid_end}` (자동)")
    st.markdown("종료: `Day 91` (고정)")

# ── 구간 온도 설정 ────────────────────────────────────────
st.markdown("**② 구간 온도 설정**")
c1, c2, c3 = st.columns(3)
with c1:
    t_early = st.slider(f"초기 온도 (Day 0 ~ {early_end})", 0, 40, 20, 1)
with c2:
    t_mid   = st.slider(f"중기 온도 (Day {early_end} ~ {mid_end})", 0, 40, 20, 1)
with c3:
    t_late  = st.slider(f"후기 온도 (Day {mid_end} ~ 91)", 0, 40, 20, 1)

# 온도이력 배열 생성 (91일)
temp_history = (
    [t_early] * early_end +
    [t_mid]   * (mid_end - early_end) +
    [t_late]  * (91 - mid_end)
)

# ── 강도 예측 및 그래프 ───────────────────────────────────
st.header("📊 압축강도 예측 결과")

ages = np.arange(1, 92)  # 1~91일 예측
avg_temp = np.mean(temp_history)
t0 = get_t0_from_temp(avg_temp, t0_by_temp)

# 등가재령 계산 (일별)
te_by_day = []
te = 0.0
T_ref = 20.0
for d in range(1, 92):
    T_d = temp_history[min(d-1, 90)]
    factor = np.exp(-E0_FIXED / R_GAS * (1/(T_d+273.15) - 1/(T_ref+273.15)))
    te += factor
    te_by_day.append(te)

# 강도 예측 (중앙값 + 90% 구간)
Su_low  = Su_pred - 1.645 * SU_RMSE
Su_high = Su_pred + 1.645 * SU_RMSE
Su_low  = max(Su_low, 5.0)

strengths_mid  = []
strengths_low  = []
strengths_high = []

for i, te in enumerate(te_by_day):
    T_d = temp_history[min(i, 90)]
    s_mid  = t_taae_strength(te, Su_pred, E0_FIXED, ALPHA_FIXED, t0, T_d)
    s_low  = t_taae_strength(te, Su_low,  E0_FIXED, ALPHA_FIXED, t0, T_d)
    s_high = t_taae_strength(te, Su_high, E0_FIXED, ALPHA_FIXED, t0, T_d)
    strengths_mid.append(max(s_mid, 0))
    strengths_low.append(max(s_low, 0))
    strengths_high.append(max(s_high, 0))

# ── 그래프 ────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# Left: Strength-Age curve
ax1.fill_between(ages, strengths_low, strengths_high,
                 alpha=0.25, color='steelblue', label='90% Confidence Interval')
ax1.plot(ages, strengths_mid, 'b-', linewidth=2.5, label='Predicted Strength (Median)')
ax1.axvline(x=28, color='red', linestyle='--', alpha=0.5, linewidth=1.5, label='Day 28')
ax1.set_xlabel('Age (days)', fontsize=12)
ax1.set_ylabel('Compressive Strength (MPa)', fontsize=12)
ax1.set_title('Compressive Strength vs. Age', fontsize=13, fontweight='bold')
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.set_xlim(0, 91)
ax1.set_ylim(0, max(strengths_high)*1.15)

# Right: Temperature history
days_temp = list(range(0, 92))
temp_plot = temp_history + [temp_history[-1]]
ax2.step(days_temp, temp_plot, where='post', color='orangered', linewidth=2.5)
ax2.fill_between(days_temp, temp_plot, step='post', alpha=0.15, color='orangered')
# 구간 경계선 표시
ax2.axvline(x=early_end, color='gray', linestyle='--', alpha=0.6, linewidth=1.2)
ax2.axvline(x=mid_end,   color='gray', linestyle='--', alpha=0.6, linewidth=1.2)
ax2.text(early_end/2,      42, 'Early', ha='center', fontsize=9, color='gray')
ax2.text((early_end+mid_end)/2, 42, 'Mid',   ha='center', fontsize=9, color='gray')
ax2.text((mid_end+91)/2,   42, 'Late',  ha='center', fontsize=9, color='gray')
ax2.set_xlabel('Age (days)', fontsize=12)
ax2.set_ylabel('Curing Temperature (°C)', fontsize=12)
ax2.set_title('Curing Temperature History', fontsize=13, fontweight='bold')
ax2.set_xlim(0, 91)
ax2.set_ylim(0, 45)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
st.pyplot(fig)
plt.close()

# ── 특정 재령 강도 조회 ───────────────────────────────────
st.header("🔍 특정 재령 강도 조회")
col1, col2 = st.columns([1, 2])
with col1:
    query_age = st.number_input("조회 재령 (일)", 1, 91, 28, 1)
with col2:
    idx = query_age - 1
    s_m = strengths_mid[idx];  s_l = strengths_low[idx];  s_h = strengths_high[idx]
    st.metric(label=f"재령 {query_age}일 예측 강도",
              value=f"{s_m:.1f} MPa",
              delta=f"90% 구간: {s_l:.1f} ~ {s_h:.1f} MPa")

# ── 주요 재령 요약 테이블 ─────────────────────────────────
key_ages = [1, 3, 7, 14, 28, 56, 91]
summary = []
for a in key_ages:
    i = a - 1
    summary.append({'재령(일)': a,
                    '예측 강도(MPa)': f"{strengths_mid[i]:.1f}",
                    '90% 하한(MPa)': f"{strengths_low[i]:.1f}",
                    '90% 상한(MPa)': f"{strengths_high[i]:.1f}"})
st.table(pd.DataFrame(summary))

st.markdown("---")
st.caption("📌 본 예측은 T-TaAE 모델 (Kim et al., 2001) + XGBoost ML 기반입니다. | Chosun University")
