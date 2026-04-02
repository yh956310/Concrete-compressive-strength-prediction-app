import streamlit as st
import numpy as np
import pandas as pd
import pickle
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'DejaVu Sans'

st.set_page_config(page_title="Concrete Strength Predictor", page_icon="🏗️", layout="wide")

# ── 언어 선택 ─────────────────────────────────────────────
st.sidebar.markdown("### 🌐 Language")
col_lang1, col_lang2 = st.sidebar.columns(2)
with col_lang1:
    if st.button("🇰🇷 한국어", use_container_width=True):
        st.session_state['lang'] = 'ko'
with col_lang2:
    if st.button("🇺🇸 English", use_container_width=True):
        st.session_state['lang'] = 'en'

if 'lang' not in st.session_state:
    st.session_state['lang'] = 'ko'
lang = st.session_state['lang']

# ── 텍스트 사전 ───────────────────────────────────────────
T = {
    'title':         {'ko': '🏗️ 콘크리트 압축강도 예측 시스템',       'en': '🏗️ Concrete Compressive Strength Predictor'},
    'subtitle':      {'ko': '배합비와 양생 온도이력을 입력하면 **재령별 압축강도**와 **90% 신뢰구간**을 예측합니다.',
                      'en': 'Enter mix proportions and curing temperature history to predict **compressive strength** and **90% confidence interval**.'},
    'mix_header':    {'ko': '📐 배합비 입력',           'en': '📐 Mix Proportions'},
    'wb':            {'ko': '물-결합재비 (W/B)',         'en': 'Water-Binder Ratio (W/B)'},
    'fab':           {'ko': '플라이애시비 (FA/B)',        'en': 'Fly Ash Ratio (FA/B)'},
    'bfsb':          {'ko': '고로슬래그비 (BFS/B)',      'en': 'GGBFS Ratio (BFS/B)'},
    'fa_bfs_err':    {'ko': '⚠️ FA/B + BFS/B 합이 1.0 미만이어야 합니다.', 'en': '⚠️ FA/B + BFS/B must be less than 1.0.'},
    'su_label':      {'ko': '**예측 극한강도 (Su):**',   'en': '**Predicted Ultimate Strength (Su):**'},
    'ci_label':      {'ko': '**90% 구간:**',             'en': '**90% Interval:**'},
    'temp_header':   {'ko': '🌡️ 양생 온도 이력 설정',   'en': '🌡️ Curing Temperature History'},
    'temp_subtitle': {'ko': '구간별 기간과 온도를 설정하세요. (전체 예측 범위: **0 ~ 91일**)',
                      'en': 'Set duration and temperature for each period. (Prediction range: **Day 0 ~ 91**)'},
    'period_title':  {'ko': '**① 구간 기간 설정**',      'en': '**① Set Period Duration**'},
    'temp_title':    {'ko': '**② 구간 온도 설정**',      'en': '**② Set Period Temperature**'},
    'early':         {'ko': '**초기 (Early)**',          'en': '**Early Period**'},
    'mid':           {'ko': '**중기 (Mid)**',            'en': '**Mid Period**'},
    'late':          {'ko': '**후기 (Late)**',           'en': '**Late Period**'},
    'start':         {'ko': '시작',   'en': 'Start'},
    'end':           {'ko': '종료',   'en': 'End'},
    'fixed':         {'ko': '(고정)', 'en': '(fixed)'},
    'auto':          {'ko': '(자동)', 'en': '(auto)'},
    'end_day':       {'ko': '종료일 (day)', 'en': 'End day'},
    'early_temp':    {'ko': '초기 온도',    'en': 'Early Temp.'},
    'mid_temp':      {'ko': '중기 온도',    'en': 'Mid Temp.'},
    'late_temp':     {'ko': '후기 온도',    'en': 'Late Temp.'},
    'result_header': {'ko': '📊 압축강도 예측 결과',      'en': '📊 Prediction Results'},
    'query_header':  {'ko': '🔍 특정 재령 강도 조회',     'en': '🔍 Strength at Specific Age'},
    'query_age':     {'ko': '조회 재령 (일)',             'en': 'Age to query (days)'},
    'metric_label':  {'ko': '예측 강도',                 'en': 'Predicted Strength'},
    'ci_delta':      {'ko': '90% 구간',                  'en': '90% Interval'},
    'table_age':     {'ko': '재령(일)',        'en': 'Age (days)'},
    'table_pred':    {'ko': '예측 강도(MPa)',  'en': 'Strength (MPa)'},
    'table_low':     {'ko': '90% 하한(MPa)',  'en': '90% Lower (MPa)'},
    'table_high':    {'ko': '90% 상한(MPa)',  'en': '90% Upper (MPa)'},
    'graph_strength_title': {'ko': '재령별 압축강도 예측',   'en': 'Compressive Strength vs. Age'},
    'graph_temp_title':     {'ko': '양생 온도 이력',         'en': 'Curing Temperature History'},
    'graph_ci':             {'ko': '90% 신뢰구간',           'en': '90% Confidence Interval'},
    'graph_pred':           {'ko': '예측 강도 (중앙값)',      'en': 'Predicted Strength (Median)'},
    'graph_age':            {'ko': '재령 (일)',              'en': 'Age (days)'},
    'graph_cs':             {'ko': '압축강도 (MPa)',         'en': 'Compressive Strength (MPa)'},
    'graph_temp_y':         {'ko': '양생 온도 (°C)',         'en': 'Curing Temperature (°C)'},
    'caption': {
        'ko': '📌 본 예측은 T-TaAE 모델 (Kim et al., 2001) + XGBoost ML 기반입니다. 총 6,635개의 실험데이터로부터 확보한 결과를 이용했습니다. | Prof. Hyeongki Kim (Chosun University)',
        'en': '📌 Predictions based on T-TaAE model (Kim et al., 2001) + XGBoost ML, utilizing results obtained from 6,635 experimental data points. | Prof. Hyeongki Kim (Chosun University)'
    },
}

