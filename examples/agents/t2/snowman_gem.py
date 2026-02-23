import asyncio
import logging
from pathlib import Path

from noesium.agents.t2 import T2Agent, parse_yaml_file

logger = logging.getLogger(__name__)


async def demo_snowman_gem():
    """Demo using gem parser with YAML config for stock metrics extraction."""
    config_path = Path(__file__).parent / "snowman_balance.yml"
    result = parse_yaml_file(str(config_path))

    models = result.models
    target_model_class = result.target_model
    instruction = result.instruction

    if not target_model_class:
        target_model_class = models.get("StockKeyMetricsAll")
        if not target_model_class:
            raise ValueError(
                "Could not find StockKeyMetricsAll model in parsed models and no output_model was specified"
            )

    logger.info(f"📊 Using target model: {target_model_class.__name__}")
    if instruction:
        logger.info(f"🎯 Instruction: {instruction}")

    logger.info(f"🧩 Parsed {len(models)} models from gem config: {list(models.keys())}")

    t2_agent = T2Agent()
    try:
        result = await t2_agent.navigate_and_extract(
            url="https://xueqiu.com/snowman/S/SZ300457/detail#/ZYCWZB",
            instruction=instruction,
            schema=target_model_class,
            headless=False,
            use_vision=True,
        )
        logger.info(f"✅ Snowman gem extraction completed: {result}")
        await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"❌ Snowman gem demo failed: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo_snowman_gem())
