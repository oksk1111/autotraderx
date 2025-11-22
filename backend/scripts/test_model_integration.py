"""
모델 통합 테스트 스크립트
실제 시장 데이터로 예측 수행
"""
import sys
sys.path.insert(0, '/app')

import numpy as np
import pandas as pd
from pathlib import Path

from app.ml.predictor import HybridPredictor
from app.ml.feature_builder import build_features_from_market_data

# 테스트용 데이터 로드
DATA_DIR = Path("/app/data/processed")

def test_single_prediction(market: str = "KRW-BTC"):
    """단일 예측 테스트"""
    print(f"\n{'='*60}")
    print(f"Testing prediction for {market}")
    print(f"{'='*60}\n")
    
    # 시퀀스 파일 로드
    market_name = market.replace("-", "_")
    sequence_file = DATA_DIR / f"{market_name}_minute60_sequences.npz"
    
    if not sequence_file.exists():
        print(f"❌ Sequence file not found: {sequence_file}")
        return False
    
    # 시퀀스 로드
    data = np.load(sequence_file)
    X = data['X']  # (N, 24, 46)
    y = data['y']  # (N,)
    
    print(f"✅ Loaded sequences: X.shape={X.shape}, y.shape={y.shape}")
    
    # 마지막 시퀀스로 예측
    test_sequence = X[-1]  # (24, 46)
    actual_label = y[-1]
    
    label_map = {-1: "Sell", 0: "Hold", 1: "Buy"}
    print(f"📊 Test sequence shape: {test_sequence.shape}")
    print(f"🎯 Actual label: {label_map[actual_label]}")
    
    # 예측 수행
    predictor = HybridPredictor()
    
    features = {
        "market": market,
        "sequence": test_sequence
    }
    
    signal = predictor.infer(features)
    
    # 결과 출력
    print(f"\n🤖 Model Prediction:")
    print(f"   Market: {signal.market}")
    print(f"   Buy Probability:  {signal.buy_probability:.4f}")
    print(f"   Sell Probability: {signal.sell_probability:.4f}")
    print(f"   Action: {signal.action}")
    print(f"   Confidence: {signal.confidence:.4f}")
    print(f"   Emergency Score: {signal.emergency_score:.4f}")
    
    # 정확도 검증
    predicted_correct = (
        (signal.action == "BUY" and actual_label == 1) or
        (signal.action == "SELL" and actual_label == -1) or
        (signal.action == "HOLD" and actual_label == 0)
    )
    
    print(f"\n{'✅' if predicted_correct else '❌'} Prediction {'CORRECT' if predicted_correct else 'INCORRECT'}")
    
    return True


def test_multi_coin():
    """다중 코인 예측 테스트"""
    print(f"\n{'='*60}")
    print(f"Testing Multi-Coin Model Manager")
    print(f"{'='*60}\n")
    
    from app.ml.model_manager import MultiCoinModelManager
    
    manager = MultiCoinModelManager()
    manager.load_all_models()
    
    loaded_markets = manager.get_loaded_markets()
    print(f"✅ Loaded models for {len(loaded_markets)} markets:")
    for market in loaded_markets:
        print(f"   - {market}")
    
    # 각 마켓에 대해 예측 수행
    for market in ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]:
        market_name = market.replace("-", "_")
        sequence_file = DATA_DIR / f"{market_name}_minute60_sequences.npz"
        
        if not sequence_file.exists():
            print(f"\n⚠️  No data for {market}")
            continue
        
        data = np.load(sequence_file)
        X = data['X']
        y = data['y']
        
        # 랜덤 샘플 5개 테스트
        indices = np.random.choice(len(X), min(5, len(X)), replace=False)
        correct = 0
        
        print(f"\n📊 Testing {market} with {len(indices)} samples:")
        
        for idx in indices:
            sequence = X[idx]
            actual_label = y[idx]
            
            signal = manager.predict(market, sequence)
            
            if signal is not None:
                predicted_correct = (
                    (signal.action == "BUY" and actual_label == 1) or
                    (signal.action == "SELL" and actual_label == -1) or
                    (signal.action == "HOLD" and actual_label == 0)
                )
                if predicted_correct:
                    correct += 1
                
                status = "✅" if predicted_correct else "❌"
                print(f"   {status} Sample {idx}: Predicted={signal.action}, Actual={['Sell', 'Hold', 'Buy'][actual_label+1]}, Conf={signal.confidence:.3f}")
        
        accuracy = correct / len(indices) * 100
        print(f"   📈 Sample Accuracy: {accuracy:.1f}% ({correct}/{len(indices)})")


def test_feature_builder():
    """Feature builder 테스트"""
    print(f"\n{'='*60}")
    print(f"Testing Feature Builder")
    print(f"{'='*60}\n")
    
    # 실제 CSV 데이터 로드
    raw_data_dir = Path("/app/data/raw")
    csv_file = raw_data_dir / "KRW_BTC_minute60.csv"
    
    if not csv_file.exists():
        print(f"❌ CSV file not found: {csv_file}")
        return False
    
    df = pd.read_csv(csv_file)
    print(f"✅ Loaded CSV: {len(df)} rows")
    print(f"   Columns: {list(df.columns)}")
    
    # 최근 200개 행 추출
    recent_data = df.tail(200).to_dict('records')
    
    try:
        features = build_features_from_market_data(recent_data, "KRW-BTC")
        sequence = features['sequence']
        
        print(f"\n✅ Feature building successful!")
        print(f"   Sequence shape: {sequence.shape}")
        print(f"   Expected: (24, 46)")
        
        # 예측 수행
        predictor = HybridPredictor()
        signal = predictor.infer(features)
        
        print(f"\n🤖 Prediction result:")
        print(f"   Action: {signal.action}")
        print(f"   Buy: {signal.buy_probability:.4f}, Sell: {signal.sell_probability:.4f}")
        print(f"   Confidence: {signal.confidence:.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Feature building failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🚀 Model Integration Test Suite")
    print("="*60)
    
    # Test 1: Single prediction
    success1 = test_single_prediction("KRW-BTC")
    
    # Test 2: Feature builder
    success2 = test_feature_builder()
    
    # Test 3: Multi-coin manager
    test_multi_coin()
    
    print(f"\n{'='*60}")
    print(f"Test Suite Complete!")
    print(f"{'='*60}\n")
