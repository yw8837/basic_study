# basic_study — 수업 복습 퀴즈 웹앱

내 블로그 수업 정리(`yearstudy_6/content`)를 자동 파싱해 **5유형 문제은행**을 만들고,
**맞춤 범위·20문항·유형랜덤** 퀴즈를 풀어 복습하는 Streamlit 웹앱.

## 문제 유형
1. 코드 빈칸 채우기  2. 코드→결과 예측  3. 결과→코드(역방향)  4. 개념·용어 객관식/OX  5. 주관식 단답

## 단계
1. ✅ 환경 세팅 (venv + requirements)
2. ⬜ 파싱 → `data/questions.json`
3. ⬜ 퀴즈 로직 + Streamlit UI + CLI
4. ⬜ GitHub → Streamlit Cloud 배포
5. ⬜ (2차) Supabase/Firebase 연결 + 오답노트 + 멀티유저

## 로컬 실행 (개발용)
```powershell
# 가상환경 활성화
.\venv\Scripts\Activate.ps1
# 퀴즈 데이터 생성 (2단계 구현 후)
python -m basic_study.parser
# 웹앱 실행 (3단계 구현 후)
streamlit run app.py
```

## 구조
```
basic_study/
├── data/questions.json      # 문제은행 (2단계 산출)
├── basic_study/
│   ├── parser/              # 파싱 + 출제엔진
│   └── quiz/                # 퀴즈 로직 + 채점 + storage 추상화
├── app.py                   # Streamlit 웹
├── cli.py                   # 터미널 실행
└── requirements.txt
```

설계서: `오늘수업/.omc/specs/deep-interview-basic-study.md`
