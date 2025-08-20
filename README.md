## 배포 방법

1. 가상환경 설정(python 3.12)
2. pip install -r requirements.txt
3. cloudfront_private_key.pem 파일 준비
4. aws 서버 배포용 access_key/secret_key 받아서 접근권한 받기
5. eb deploy

- 참고자료: https://docs.aws.amazon.com/ko_kr/elasticbeanstalk/latest/dg/eb-cli3.html
- 환경변수 개발/운영별로 각각 beanstalk 환경변수에 다 저장해뒀음

## 환경 구성

1. DB - AWS RDS/Postgres
2. 이미지파일 - AWS S3 / CloudFront
3. 로드밸런스 및 서버인스턴스 - AWS Elastic Beanstalk
4. 호스팅 - Godaddy
5. 배포방식 - EB deploy (깃허브 액션 돈내야되서 대체함. 바꿔주세요)
6. RDS 로컬에서 접근할려고 bastion 서버 하나 파놨음
   - ssh -i ~/.ssh/pio-bastion.pem ec2-user@43.203.127.92 -L 5433:phoneinone-dev.ch4i06g6mr6s.ap-northeast-2.rds.amazonaws.com:5432
   - ssh -i ~/.ssh/pio-bastion.pem ec2-user@43.203.127.92 -L 5433:phoneinone-prod.ch4i06g6mr6s.ap-northeast-2.rds.amazonaws.com:5432

## 계정 및 aws 관리

1. external.services@smartel.co.kr 로 루트계정 새로 팠음
