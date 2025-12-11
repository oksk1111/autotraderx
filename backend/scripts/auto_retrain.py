"""
자동 모델 재훈련 스크립트
매일 새벽 3시에 실행되어 최신 데이터로 ML 모델을 재훈련합니다.
"""
import sys
from pathlib import Path
import subprocess
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def run_command(command: list, description: str) -> bool:
    """
    명령 실행 및 로깅
    
    Args:
        command: 실행할 명령어 리스트
        description: 명령 설명
        
    Returns:
        bool: 성공 여부
    """
    logger.info(f"🔄 {description}...")
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_ROOT
        )
        
        logger.info(f"✅ {description} 완료")
        if result.stdout:
            logger.debug(f"출력: {result.stdout[:500]}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ {description} 실패: {e}")
        if e.stderr:
            logger.error(f"에러: {e.stderr[:500]}")
        return False


def archive_model():
    """
    현재 모델을 아카이브 폴더로 백업합니다.
    """
    model_dir = PROJECT_ROOT / "backend" / "models"
    archive_dir = model_dir / "archive"
    archive_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 주요 모델 파일 백업
    model_files = ["lstm_best.pth", "lightgbm_model.txt", "model_metadata.json"]
    
    for filename in model_files:
        src = model_dir / filename
        if src.exists():
            dst = archive_dir / f"{filename.split('.')[0]}_{timestamp}.{filename.split('.')[1]}"
            try:
                import shutil
                shutil.copy2(src, dst)
                logger.info(f"📦 모델 백업 완료: {dst.name}")
            except Exception as e:
                logger.error(f"모델 백업 실패 ({filename}): {e}")


def main():
    """
    자동 재훈련 메인 함수
    
    실행 순서:
    1. 최신 데이터 수집
    2. 피처 엔지니어링
    3. 모델 훈련
    4. 모델 교체 (자동)
    """
    start_time = datetime.now()
    logger.info("="*70)
    logger.info(f"🤖 자동 모델 재훈련 시작: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)
    
    # 1단계: 데이터 수집
    if not run_command(
        [sys.executable, str(SCRIPTS_DIR / "collect_data.py")],
        "1단계: 최신 시장 데이터 수집"
    ):
        logger.error("데이터 수집 실패 - 재훈련 중단")
        return False
    
    # 2단계: 피처 준비
    if not run_command(
        [sys.executable, str(SCRIPTS_DIR / "prepare_features.py")],
        "2단계: 피처 엔지니어링 및 시퀀스 생성"
    ):
        logger.error("피처 준비 실패 - 재훈련 중단")
        return False
    
    # 3단계: 모델 훈련
    # 훈련 전 기존 모델 백업
    archive_model()
    
    if not run_command(
        [sys.executable, str(SCRIPTS_DIR / "train_model.py")],
        "3단계: LSTM + LightGBM 하이브리드 모델 훈련"
    ):
        logger.error("모델 훈련 실패 - 재훈련 중단")
        return False
    
    # 완료
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("="*70)
    logger.info(f"✅ 자동 모델 재훈련 완료!")
    logger.info(f"⏱️ 소요 시간: {duration:.1f}초 ({duration/60:.1f}분)")
    logger.info(f"📁 모델 저장 위치: {PROJECT_ROOT / 'models'}")
    logger.info("="*70)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ 예외 발생: {e}", exc_info=True)
        sys.exit(1)
