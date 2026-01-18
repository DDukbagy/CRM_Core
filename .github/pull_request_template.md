## PR Checklist (운영/관측)

- [ ] 이 변경이 운영 장애(5xx, ready 실패, latency)에 영향을 줄 수 있는가?
- [ ] 필요하면 관측/알람(CloudWatch) 변경도 함께 반영했는가? (또는 “불필요” 사유를 적었는가?)
- [ ] 배포 후 staging smoke(/health/ready, /openapi.json)가 통과하는가?
- [ ] 회귀 테스트(pytest)가 통과하는가?

## Notes
(필요시) 알람/관측 변경이 없었던 이유:
-