def t_(key): return T[key][lang]

# ── 모델 로드 ─────────────────────────────────────────────
@st.cache_resource
def load_models():
    model_corr = pickle.load(open('model/model_correction.pkl', 'rb'))
    t0_by_temp = pickle.load(open('model/t0_by_temp.pkl',       'rb'))
    df_params  = pd.read_csv('model/params_fitted.csv')
    return model_corr, t0_by_temp, df_params

model_corr, t0_by_temp, df_params = load_models()

R_GAS=8.3144; A_CONST=1e7; E0_FIXED=42466.0; ALPHA_FIXED=0.0076

def t_taae_strength(te, Su, E0, alpha, t0, T_avg):
    T_K   = T_avg + 273.15
    inner = A_CONST*(np.exp(-E0*np.exp(-alpha*te)/(R_GAS*T_K))+
                     np.exp(-E0*np.exp(-alpha*t0)/(R_GAS*T_K)))*max(te-t0,0)
    return Su*(1-1/np.sqrt(1+max(inner,0)))

def get_t0_from_temp(avg_temp, t0_by_temp):
    temps=sorted(t0_by_temp.keys()); t0s=[t0_by_temp[t] for t in temps]
    return float(np.interp(avg_temp, temps, t0s))

# ── 타이틀 ────────────────────────────────────────────────
st.title(t_('title'))
st.markdown(t_('subtitle'))

# ── 사이드바: 배합비 ──────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.header(t_('mix_header'))

# 구속 조건 안내
st.sidebar.caption("⚠️ Constrained within training data range" if lang=='en' else "⚠️ 학습 데이터 범위 내로 제한됨")

w_b  = st.sidebar.slider(t_('wb'),  0.30, 0.65, 0.45, 0.01)

# FA/B: 0 ~ 0.40 고정 한계
fa_b = st.sidebar.slider(t_('fab'), 0.00, 0.40, 0.10, 0.01)

