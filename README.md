# 콘크리트 압축강도 예측 시스템

배합비와 양생 온도이력을 입력하면 재령별 압축강도와 90% 신뢰구간을 예측합니다.

## 사용 모델
- **강도 발현**: T-TaAE model (Kim et al., 2001)
- **파라미터 예측**: XGBoost (학습 데이터 5,201개)

## 실행 방법
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 파일 구조
```
app.py              # 메인 앱
requirements.txt    # 의존성
model/
  model_Su.pkl      # Su 예측 모델
  t0_by_temp.pkl    # t0 온도 룩업 테이블
  params_fitted.csv # T-TaAE 피팅 파라미터
```

## 개발
- Chosun University, Department of Architectural Engineering
- Prof. Hyeong-Ki Kim
