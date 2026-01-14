from app.db.session import SessionLocal
from app.models.trading import AutoTradingConfig

def update_strategy():
    db = SessionLocal()
    try:
        config = db.query(AutoTradingConfig).order_by(AutoTradingConfig.id.desc()).first()
        if config:
            print(f"Current strategy: {config.strategy_option}")
            config.strategy_option = "breakout_strategy"
            db.commit()
            print(f"Updated strategy to: {config.strategy_option}")
        else:
            print("No config found, creating new one...")
            config = AutoTradingConfig(strategy_option="breakout_strategy")
            db.add(config)
            db.commit()
            print("Created new config with breakout_strategy")
    finally:
        db.close()

if __name__ == "__main__":
    update_strategy()
