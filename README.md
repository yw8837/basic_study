# basic_study — 수업 복습 퀴즈 웹앱

내 블로그 수업 정리(`yearstudy_6/content`)를 자동 파싱해 **5유형 문제은행**을 만들고,
**맞춤 범위·20문항·유형랜덤** 퀴즈를 풀어 복습하는 Streamlit 웹앱.

## 문제 유형
1. 코드 빈칸 채우기  2. 코드→결과 예측  3. 결과→코드(역방향)  4. 개념·용어 객관식/OX  5. 주관식 단답

## 단계
1. ✅ 환경 세팅 (venv + requirements)
2. ✅ 파싱 → `data/questions.json` (1,627개 문제)
3. ✅ 퀴즈 로직 + Streamlit UI + CLI
4. ✅ GitHub → Streamlit Cloud 배포 준비
5. ⬜ (2차) Supabase/Firebase 연결 + 오답노트 + 멀티유저

## 로컬 실행

```powershell
# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# 문제은행 재생성 (새 수업 추가 후 실행)
python parse_questions.py

# 웹앱 실행
streamlit run app.py

# CLI 퀴즈
python cli.py
```

## Streamlit Cloud 배포 방법
1. GitHub에 push: `git push origin main`
2. [share.streamlit.io](https://share.streamlit.io) 접속 → "New app"
3. repo `yw8837/basic_study`, branch `main`, main file `app.py` 선택
4. Deploy 클릭 → 자동 배포 완료
5. 이후 `git push` 할 때마다 자동 갱신

## 새 수업 추가 방법
```powershell
# 1. yearstudy_6/content/posts 에 새 강의 md 추가 후
python parse_questions.py       # 문제은행 재생성
git add data/questions.json
git commit -m "수업 추가: {날짜 주제}"
git push origin main            # Streamlit Cloud 자동 갱신
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
