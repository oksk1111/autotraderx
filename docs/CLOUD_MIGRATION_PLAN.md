# 클라우드 마이그레이션 계획 (Free Tier)

## 1. 개요
본 문서는 `autotraderx` 서비스를 로컬 환경에서 클라우드 환경으로 이전하기 위한 계획을 기술합니다.
현재 1인 사용자, 로컬 학습/클라우드 추론(Inference) 구조, 낮은 트래픽 특성을 고려하여 **비용 효율적인 무료(Free Tier)** 환경을 선정하고 구축합니다.

## 2. 클라우드 선정: Oracle Cloud Infrastructure (OCI)
가장 강력한 "Always Free" (평생 무료) 티어를 제공하는 오라클 클라우드를 1순위로 추천합니다.

### 2.1 OCI Always Free 스펙 (추천)
- **인스턴스**: VM.Standard.A1.Flex (ARM 프로세서)
- **CPU**: 최대 4 OCPU (4 vCPU 상당)
- **RAM**: **최대 24 GB** (타사 무료 티어는 보통 1GB)
- **스토리지**: 200 GB 블록 볼륨
- **장점**: 머신러닝 추론, DB, Redis, 백엔드를 동시에 구동하기에 충분한 메모리를 제공합니다.
- **주의**: ARM 아키텍처이므로 Docker 이미지 빌드 시 멀티 아키텍처 빌드(`linux/arm64`)가 필요할 수 있습니다. (Python은 대부분 호환됨)

### 2.2 대안 (OCI 가입 불가 시)
1. **Google Cloud Platform (GCP)**: `e2-micro` (2 vCPU, 1GB RAM). 메모리가 매우 부족하여 Swap 설정 필수. ML 모델 로딩 시 OOM(메모리 부족) 발생 가능성 높음.
2. **AWS Free Tier**: `t2.micro` 또는 `t3.micro` (1 vCPU, 1GB RAM). 12개월 한정 무료.

## 3. 아키텍처 변경 사항

### 3.1 배포 구조
- **기존**: 로컬 `docker-compose up`
- **변경**: 클라우드 VM 내 `docker-compose` 구동
    - **Backend**: FastAPI 서버 (모델 추론 포함)
    - **Worker**: Celery Worker (매매 로직, 데이터 수집)
    - **Beat**: Celery Beat (스케줄링)
    - **Redis**: 메시지 브로커 및 캐시
    - **PostgreSQL**: 메인 데이터베이스
    - **Frontend**: Nginx 또는 Vite Preview (프로덕션 빌드 서빙)

### 3.2 ML 모델 배포 파이프라인
1. **로컬 학습**: 고성능 PC/GPU에서 모델 학습 (`.pth`, `.txt` 파일 생성)
2. **업로드**: 학습된 모델 파일을 서버로 전송 (`scp` 또는 Git LFS, S3 등)
3. **적용**: 서버의 컨테이너 재시작 또는 핫 리로드

## 4. 보안 설정
- **방화벽 (Security List)**:
    - Inbound: 22 (SSH), 80 (HTTP), 443 (HTTPS) 만 허용
    - DB(5432), Redis(6379)는 외부 접근 차단 (Docker Network 내부 통신만 허용)
- **환경 변수**: `.env` 파일은 서버에 직접 생성하여 관리 (Git 포함 금지)

## 5. 마이그레이션 단계 (Todo)
1. [ ] 클라우드 인스턴스 생성 (Ubuntu 22.04 LTS 권장)
2. [ ] 서버 기본 설정 (Docker, Docker Compose 설치, 방화벽 설정)
3. [ ] 프로젝트 코드 배포 (Git Clone)
4. [ ] 환경 변수 설정 (.env)
5. [ ] 데이터베이스 초기화 (Alembic Migration)
6. [ ] 서비스 구동 및 헬스 체크

## 6. 향후 확장
- 트래픽 증가 시: 로드 밸런서 도입
- 데이터 증가 시: 관리형 DB (RDS/Cloud SQL) 고려 (비용 발생)