# BFS/B: FA/B에 따라 상한 동적 결정 (FA/B + BFS/B ≤ 0.60)
bfs_max = round(min(0.40, 0.60 - fa_b), 2)
bfs_b   = st.sidebar.slider(t_('bfsb'), 0.00, bfs_max,
                              min(0.15, bfs_max), 0.01)

# 합계 표시
scm_total = fa_b + bfs_b
bar_pct   = int(scm_total / 0.60 * 100)
st.sidebar.markdown(
    f"**FA/B + BFS/B = `{scm_total:.2f}`** / 0.60 max"
)
st.sidebar.progress(bar_pct)

if scm_total > 0.55:
    st.sidebar.warning("⚠️ Approaching data limit!" if lang=='en' else "⚠️ 학습 데이터 한계에 근접!")

if fa_b + bfs_b >= 1.0:
    st.sidebar.error(t_('fa_bfs_err')); st.stop()

# 교수님 경험식 기반 Su 예측: fc,28 = 73.6 × exp(-0.015 × W/B%)
# FA/B, BFS/B 보정계수 적용 (단위수량 175 kg/m³ 고정 가정)
fc_base  = 73.6 * np.exp(-0.015 * w_b * 100)
corr     = float(model_corr.predict([[fa_b, bfs_b, fa_b*bfs_b]])[0])
Su_pred  = max(fc_base * corr, 10.0)
SU_RMSE  = 6.8   # MPa (전체 데이터 기반 RMSE)

st.sidebar.markdown("---")
st.sidebar.markdown(f"{t_('su_label')} `{Su_pred:.1f} MPa`")
st.sidebar.markdown(f"{t_('ci_label')} `{Su_pred-1.645*SU_RMSE:.1f} ~ {Su_pred+1.645*SU_RMSE:.1f} MPa`")

# ── 온도이력 입력 ─────────────────────────────────────────
st.header(t_('temp_header'))
st.markdown(t_('temp_subtitle'))

st.markdown(t_('period_title'))
col_p1, col_p2, col_p3 = st.columns(3)
with col_p1:
    st.markdown(t_('early'))
    st.markdown(f"{t_('start')}: `Day 0` {t_('fixed')}")
    early_end=st.number_input(t_('end_day'),min_value=1,max_value=89,value=7,step=1,key="early_end")
with col_p2:
    st.markdown(t_('mid'))
    st.markdown(f"{t_('start')}: `Day {early_end}` {t_('auto')}")
    mid_end=st.number_input(t_('end_day'),min_value=early_end+1,max_value=90,
                            value=min(28,early_end+1),step=1,key="mid_end")
    mid_end=max(mid_end,early_end+1)
with col_p3:
    st.markdown(t_('late'))
    st.markdown(f"{t_('start')}: `Day {mid_end}` {t_('auto')}")
    st.markdown(f"{t_('end')}: `Day 91` {t_('fixed')}")

st.markdown(t_('temp_title'))
c1,c2,c3=st.columns(3)
with c1: t_early=st.slider(f"{t_('early_temp')} (Day 0~{early_end})",0,40,20,1)
with c2: t_mid  =st.slider(f"{t_('mid_temp')} (Day {early_end}~{mid_end})",0,40,20,1)
with c3: t_late =st.slider(f"{t_('late_temp')} (Day {mid_end}~91)",0,40,20,1)

temp_history=[t_early]*early_end+[t_mid]*(mid_end-early_end)+[t_late]*(91-mid_end)

# ── 강도 예측 ─────────────────────────────────────────────
st.header(t_('result_header'))
ages=np.arange(1,92)
avg_temp=np.mean(temp_history)
t0=get_t0_from_temp(avg_temp,t0_by_temp)
Su_low=max(Su_pred-1.645*SU_RMSE,5.0); Su_high=Su_pred+1.645*SU_RMSE

