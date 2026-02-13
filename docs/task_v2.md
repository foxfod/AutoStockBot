# 작업 체크리스트: 주식 선정 v2 구현

- [ ] `market_analyst.py` 리팩토링 <!-- id: 0 -->
    - [ ] 새로운 AI 프롬프트를 적용한 `generate_top_10_picks(market_type)` 구현 <!-- id: 1 -->
    - [ ] AI 응답 JSON 파싱 처리 추가 <!-- id: 2 -->
    - [ ] `save_top_picks` 및 `load_top_picks` 구현 <!-- id: 3 -->
- [ ] `selector.py` 로직 업데이트 <!-- id: 4 -->
    - [ ] `select_stocks`를 `select_stocks_kr`와 `select_stocks_us`로 분리 <!-- id: 5 -->
    - [ ] "Top 10"을 1순위(Priority 1) 소스로 통합 <!-- id: 6 -->
    - [ ] KR용 하드 필터 및 US용 컨텍스트 필터 구현 <!-- id: 7 -->
- [ ] 대시보드 통합 <!-- id: 8 -->
    - [ ] 백엔드 API 추가: `GET/POST/DELETE /api/top-picks` <!-- id: 9 -->
    - [ ] `dashboard.html`에 Top 10 패널 추가 <!-- id: 10 -->
    - [ ] 추가/새로고침/삭제 UI 로직 구현 <!-- id: 11 -->
- [ ] 검증 <!-- id: 12 -->
    - [ ] Top 10 생성 API 테스트 <!-- id: 13 -->
    - [ ] 대시보드 UI 흐름 검증 <!-- id: 14 -->
