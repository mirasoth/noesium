import asyncio
import logging
from typing import List

from pydantic import BaseModel, Field

from noesium.agents.t2 import T2Agent

logger = logging.getLogger(__name__)


class StockMetric(BaseModel):
    metric_name: str = Field(description="指标名称，如营业收入、营业收入同比增长、净利润")
    report_time: str = Field(description="报告时间，如2024中报、2024三季报")
    value: str = Field(description="指标值，如100亿")
    yoy_growth: str = Field(description="同比增长，如-10%")


class StockKeyMetricsAll(BaseModel):
    stock_name: str = Field(description="股票名称，如雪人股份")
    stock_code: str = Field(description="股票代码，如002639")
    key_measures: List[StockMetric] = Field(description="关键指标")
    per_stock_measures: List[StockMetric] = Field(description="每股指标")
    profitability: List[StockMetric] = Field(description="盈利能力指标")
    financial_risks: List[StockMetric] = Field(description="财务风险指标")
    opertional_capacity: List[StockMetric] = Field(description="运营能力指标")


async def demo_snowman_balance():
    t2_agent = T2Agent()
    try:
        result = await t2_agent.navigate_and_extract(
            url="https://xueqiu.com/snowman/S/SZ300457/detail#/ZYCWZB",
            instruction="页面加载完成后，选择【同比】按钮，解析【关键指标】、【每股指标】、【盈利能力】、【财务风险】、【运营能力】五类指标，并格式化输出到指定数据结构",
            schema=StockKeyMetricsAll,
            headless=False,
            use_vision=True,
        )
        logger.info(f"✅ Snowman balance completed: {result}")
        await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"❌ Snowman balance demo failed: {e}")
        raise


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Run the demo
    asyncio.run(demo_snowman_balance())