te_by_day=[]; te=0.0
for d in range(1,92):
    T_d=temp_history[min(d-1,90)]
    te+=np.exp(-E0_FIXED/R_GAS*(1/(T_d+273.15)-1/(20+273.15)))
    te_by_day.append(te)

strengths_mid,strengths_low,strengths_high=[],[],[]
for i,te in enumerate(te_by_day):
    T_d=temp_history[min(i,90)]
    strengths_mid.append(max(t_taae_strength(te,Su_pred,E0_FIXED,ALPHA_FIXED,t0,T_d),0))
    strengths_low.append(max(t_taae_strength(te,Su_low, E0_FIXED,ALPHA_FIXED,t0,T_d),0))
    strengths_high.append(max(t_taae_strength(te,Su_high,E0_FIXED,ALPHA_FIXED,t0,T_d),0))

# ── 그래프 ────────────────────────────────────────────────
fig,(ax1,ax2)=plt.subplots(1,2,figsize=(14,5))
ax1.fill_between(ages,strengths_low,strengths_high,alpha=0.25,color='steelblue',label='90% Confidence Interval')
ax1.plot(ages,strengths_mid,'b-',linewidth=2.5,label='Predicted Strength (Median)')
ax1.axvline(x=28,color='red',linestyle='--',alpha=0.5,linewidth=1.5,label='Day 28')
ax1.set_xlabel('Age (days)',fontsize=12); ax1.set_ylabel('Compressive Strength (MPa)',fontsize=12)
ax1.set_title('Compressive Strength vs. Age',fontsize=13,fontweight='bold')
ax1.legend(fontsize=10); ax1.grid(True,alpha=0.3)
ax1.set_xlim(0,91); ax1.set_ylim(0,max(strengths_high)*1.15)

days_temp=list(range(0,92)); temp_plot=temp_history+[temp_history[-1]]
ax2.step(days_temp,temp_plot,where='post',color='orangered',linewidth=2.5)
ax2.fill_between(days_temp,temp_plot,step='post',alpha=0.15,color='orangered')
ax2.axvline(x=early_end,color='gray',linestyle='--',alpha=0.6,linewidth=1.2)
ax2.axvline(x=mid_end,  color='gray',linestyle='--',alpha=0.6,linewidth=1.2)
ax2.text(early_end/2,          42,'Early',ha='center',fontsize=9,color='gray')
ax2.text((early_end+mid_end)/2,42,'Mid',  ha='center',fontsize=9,color='gray')
ax2.text((mid_end+91)/2,       42,'Late', ha='center',fontsize=9,color='gray')
ax2.set_xlabel('Age (days)',fontsize=12); ax2.set_ylabel('Curing Temperature (°C)',fontsize=12)
ax2.set_title('Curing Temperature History',fontsize=13,fontweight='bold')
ax2.set_xlim(0,91); ax2.set_ylim(0,45); ax2.grid(True,alpha=0.3)
plt.tight_layout(); st.pyplot(fig); plt.close()

# ── 특정 재령 조회 ────────────────────────────────────────
st.header(t_('query_header'))
col1,col2=st.columns([1,2])
with col1: query_age=st.number_input(t_('query_age'),1,91,28,1)
with col2:
    idx=query_age-1
    s_m=strengths_mid[idx]; s_l=strengths_low[idx]; s_h=strengths_high[idx]
    st.metric(label=f"{t_('metric_label')} — Day {query_age}",
              value=f"{s_m:.1f} MPa",
              delta=f"{t_('ci_delta')}: {s_l:.1f} ~ {s_h:.1f} MPa")

# ── 요약 테이블 ───────────────────────────────────────────
key_ages=[1,3,7,14,28,56,91]; summary=[]
for a in key_ages:
    i=a-1
    summary.append({t_('table_age'):a, t_('table_pred'):f"{strengths_mid[i]:.1f}",
                    t_('table_low'):f"{strengths_low[i]:.1f}", t_('table_high'):f"{strengths_high[i]:.1f}"})
st.table(pd.DataFrame(summary))

st.markdown("---")
st.caption(t_('caption'))
